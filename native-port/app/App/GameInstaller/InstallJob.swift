import Foundation

/// Box handed to the C read callback.
private final class SourceBox {
    let source: ArchiveByteSource
    var head = Data()
    init(_ source: ArchiveByteSource) { self.source = source }
}

private let readCallback: gi_read_fn = { context, bufferOut in
    let box = Unmanaged<SourceBox>.fromOpaque(context!).takeUnretainedValue()
    guard let (pointer, length) = box.source.nextBlock() else { return -1 }
    if box.head.count < 16 && length > 0 {
        box.head.append(pointer.assumingMemoryBound(to: UInt8.self), count: min(16 - box.head.count, length))
    }
    bufferOut!.pointee = pointer
    return length
}

final class InstallJob {
    private let source: GameInstaller.Source
    private let destination: URL
    private let manifestURL: URL
    private let options: GameInstaller.Options
    private let progressHandler: (GameInstaller.Progress) -> Void
    private var completionHandler: ((Result<GameInstaller.Report, InstallError>) -> Void)?
    private weak var task: InstallTask?
    private var readCoordinator: NSFileCoordinator?

    private let lock = NSLock()
    // --- guarded by lock ---
    private var cancelled = false
    private var phase: GameInstaller.Phase = .checking
    private var extracted: Int64 = 0
    private var filesDone = 0
    private var currentFile: String?
    private var samples: [(Date, Int64)] = []
    private var peakIncrease: Int64 = 0
    // ------------------------

    private var manifest: GameManifest!
    private var byteSource: ArchiveByteSource?
    private var local: LocalFileSource? { byteSource as? LocalFileSource }
    private var remote: RemoteSource? { byteSource as? RemoteSource }
    private var timer: DispatchSourceTimer?
    private var startFootprint: Int64 = 0
    private var partCount = 1
    private var partNames: [String] = []
    private var createdFolders = Set<String>()
    private let started = Date()

    init(source: GameInstaller.Source, destination: URL, manifestURL: URL, options: GameInstaller.Options,
         task: InstallTask, progress: @escaping (GameInstaller.Progress) -> Void,
         completion: @escaping (Result<GameInstaller.Report, InstallError>) -> Void) {
        self.source = source
        self.destination = destination.standardizedFileURL
        self.manifestURL = manifestURL
        self.options = options
        self.task = task
        self.progressHandler = progress
        self.completionHandler = completion
    }

    private func log(_ line: String) { options.log?(line) }

    func start() {
        let thread = Thread { [self] in run() }
        thread.name = "GameInstaller"
        thread.qualityOfService = .userInitiated
        thread.stackSize = 1 << 20
        thread.start()
    }

    func cancel() {
        lock.lock(); cancelled = true; let coordinator = readCoordinator; lock.unlock()
        coordinator?.cancel()
        byteSource?.cancel()
    }

    private var isCancelled: Bool { lock.lock(); defer { lock.unlock() }; return cancelled }

    private var dataFolder: URL { destination.appendingPathComponent("data", isDirectory: true) }
    private var workFolder: URL { destination.appendingPathComponent(".gameinstaller", isDirectory: true) }

    // MARK: Main sequence

    private func run() {
        log("GameInstaller: \(String(cString: gi_libarchive_version()))")
        do {
            manifest = try GameManifest(url: manifestURL)
            log("Game file list: \(manifest.files.count) files, \(formatBytes(manifest.totalBytes))")
            do { try FileManager.default.createDirectory(at: dataFolder, withIntermediateDirectories: true) } catch {
                throw InstallError(.writeFailed, "The game folder could not be created.", detail: error.localizedDescription)
            }
            let report = try withCoordinatedSource { readableSource -> GameInstaller.Report in
                try prepareSource(readableSource)
                try checkSpace()
                if isCancelled { throw InstallError(.cancelled, "The install was cancelled.") }
                startTimer()
                set(phase: byteSource is RemoteSource ? .downloading : .unpacking)
                remote?.start()
                let (prefix, skipped, unsafe, format) = try extract()
                byteSource?.finish(success: true)
                set(phase: .verifying)
                try verify()
                if options.writeManifest { writeManifestCopy() }
                try? FileManager.default.removeItem(at: workFolder)
                sampleDisk()
                stopTimer()
                set(phase: .finished)
                let stats = remote?.stats
                lock.lock()
                let report = GameInstaller.Report(
                    dataFolder: dataFolder, filesWritten: filesDone, bytesWritten: extracted,
                    duration: Date().timeIntervalSince(started), archivePrefix: prefix, skippedEntries: skipped,
                    unsafeEntries: unsafe, peakPendingBytes: stats?.peak ?? 0, peakDiskIncrease: peakIncrease,
                    downloadedBytes: stats?.downloaded ?? (local?.bytesConsumed ?? 0), retries: stats?.retries ?? 0, format: format,
                    toleratedSizeMismatches: toleratedMismatches)
                lock.unlock()
                log("Install finished: \(report.filesWritten) files, \(formatBytes(report.bytesWritten)) in \(String(format: "%.0f", report.duration)) s; peak pending \(formatBytes(report.peakPendingBytes)), peak disk increase \(formatBytes(report.peakDiskIncrease)), retries \(report.retries)")
                emitProgress()
                return report
            }
            finish(.success(report))
        } catch let error as InstallError {
            var error = error
            if isCancelled { error = InstallError(.cancelled, "The install was cancelled.") }
            byteSource?.cancel()
            byteSource?.finish(success: false)
            try? FileManager.default.removeItem(at: workFolder)
            stopTimer()
            log("Install failed: \(error)")
            finish(.failure(error))
        } catch {
            stopTimer()
            finish(.failure(InstallError(.writeFailed, "The install failed: \(error.localizedDescription)")))
        }
    }

    private func finish(_ result: Result<GameInstaller.Report, InstallError>) {
        guard let completion = completionHandler else { return }
        completionHandler = nil
        options.callbackQueue.async { completion(result); self.task?.job = nil }
    }

    /// Keep the actual content reads inside coordinated accessors. Batch
    /// preparation alone is not a content-read grant. Each provider may also
    /// return a different URL, which must be the one the byte reader opens.
    private func withCoordinatedSource<T>(_ read: (GameInstaller.Source) throws -> T) throws -> T {
        guard !options.allowModifyingSource else { return try read(source) }
        let parts: [URL]
        switch source {
        case let .file(file): parts = try ArchiveParts.resolve(file)
        case let .files(files): parts = files
        case .url, .urls: return try read(source)
        }
        guard !parts.isEmpty else { throw InstallError(.sourceUnreadable, "No archive file was given.") }
        let coordinator = NSFileCoordinator(filePresenter: nil)
        lock.lock(); readCoordinator = coordinator; lock.unlock()
        defer { lock.lock(); readCoordinator = nil; lock.unlock() }
        var preparationError: NSError?
        var readError: Error?
        var value: T?
        coordinator.prepare(forReadingItemsAt: parts, options: [],
                            writingItemsAt: [], options: [], error: &preparationError) { finish in
            // The iOS SDK isolates this imported completion block to the main actor.
            // Queue it before the main-queue result callback, after all content reads end.
            defer { DispatchQueue.main.async { finish() } }
            func coordinatePart(_ index: Int, _ readable: [URL]) {
                if isCancelled { readError = InstallError(.cancelled, "The install was cancelled."); return }
                if index == parts.count {
                    log("Coordinated archive read: \(parts.count) part(s); source retained")
                    do { value = try read(.files(readable)) } catch { readError = error }
                    return
                }
                var error: NSError?
                coordinator.coordinate(readingItemAt: parts[index], options: .withoutChanges, error: &error) { url in
                    let scoped = url.startAccessingSecurityScopedResource()
                    defer { if scoped { url.stopAccessingSecurityScopedResource() } }
                    coordinatePart(index + 1, readable + [url])
                }
                if let error, readError == nil { readError = error }
            }
            coordinatePart(0, [])
        }
        if let error = readError ?? preparationError {
            if let install = error as? InstallError { throw install }
            let system = error as NSError
            throw InstallError(.sourceUnreadable,
                "Files could not provide the archive for reading. Choose its containing folder again, or choose the archive directly in Files. Your archive and existing game files have been kept.",
                files: parts.map(\.lastPathComponent), detail: "File coordination: \(system.domain) \(system.code): \(system.localizedDescription)")
        }
        guard let value else {
            throw InstallError(.sourceUnreadable, "Files did not grant access to the archive. Choose its containing folder again, or choose the archive directly in Files.")
        }
        return value
    }

    private func prepareSource(_ readableSource: GameInstaller.Source) throws {
        switch readableSource {
        case .url(let url): try makeRemote([url])
        case .urls(let urls): try makeRemote(urls)
        case .file(let file): try makeLocal(ArchiveParts.resolve(file))
        case .files(let files): try makeLocal(files)
        }
    }

    private func makeRemote(_ urls: [URL]) throws {
        guard !urls.isEmpty else { throw InstallError(.sourceUnreadable, "No download link was given.") }
        for url in urls where !["http", "https"].contains(url.scheme?.lowercased() ?? "") {
            throw InstallError(.httpError, "The link must start with http:// or https:// (got \"\(url.absoluteString)\").")
        }
        partCount = urls.count
        partNames = urls.map(\.lastPathComponent)
        byteSource = try RemoteSource(urls: urls, workFolder: workFolder, options: options, log: { [weak self] in self?.log($0) })
    }

    private func makeLocal(_ parts: [URL]) throws {
        guard !parts.isEmpty else { throw InstallError(.sourceUnreadable, "No archive file was given.") }
        partCount = parts.count
        partNames = parts.map(\.lastPathComponent)
        if parts.count > 1 { log("Multi-part archive: \(partNames.joined(separator: ", "))") }
        let source = try LocalFileSource(parts: parts, modify: options.allowModifyingSource, log: { [weak self] in self?.log($0) })
        byteSource = source
        startFootprint = source.allocatedBytes()
    }

    // MARK: Free space

    private func checkSpace() throws {
        set(phase: .checking)
        // Game files already there get replaced, so they need no extra room.
        var existing: Int64 = 0
        for file in manifest.files {
            var st = stat()
            if stat(dataFolder.appendingPathComponent(file.path).path, &st) == 0 { existing += Int64(st.st_blocks) * 512 }
        }
        let game = max(0, manifest.totalBytes - existing)
        var needed: Int64
        var how: String
        if byteSource is RemoteSource {
            needed = game + options.maxPendingBytes
            how = "the game (\(formatBytes(game))) plus up to \(formatBytes(options.maxPendingBytes)) of download buffer"
        } else if let local, local.modify, sameVolume(local.parts[0], destination) {
            needed = max(0, game - local.totalBytes) + (256 << 20)
            how = "the game minus the archive it replaces as it unpacks (\(formatBytes(max(0, game - local.totalBytes))))"
        } else {
            needed = game
            how = "the game (\(formatBytes(game))) next to the archive"
        }
        needed += options.spaceMargin
        let free = options.freeSpaceOverride ?? freeSpace(at: destination)
        log("Space check: need \(formatBytes(needed)) (\(how), plus \(formatBytes(options.spaceMargin)) to spare); free \(formatBytes(free))")
        if free < needed {
            throw InstallError(.notEnoughSpace, "Not enough free storage. Installing needs \(formatBytes(needed)) free (\(how), plus \(formatBytes(options.spaceMargin)) to spare), but only \(formatBytes(free)) is free. Free up \(formatBytes(needed - free)) more and try again.",
                               detail: "need \(needed), free \(free)")
        }
    }

    private func freeSpace(at url: URL) -> Int64 {
        let values = try? url.resourceValues(forKeys: [.volumeAvailableCapacityForImportantUsageKey, .volumeAvailableCapacityKey])
        if let important = values?.volumeAvailableCapacityForImportantUsage, important > 0 { return important }
        if let plain = values?.volumeAvailableCapacity { return Int64(plain) }
        var sfs = statfs()
        if statfs(url.path, &sfs) == 0 { return Int64(sfs.f_bavail) * Int64(sfs.f_bsize) }
        return 0
    }

    private func sameVolume(_ a: URL, _ b: URL) -> Bool {
        var sa = stat(), sb = stat()
        return stat(a.path, &sa) == 0 && stat(b.path, &sb) == 0 && sa.st_dev == sb.st_dev
    }

    // MARK: Unpacking

    private func extract() throws -> (prefix: String, skipped: Int, unsafe: [String], format: String) {
        guard let byteSource else { throw InstallError(.sourceUnreadable, "No archive.") }
        let box = SourceBox(byteSource)
        let unmanaged = Unmanaged.passRetained(box)
        defer { unmanaged.release() }
        guard let reader = gi_reader_open(readCallback, unmanaged.toOpaque()) else {
            throw InstallError(.writeFailed, "Out of memory.")
        }
        defer { gi_reader_close(reader) }

        var matcher = GameRootMatcher(manifest: manifest)
        var skipped = 0
        var unsafe: [String] = []
        var first = true
        var format = ""
        var sawEncrypted = false
        let buffers = WriteState()
        while true {
            if isCancelled { throw InstallError(.cancelled, "The install was cancelled.") }
            var info = gi_entry_info()
            let r = gi_reader_next(reader, &info)
            if r == GI_EOF { break }
            let path = info.path.map { String(cString: $0) } ?? ""
            if first { format = gi_reader_format_name(reader).map { String(cString: $0) } ?? "" }
            if r == GI_FATAL || r == GI_FAILED {
                if info.encrypted != 0 { throw passwordError() }
                throw archiveError(reader, box: box, file: nil, firstHeader: first)
            }
            if first { log("Archive format: \(format)"); first = false }
            if info.encrypted != 0 { sawEncrypted = true }
            switch info.kind {
            case Int32(GI_ENTRY_DIRECTORY): continue
            case Int32(GI_ENTRY_FILE): break
            default:
                // Links and devices are never created.
                if case .file = matcher.match(path) { unsafe.append(path) } else { skipped += 1 }
                if info.kind == Int32(GI_ENTRY_SYMLINK) && unsafe.last != path { unsafe.append(path) }
                continue
            }
            switch matcher.match(path) {
            case .unsafe:
                unsafe.append(path)
                log("Refused unsafe path in archive: \(path)")
            case .notGame:
                skipped += 1
            case .file(let index):
                if filesDone == 0 { log("Game found in the archive at \"\(matcher.prefixString)\"") }
                if info.encrypted != 0 { throw passwordError() }
                try write(entry: index, declaredSize: info.size_known != 0 ? info.size : -1, reader: reader, box: box, state: buffers)
            }
        }
        if first {
            // Not even one entry: empty or not an archive.
            throw archiveError(reader, box: box, file: nil, firstHeader: true)
        }
        lock.lock(); let done = filesDone; lock.unlock()
        if done == 0 {
            if sawEncrypted || gi_reader_has_encrypted_entries(reader) > 0 { throw passwordError() }
            throw InstallError(.noGameFiles, "None of the files in this archive belong to the game. It is probably a different archive (or a different game version).", detail: "skipped \(skipped) entries")
        }
        log("Unpacked \(done) game files; skipped \(skipped) other entries; refused \(unsafe.count) unsafe entries")
        return (matcher.prefixString, skipped, unsafe, format)
    }

    private final class WriteState {}

    private func write(entry index: Int, declaredSize: Int64, reader: OpaquePointer, box: SourceBox, state: WriteState) throws {
        let file = manifest.files[index]
        let target = dataFolder.appendingPathComponent(file.path)
        let folder = target.deletingLastPathComponent().path
        if !createdFolders.contains(folder) {
            do { try FileManager.default.createDirectory(atPath: folder, withIntermediateDirectories: true) } catch {
                throw diskError(errno, file: file.path)
            }
            createdFolders.insert(folder)
        }
        lock.lock(); currentFile = file.path; lock.unlock()
        let temp = target.path + ".gipart"
        let fd = open(temp, O_WRONLY | O_CREAT | O_TRUNC | O_NOFOLLOW, 0o644)
        guard fd >= 0 else { throw diskError(errno, file: file.path) }
        var ok = false
        defer { if !ok { close(fd); unlink(temp) } }
        var end: Int64 = 0
        while true {
            var buffer: UnsafeRawPointer?
            var size = 0
            var offset: Int64 = 0
            let r = gi_reader_data(reader, &buffer, &size, &offset)
            if r == GI_EOF { break }
            if r != GI_OK { throw archiveError(reader, box: box, file: file.path, firstHeader: false) }
            if isCancelled { throw InstallError(.cancelled, "The install was cancelled.") }
            guard size > 0, var p = buffer else { continue }
            var left = size, at = offset
            while left > 0 {
                let n = pwrite(fd, p, left, off_t(at))
                if n < 0 { if errno == EINTR { continue }; throw diskError(errno, file: file.path) }
                p += n; left -= n; at += Int64(n)
            }
            end = max(end, offset + Int64(size))
            lock.lock(); extracted += Int64(size); lock.unlock()
        }
        // Sparse tails (tar) end in a hole: extend to the size the ARCHIVE declares (never to the
        // manifest size, which would hide a short or wrong file from verification).
        if declaredSize > end, ftruncate(fd, off_t(declaredSize)) != 0 { throw diskError(errno, file: file.path) }
        if close(fd) != 0 { ok = true; unlink(temp); throw diskError(errno, file: file.path) }
        ok = true
        if rename(temp, target.path) != 0 { let e = errno; unlink(temp); throw diskError(e, file: file.path) }
        lock.lock(); filesDone += 1; currentFile = nil; lock.unlock()
    }

    // MARK: Errors

    private func passwordError() -> InstallError {
        InstallError(.passwordProtected, "The archive is password-protected. The installer can't open protected archives: unpack it on a computer with the password and re-pack it without one (zip or rar).")
    }

    private func diskError(_ code: Int32, file: String) -> InstallError {
        if code == ENOSPC || code == EDQUOT {
            return InstallError(.outOfSpace, "The device ran out of storage while unpacking \(file). Free up space and try again; files unpacked so far are kept.", files: [file], detail: String(cString: strerror(code)))
        }
        return InstallError(.writeFailed, "Writing \(file) failed: \(String(cString: strerror(code))).", files: [file], detail: String(cString: strerror(code)))
    }

    private func archiveError(_ reader: OpaquePointer, box: SourceBox, file: String?, firstHeader: Bool) -> InstallError {
        if isCancelled { return InstallError(.cancelled, "The install was cancelled.") }
        if let failure = box.source.failure { return failure }
        let message = gi_reader_error(reader).map { String(cString: $0) } ?? "unknown error"
        let code = gi_reader_errno(reader)
        let lower = message.lowercased()
        if code == ENOSPC { return diskError(ENOSPC, file: file ?? "the game") }
        if lower.contains("encrypt") || lower.contains("passphrase") || lower.contains("password") { return passwordError() }
        if firstHeader && lower.contains("unrecognized archive format") || (firstHeader && box.head.isEmpty) {
            let head = [UInt8](box.head)
            if head.starts(with: [0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C]) {
                return InstallError(.unsupported, "7-Zip (.7z) archives are not supported. Re-pack the game as a zip or rar.", detail: message)
            }
            if box.head.isEmpty {
                return InstallError(.notAnArchive, "The file is empty.", detail: message)
            }
            if let text = String(data: box.head, encoding: .utf8)?.lowercased(), text.contains("<!doctype") || text.contains("<html") {
                return InstallError(.webPageNotFile, "This is a web page, not the game archive.", detail: message)
            }
            return InstallError(.notAnArchive, "This file is not an archive the installer can open. Supported: zip, rar, rar5, tar.", detail: message)
        }
        let multi = partCount > 1 || partNames.first.map { $0.range(of: #"\.part\d+\.rar$|\.r\d\d$|\.z\d\d$|\.\d{3}$"#, options: [.regularExpression, .caseInsensitive]) != nil } ?? false
        if lower.contains("crc") || lower.contains("checksum") {
            if let file {
                return InstallError(.corrupted, "The archive is damaged: \(file) failed its integrity check (CRC error). Download the archive again.", files: [file], detail: message)
            }
            return InstallError(.corrupted, "The archive is damaged (an index entry failed its integrity check). Download the archive again.", detail: message)
        }
        if lower.contains("multi-volume") || lower.contains("volume") && !lower.contains("invalid") {
            return InstallError(.missingPart, "A part of the multi-part archive is missing or out of order. Make sure all parts are there and come from the same set.", detail: message)
        }
        if lower.contains("truncat") || lower.contains("premature") || lower.contains("end of") || lower.contains("eof") {
            if multi {
                return InstallError(.missingPart, "The archive ends after \"\(partNames.last ?? "the last part")\" but continues in another part. A part of the multi-part set is missing: add the next part and try again.", files: file.map { [$0] } ?? [], detail: message)
            }
            return InstallError(.truncated, "The archive ends too early\(file.map { " (in \($0))" } ?? ""): it is incomplete. The download probably didn't finish, or the file was cut short. Get the archive again.", files: file.map { [$0] } ?? [], detail: message)
        }
        if lower.contains("unsupported") || lower.contains("not supported") {
            return InstallError(.unsupported, "The archive uses a compression method the installer can't unpack (\(message)). Re-pack it as an ordinary zip or rar.", detail: message)
        }
        return InstallError(.corrupted, "The archive could not be read\(file.map { " at \($0)" } ?? ""): it seems damaged. Download it again.", files: file.map { [$0] } ?? [], detail: message)
    }

    // MARK: Verify

    private var toleratedMismatches: [String] = []

    private func verify() throws {
        var missing: [String] = [], wrongSize: [String] = []
        for file in manifest.files {
            var st = stat()
            if lstat(dataFolder.appendingPathComponent(file.path).path, &st) != 0 || (st.st_mode & S_IFMT) != S_IFREG { missing.append(file.path) }
            else if Int64(st.st_size) != file.size {
                if options.toleratedSizeMismatches.contains(file.path) {
                    toleratedMismatches.append(file.path)
                    log("size differs but tolerated: \(file.path) (\(st.st_size), manifest \(file.size))")
                } else { wrongSize.append(file.path) }
            }
        }
        log("Verified \(manifest.files.count) files: \(missing.count) missing, \(wrongSize.count) wrong size")
        guard missing.isEmpty && wrongSize.isEmpty else {
            var parts: [String] = []
            if !missing.isEmpty { parts.append("\(missing.count) game file\(missing.count == 1 ? " is" : "s are") missing (e.g. \(missing.prefix(3).joined(separator: ", ")))") }
            if !wrongSize.isEmpty { parts.append("\(wrongSize.count) game file\(wrongSize.count == 1 ? " has" : "s have") the wrong size (e.g. \(wrongSize.prefix(3).joined(separator: ", ")))") }
            for name in missing.prefix(50) { log("missing: \(name)") }
            for name in wrongSize.prefix(50) { log("wrong size: \(name)") }
            throw InstallError(.verificationFailed, "After unpacking, \(parts.joined(separator: " and ")). The archive is incomplete or holds a different game version.",
                               files: missing + wrongSize, detail: "missing \(missing.count), wrong size \(wrongSize.count)")
        }
    }

    private func writeManifestCopy() {
        let target = dataFolder.appendingPathComponent("manifest.json")
        try? FileManager.default.removeItem(at: target)
        try? FileManager.default.copyItem(at: manifestURL, to: target)
    }

    // MARK: Progress

    private func set(phase: GameInstaller.Phase) { lock.lock(); self.phase = phase; lock.unlock() }

    private func startTimer() {
        let timer = DispatchSource.makeTimerSource(queue: DispatchQueue.global(qos: .utility))
        timer.schedule(deadline: .now() + options.progressInterval, repeating: options.progressInterval)
        timer.setEventHandler { [weak self] in self?.sampleDisk(); self?.emitProgress() }
        timer.resume()
        self.timer = timer
    }

    private func stopTimer() { timer?.cancel(); timer = nil }

    /// Disk use of the install now, compared with the start.
    private func sampleDisk() {
        lock.lock(); let written = extracted; lock.unlock()
        var footprint = written
        if let local, local.modify { footprint += local.allocatedBytes() }
        else if let local { footprint += local.totalBytes }
        if let remote { footprint += remote.pendingBytes }
        let increase = footprint - (local != nil ? startFootprint : 0)
        lock.lock(); peakIncrease = max(peakIncrease, increase); lock.unlock()
    }

    private func emitProgress() {
        let now = Date()
        let downloaded: Int64, total: Int64?, pending: Int64, retries: Int
        if let remote { let s = remote.stats; downloaded = s.downloaded; total = s.total; pending = s.pending; retries = s.retries }
        else { downloaded = byteSource?.bytesConsumed ?? 0; total = local?.totalBytes; pending = 0; retries = 0 }
        lock.lock()
        samples.append((now, extracted))
        while let first = samples.first, now.timeIntervalSince(first.0) > 10 { samples.removeFirst() }
        var rate: Double?
        if let first = samples.first, let last = samples.last, last.0.timeIntervalSince(first.0) >= 2 {
            rate = Double(last.1 - first.1) / last.0.timeIntervalSince(first.0)
        }
        let progress = GameInstaller.Progress(
            phase: phase, downloadedBytes: downloaded, downloadTotalBytes: total, extractedBytes: extracted,
            totalBytes: manifest?.totalBytes ?? 0, filesDone: filesDone, filesTotal: manifest?.files.count ?? 0,
            currentFile: currentFile, bytesPerSecond: rate,
            secondsRemaining: rate.flatMap { $0 > 1000 ? Double(max(0, (manifest?.totalBytes ?? 0) - extracted)) / $0 : nil },
            pendingBytes: pending, retries: retries)
        lock.unlock()
        let handler = progressHandler
        options.callbackQueue.async { handler(progress) }
    }
}
