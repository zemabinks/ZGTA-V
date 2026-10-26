import Foundation

/// Downloads the archive into small rolling chunk files and hands them to libarchive.
/// At most `maxPendingBytes` of downloaded-but-unread data sit on disk; a chunk file is
/// deleted as soon as it was read. A dropped connection is resumed with an HTTP Range request
/// from the exact byte where it stopped; meanwhile the unpacker simply waits for more bytes.
final class RemoteSource: NSObject, ArchiveByteSource, URLSessionDataDelegate, @unchecked Sendable {
    private let urls: [URL]
    private let chunkFolder: URL
    private let options: GameInstaller.Options
    private let log: (String) -> Void
    private let readSize = 4 << 20
    private let buffer: UnsafeMutableRawPointer

    private let cond = NSCondition()
    // --- guarded by cond ---
    private var sealed: [(url: URL, size: Int64)] = []
    private var pending: Int64 = 0
    private(set) var peakPending: Int64 = 0
    private var downloadDone = false
    private var cancelled = false
    private var stopError: InstallError?
    private var consumed: Int64 = 0
    private(set) var downloaded: Int64 = 0
    private(set) var retries = 0
    private(set) var contentTotal: Int64?
    // --------------------------

    // Download state (delegate queue only).
    private let queue: OperationQueue
    private var session: URLSession!
    private var task: URLSessionDataTask?
    private var partIndex = 0
    private var partOffset: Int64 = 0
    private var partLength: Int64?
    private var partLengths: [Int64?]
    private var validator: (etag: String?, lastModified: String?)?
    private var discardBytes: Int64 = 0
    private var sniffed = false
    private var chunkFD: Int32 = -1
    private var chunkURL: URL?
    private var chunkBytes: Int64 = 0
    private var chunkCounter = 0
    private var waitingForRoom = false
    private var streamingFallback = false
    private var requestedEnd: Int64?
    private var lastProgress = Date()
    private var attempt = 0
    private var responseFailure: InstallError?

    // Reading state (unpacker thread only).
    private var readFD: Int32 = -1
    private var readChunk: (url: URL, size: Int64)?

    init(urls: [URL], workFolder: URL, options: GameInstaller.Options, log: @escaping (String) -> Void) throws {
        self.urls = urls
        self.options = options
        self.log = log
        chunkFolder = workFolder.appendingPathComponent("chunks", isDirectory: true)
        try? FileManager.default.removeItem(at: chunkFolder)
        do { try FileManager.default.createDirectory(at: chunkFolder, withIntermediateDirectories: true) } catch {
            throw InstallError(.writeFailed, "The download folder could not be created.", detail: error.localizedDescription)
        }
        partLengths = Array(repeating: nil, count: urls.count)
        buffer = UnsafeMutableRawPointer.allocate(byteCount: readSize, alignment: 16)
        queue = OperationQueue()
        queue.maxConcurrentOperationCount = 1
        queue.name = "GameInstaller.download"
        super.init()
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = options.requestTimeout
        config.timeoutIntervalForResource = 7 * 24 * 3600
        config.requestCachePolicy = .reloadIgnoringLocalAndRemoteCacheData
        config.urlCache = nil
        config.httpMaximumConnectionsPerHost = 1
        config.waitsForConnectivity = false
        session = URLSession(configuration: config, delegate: self, delegateQueue: queue)
    }

    deinit {
        buffer.deallocate()
        if readFD >= 0 { close(readFD) }
    }

    func start() { queue.addOperation { self.startRequest() } }

    var bytesConsumed: Int64 { cond.lock(); defer { cond.unlock() }; return consumed }
    var pendingBytes: Int64 { cond.lock(); defer { cond.unlock() }; return pending }
    var stats: (downloaded: Int64, total: Int64?, pending: Int64, peak: Int64, retries: Int) {
        cond.lock(); defer { cond.unlock() }
        return (downloaded, contentTotal, pending, peakPending, retries)
    }
    var failure: InstallError? { cond.lock(); defer { cond.unlock() }; return stopError }

    func cancel() {
        cond.lock()
        cancelled = true
        if stopError == nil { stopError = InstallError(.cancelled, "The install was cancelled.") }
        cond.broadcast()
        cond.unlock()
        queue.addOperation { self.task?.cancel(); self.session.invalidateAndCancel() }
    }

    func finish(success: Bool) {
        queue.addOperation {
            self.task?.cancel()
            self.session.invalidateAndCancel()
            if self.chunkFD >= 0 { close(self.chunkFD); self.chunkFD = -1 }
        }
        queue.waitUntilAllOperationsAreFinished()
        if readFD >= 0 { close(readFD); readFD = -1 }
        try? FileManager.default.removeItem(at: chunkFolder)
    }

    // MARK: Reading (unpacker thread)

    func nextBlock() -> (UnsafeRawPointer, Int)? {
        while true {
            if readFD >= 0 {
                let n = read(readFD, buffer, readSize)
                if n > 0 {
                    cond.lock(); consumed += Int64(n); cond.unlock()
                    return (UnsafeRawPointer(buffer), n)
                }
                if n < 0 {
                    fail(InstallError(.writeFailed, "Reading a downloaded chunk failed.", detail: String(cString: strerror(errno))))
                    return nil
                }
                // Chunk used up: delete it and make room for more downloading.
                close(readFD); readFD = -1
                if let chunk = readChunk { unlink(chunk.url.path) }
                cond.lock()
                pending -= readChunk?.size ?? 0
                readChunk = nil
                cond.unlock()
                queue.addOperation { self.resumeIfRoom() }
            }
            cond.lock()
            while sealed.isEmpty && !downloadDone && stopError == nil { cond.wait() }
            if let error = stopError { cond.unlock(); _ = error; return nil }
            if sealed.isEmpty && downloadDone { cond.unlock(); return (UnsafeRawPointer(buffer), 0) }
            let next = sealed.removeFirst()
            cond.unlock()
            readFD = open(next.url.path, O_RDONLY)
            readChunk = next
            if readFD < 0 {
                fail(InstallError(.writeFailed, "A downloaded chunk could not be opened.", detail: String(cString: strerror(errno))))
                return nil
            }
        }
    }

    private func fail(_ error: InstallError) {
        cond.lock()
        if stopError == nil { stopError = error }
        cond.broadcast()
        cond.unlock()
        queue.addOperation { self.task?.cancel() }
    }

    // MARK: Downloading (delegate queue)

    private var isStopped: Bool { cond.lock(); defer { cond.unlock() }; return cancelled || stopError != nil }

    /// Bytes asked for per request. The next window is only requested when it fits under
    /// maxPendingBytes, which is what keeps the disk bound strict (URLSessionDataTask.suspend()
    /// does not reliably stop data from arriving).
    private var windowSize: Int64 { max(options.chunkSize, min(64 << 20, options.maxPendingBytes / 2)) }

    private func startRequest() {
        task = nil
        guard !isStopped else { return }
        var request = URLRequest(url: urls[partIndex])
        for (k, v) in options.httpHeaders { request.setValue(v, forHTTPHeaderField: k) }
        request.setValue("identity", forHTTPHeaderField: "Accept-Encoding")
        if streamingFallback {
            requestedEnd = nil
            if partOffset > 0 { request.setValue("bytes=\(partOffset)-", forHTTPHeaderField: "Range") }
        } else {
            cond.lock(); let room = options.maxPendingBytes - pending; cond.unlock()
            var want = min(windowSize, room)
            if let length = partLength { want = min(want, length - partOffset) }
            // Wait for the unpacker to make room (it calls resumeIfRoom after each chunk).
            if want < min(windowSize / 4, partLength.map { $0 - partOffset } ?? Int64.max) || want <= 0 {
                waitingForRoom = true
                return
            }
            requestedEnd = partOffset + want
            request.setValue("bytes=\(partOffset)-\(partOffset + want - 1)", forHTTPHeaderField: "Range")
        }
        if partOffset > 0 {
            if let v = validator?.etag, !v.hasPrefix("W/") { request.setValue(v, forHTTPHeaderField: "If-Range") }
            else if let v = validator?.lastModified { request.setValue(v, forHTTPHeaderField: "If-Range") }
        }
        discardBytes = 0
        responseFailure = nil
        let task = session.dataTask(with: request)
        self.task = task
        task.resume()
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive response: URLResponse,
                    completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
        guard dataTask === task else { completionHandler(.cancel); return }
        guard let http = response as? HTTPURLResponse else {
            responseFailure = InstallError(.httpError, "The link did not answer like a web server.", detail: response.url?.absoluteString)
            completionHandler(.cancel); return
        }
        let status = http.statusCode
        let type = (http.value(forHTTPHeaderField: "Content-Type") ?? "").lowercased()
        if status == 200 || status == 206, type.hasPrefix("text/html") || type.hasPrefix("application/xhtml") {
            responseFailure = webPageError(detail: "Content-Type: \(type)")
            completionHandler(.cancel); return
        }
        switch status {
        case 200:
            if partOffset == 0 && !streamingFallback {
                // Asked for a window, got the whole file: the server does not do Range.
                streamingFallback = true
                requestedEnd = nil
                log("The server does not support resuming (HTTP Range); streaming the whole file. Downloaded data is held back by pausing reads instead of by request size.")
            }
            if partOffset > 0 {
                if validator != nil && (http.value(forHTTPHeaderField: "ETag") != validator?.etag || http.value(forHTTPHeaderField: "Last-Modified") != validator?.lastModified) {
                    responseFailure = InstallError(.fileChangedOnServer, "The file on the server changed while it was downloading. Start the install again.", detail: "HTTP 200 to a resume request")
                    completionHandler(.cancel); return
                }
                // The server ignores Range: skip what we already have.
                discardBytes = partOffset
                log("Server ignored the resume request; skipping \(partOffset) bytes already received.")
            }
            noteLength(http.expectedContentLength > 0 ? http.expectedContentLength : nil)
        case 206:
            let range = http.value(forHTTPHeaderField: "Content-Range") ?? ""
            // "bytes start-end/total"
            let numbers = range.split(whereSeparator: { !$0.isNumber }).compactMap { Int64($0) }
            guard numbers.count >= 2, numbers[0] == partOffset else {
                responseFailure = InstallError(.httpError, "The server sent the wrong part of the file when resuming.", detail: "Content-Range: \(range), wanted \(partOffset)")
                completionHandler(.cancel); return
            }
            if numbers.count >= 3 { noteLength(numbers[2]) }
        case 416:
            // Asked past the end: fine when we already have the whole part.
            let total = (http.value(forHTTPHeaderField: "Content-Range") ?? "").split(separator: "/").last.flatMap { Int64($0) }
            if let total { noteLength(total) }
            guard let length = partLength, partOffset >= length else {
                responseFailure = httpError(status, retryAfter: nil)
                completionHandler(.cancel); return
            }
        default:
            responseFailure = httpError(status, retryAfter: http.value(forHTTPHeaderField: "Retry-After"))
            completionHandler(.cancel); return
        }
        if validator == nil || partOffset == 0 {
            validator = (http.value(forHTTPHeaderField: "ETag"), http.value(forHTTPHeaderField: "Last-Modified"))
        }
        if status == 416 { requestedEnd = nil }
        attempt = 0
        completionHandler(.allow)
    }

    private func noteLength(_ length: Int64?) {
        guard let length else { return }
        partLength = length // 200: Content-Length of the whole file; 206: the total after "/"
        partLengths[partIndex] = length
        cond.lock()
        if partLengths.allSatisfy({ $0 != nil }) { contentTotal = partLengths.reduce(0) { $0 + ($1 ?? 0) } }
        cond.unlock()
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        guard dataTask === task, !isStopped else { return }
        var bytes = data
        if discardBytes > 0 {
            let drop = Int(min(discardBytes, Int64(bytes.count)))
            discardBytes -= Int64(drop)
            bytes = bytes.dropFirst(drop)
            if bytes.isEmpty { return }
        }
        if !sniffed && partOffset == 0 {
            sniffed = true
            if looksLikeHTML(bytes.prefix(512)) {
                responseFailure = webPageError(detail: "body starts with HTML")
                dataTask.cancel(); return
            }
        }
        if !write(bytes) { dataTask.cancel(); return }
        partOffset += Int64(bytes.count)
        lastProgress = Date()
        cond.lock()
        downloaded += Int64(bytes.count)
        cond.unlock()
        if chunkBytes >= options.chunkSize { seal() }
        if streamingFallback {
            // No Range support: hold this delegate queue until the unpacker catches up.
            cond.lock()
            while pending >= options.maxPendingBytes - options.chunkSize && !cancelled && stopError == nil {
                _ = cond.wait(until: Date().addingTimeInterval(1))
            }
            cond.unlock()
            lastProgress = Date()
        }
    }

    private func resumeIfRoom() {
        guard waitingForRoom, !isStopped else { return }
        waitingForRoom = false
        lastProgress = Date()
        startRequest() // waits again if there is still not enough room
    }

    func urlSession(_ session: URLSession, task finished: URLSessionTask, didCompleteWithError error: Error?) {
        guard finished === task else { return }
        seal()
        if isStopped { return }
        if let failure = responseFailure {
            if failure.kind == .httpError, failure.detail?.hasPrefix("retry") == true {
                retry(reason: failure.message, hardFailure: failure); return
            }
            stop(failure); return
        }
        if let error = error as NSError? {
            if error.domain == NSURLErrorDomain, [NSURLErrorBadURL, NSURLErrorUnsupportedURL, NSURLErrorCannotFindHost,
                NSURLErrorSecureConnectionFailed, NSURLErrorServerCertificateUntrusted, NSURLErrorServerCertificateHasBadDate,
                NSURLErrorServerCertificateNotYetValid, NSURLErrorAppTransportSecurityRequiresSecureConnection].contains(error.code) {
                // Retry a missing host a few times (DNS hiccup), but these usually mean a bad link.
                if error.code == NSURLErrorCannotFindHost && Date().timeIntervalSince(lastProgress) < 20 {
                    retry(reason: error.localizedDescription, hardFailure: nil); return
                }
                stop(InstallError(.httpError, "The link could not be opened: \(error.localizedDescription)", detail: "\(error.domain) \(error.code)")); return
            }
            retry(reason: error.localizedDescription, hardFailure: nil); return
        }
        // Finished without error: did we get the whole window / part?
        if let end = requestedEnd, partOffset < end, partLength.map({ partOffset < $0 }) ?? true {
            retry(reason: "connection closed early at \(partOffset) of \(end) bytes", hardFailure: nil); return
        }
        if let length = partLength, partOffset < length {
            if requestedEnd != nil { attempt = 0; startRequest(); return } // next window
            retry(reason: "connection closed early at \(partOffset) of \(length) bytes", hardFailure: nil); return
        }
        if partLength == nil && requestedEnd != nil {
            // Window answered without a total size: keep asking until the server says 416.
            attempt = 0; startRequest(); return
        }
        log("Downloaded \(urls[partIndex].lastPathComponent): \(partOffset) bytes")
        partIndex += 1
        if partIndex < urls.count {
            partOffset = 0; partLength = nil; validator = nil; sniffed = false; attempt = 0; streamingFallback = false
            startRequest()
        } else {
            cond.lock(); downloadDone = true; cond.broadcast(); cond.unlock()
            session.finishTasksAndInvalidate()
        }
    }

    private func retry(reason: String, hardFailure: InstallError?) {
        let stalled = Date().timeIntervalSince(lastProgress)
        if stalled > options.giveUpAfter {
            stop(hardFailure ?? InstallError(.networkLost, "The internet connection was lost and did not come back for \(options.giveUpAfter >= 120 ? "\(Int(options.giveUpAfter / 60)) minutes" : "\(Int(options.giveUpAfter)) seconds"). Check your connection and start again; what was unpacked so far is kept.", detail: reason))
            return
        }
        attempt += 1
        cond.lock(); retries += 1; cond.unlock()
        let delay = min(15.0, 0.5 * pow(2.0, Double(min(attempt, 6))))
        log("Download interrupted at byte \(partOffset) (\(reason)); resuming in \(String(format: "%.1f", delay)) s (try \(attempt))")
        let deadline = DispatchTime.now() + delay
        DispatchQueue.global(qos: .utility).asyncAfter(deadline: deadline) { [weak self] in
            self?.queue.addOperation { self?.startRequest() }
        }
    }

    private func stop(_ error: InstallError) {
        log("Download stopped: \(error)")
        cond.lock()
        if stopError == nil { stopError = error }
        cond.broadcast()
        cond.unlock()
    }

    // MARK: Chunk files

    private func write(_ data: Data) -> Bool {
        if chunkFD < 0 {
            chunkCounter += 1
            let url = chunkFolder.appendingPathComponent(String(format: "chunk-%08d", chunkCounter))
            chunkFD = open(url.path, O_WRONLY | O_CREAT | O_TRUNC, 0o600)
            guard chunkFD >= 0 else { stop(diskError(errno)); return false }
            chunkURL = url
            chunkBytes = 0
        }
        let ok: Bool = data.withUnsafeBytes { raw in
            var p = raw.baseAddress!, left = raw.count
            while left > 0 {
                let n = Darwin.write(chunkFD, p, left)
                if n < 0 { if errno == EINTR { continue }; return false }
                p += n; left -= n
            }
            return true
        }
        guard ok else { stop(diskError(errno)); return false }
        chunkBytes += Int64(data.count)
        cond.lock()
        pending += Int64(data.count)
        peakPending = max(peakPending, pending)
        cond.unlock()
        return true
    }

    /// Hands the current chunk file to the reader.
    private func seal() {
        guard chunkFD >= 0, let url = chunkURL else { return }
        close(chunkFD); chunkFD = -1
        if chunkBytes == 0 { unlink(url.path); return }
        cond.lock()
        sealed.append((url, chunkBytes))
        cond.broadcast()
        cond.unlock()
        chunkURL = nil
        chunkBytes = 0
    }

    // MARK: Messages

    private func looksLikeHTML(_ data: Data) -> Bool {
        guard var text = String(data: data, encoding: .utf8) ?? String(data: data, encoding: .isoLatin1) else { return false }
        text = text.trimmingCharacters(in: .whitespacesAndNewlines.union(CharacterSet(charactersIn: "\u{FEFF}"))).lowercased()
        return text.hasPrefix("<!doctype html") || text.hasPrefix("<html") || text.hasPrefix("<head") || text.hasPrefix("<!--") && text.contains("<html")
    }

    private func webPageError(detail: String) -> InstallError {
        InstallError(.webPageNotFile, "The link opens a web page, not the game file. On the download site, copy the address of the actual download (often behind a \"Download\" button), not the page's address.", detail: detail)
    }

    private func httpError(_ status: Int, retryAfter: String?) -> InstallError {
        let message: String
        var retryable = false
        switch status {
        case 401, 403: message = "The server refused to give out the file (HTTP \(status)). The link may have expired, need a login, or only work in a browser. Get a fresh link and try again."
        case 404, 410: message = "The file is not at that link (HTTP \(status)). The link is wrong or the file was removed."
        case 429: message = "The server says too many downloads were started (HTTP 429). Wait a while and try again."; retryable = true
        case 500...599: message = "The server had a problem (HTTP \(status)). This is on the server's side; try again later."; retryable = true
        case 300...399: message = "The link redirects somewhere that could not be followed (HTTP \(status))."
        default: message = "The server answered with an error (HTTP \(status))."
        }
        return InstallError(.httpError, message, detail: (retryable ? "retry " : "") + "HTTP \(status)" + (retryAfter.map { ", Retry-After \($0)" } ?? ""))
    }

    private func diskError(_ code: Int32) -> InstallError {
        if code == ENOSPC || code == EDQUOT {
            return InstallError(.outOfSpace, "The device ran out of storage while downloading. Free up space and try again.", detail: String(cString: strerror(code)))
        }
        return InstallError(.writeFailed, "Saving the download failed.", detail: String(cString: strerror(code)))
    }
}
