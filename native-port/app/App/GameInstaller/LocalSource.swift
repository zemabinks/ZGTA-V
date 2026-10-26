import Foundation

/// Feeds archive bytes to libarchive, one block at a time, strictly front to back.
protocol ArchiveByteSource: AnyObject {
    /// Returns the next block (length 0 = end of archive), or nil on failure/cancel.
    /// The block stays valid until the next call.
    func nextBlock() -> (UnsafeRawPointer, Int)?
    /// Why nextBlock returned nil.
    var failure: InstallError? { get }
    /// Archive bytes handed to libarchive so far.
    var bytesConsumed: Int64 { get }
    /// Wakes up a waiting nextBlock and makes it fail.
    func cancel()
    /// Called once the archive was fully unpacked.
    func finish(success: Bool)
}

/// Reads one local archive or the parts of a multi-part set as one stream. When allowed, frees
/// what was read (F_PUNCHHOLE) and deletes finished parts, so disk use stays flat.
final class LocalFileSource: ArchiveByteSource {
    let parts: [URL]
    let modify: Bool
    let log: (String) -> Void
    private let blockSize = 4 << 20
    private let punchEvery: Int64 = 64 << 20
    private let buffer: UnsafeMutableRawPointer
    private var index = -1
    private var fd: Int32 = -1
    private var offsetInPart: Int64 = 0
    private var punchedTo: Int64 = 0
    private var fsBlock: Int64 = 4096
    private var punchWorks = true
    private let lock = NSLock()
    private var cancelled = false
    private var consumed: Int64 = 0
    private(set) var failure: InstallError?
    /// Sum of the parts' sizes.
    let totalBytes: Int64
    /// Bytes freed by punching holes / deleting parts.
    private(set) var freedBytes: Int64 = 0

    init(parts: [URL], modify: Bool, log: @escaping (String) -> Void) throws {
        self.parts = parts
        self.modify = modify
        self.log = log
        var total: Int64 = 0
        for part in parts {
            var st = stat()
            guard stat(part.path, &st) == 0 else {
                throw Self.readError(part, code: errno, operation: "stat")
            }
            total += Int64(st.st_size)
        }
        totalBytes = total
        buffer = UnsafeMutableRawPointer.allocate(byteCount: blockSize, alignment: 16)
    }

    deinit {
        if fd >= 0 { close(fd) }
        buffer.deallocate()
    }

    var bytesConsumed: Int64 { lock.lock(); defer { lock.unlock() }; return consumed }

    func cancel() { lock.lock(); cancelled = true; lock.unlock() }

    /// Disk space the not-yet-freed parts of the archive still take (st_blocks).
    func allocatedBytes() -> Int64 {
        var total: Int64 = 0
        for (i, part) in parts.enumerated() where i >= max(index, 0) {
            var st = stat()
            if stat(part.path, &st) == 0 { total += Int64(st.st_blocks) * 512 }
        }
        return total
    }

    func nextBlock() -> (UnsafeRawPointer, Int)? {
        lock.lock(); let stop = cancelled; lock.unlock()
        if stop { failure = InstallError(.cancelled, "The install was cancelled."); return nil }
        while true {
            if fd < 0 {
                if !openNext() { return failure == nil ? (UnsafeRawPointer(buffer), 0) : nil }
            }
            let n = read(fd, buffer, blockSize)
            if n < 0 {
                failure = Self.readError(parts[index], code: errno, operation: "read")
                return nil
            }
            if n == 0 { closeCurrent(finished: true); continue }
            offsetInPart += Int64(n)
            lock.lock(); consumed += Int64(n); lock.unlock()
            // The bytes are in memory now; libarchive never seeks back, so the disk copy can go.
            if modify && punchWorks && offsetInPart - punchedTo >= punchEvery { punch() }
            return (UnsafeRawPointer(buffer), n)
        }
    }

    private func openNext() -> Bool {
        index += 1
        guard index < parts.count else { return false }
        let path = parts[index].path
        fd = open(path, modify ? O_RDWR : O_RDONLY)
        if fd < 0 && modify { fd = open(path, O_RDONLY); if fd >= 0 { log("Archive part is read-only; it will not be freed as it is read.") } }
        guard fd >= 0 else {
            failure = Self.readError(parts[index], code: errno, operation: "open")
            return false
        }
        var sfs = statfs()
        if fstatfs(fd, &sfs) == 0 { fsBlock = Int64(max(sfs.f_bsize, 512)) }
        offsetInPart = 0
        punchedTo = 0
        if parts.count > 1 { log("Reading part \(index + 1) of \(parts.count): \(parts[index].lastPathComponent)") }
        return true
    }

    private static func readError(_ file: URL, code: Int32, operation: String) -> InstallError {
        let reason: String
        switch code {
        case EPERM, EACCES:
            reason = "Files did not allow access. Choose the containing folder again, or choose this archive directly in Files to grant fresh access."
        case ENOENT, ENOTDIR:
            reason = "The file is no longer available at that location. Choose its current folder or select the archive again in Files."
        default:
            reason = "The system reported: \(String(cString: strerror(code)))."
        }
        return InstallError(.sourceUnreadable,
                            "The archive \"\(file.lastPathComponent)\" could not be read. " + reason,
                            files: [file.lastPathComponent],
                            detail: "\(operation) errno=\(code) (\(String(cString: strerror(code)))) at \(file.path)")
    }

    private func punch() {
        let result = gi_punch_hole(fd, punchedTo, offsetInPart - punchedTo, fsBlock)
        if result == 0 {
            // Rounded down to whole blocks; the remainder is punched next time.
            let end = offsetInPart / fsBlock * fsBlock
            freedBytes += end - punchedTo
            punchedTo = end
        } else {
            punchWorks = false
            log("Freeing the read part of the archive is not supported here (\(String(cString: strerror(result)))); the archive keeps its space until the end.")
        }
    }

    private func closeCurrent(finished: Bool) {
        guard fd >= 0 else { return }
        close(fd)
        fd = -1
        // A finished part of a multi-part set is no longer needed at all.
        if finished && modify && parts.count > 1 && index < parts.count - 1 {
            if unlink(parts[index].path) == 0 {
                freedBytes += offsetInPart - punchedTo
                log("Deleted finished part \(parts[index].lastPathComponent)")
            }
        }
    }

    func finish(success: Bool) {
        if fd >= 0 { close(fd); fd = -1 }
        guard success && modify else { return }
        for part in parts where FileManager.default.fileExists(atPath: part.path) {
            if unlink(part.path) == 0 { log("Deleted the unpacked archive \(part.lastPathComponent)") }
        }
    }
}

/// Finds the parts of a multi-part set from one of its files.
enum ArchiveParts {
    /// Returns all parts in order, or throws `.missingPart` when there is a gap.
    static func resolve(_ file: URL) throws -> [URL] {
        let folder = file.deletingLastPathComponent()
        let name = file.lastPathComponent
        let fm = FileManager.default
        func exists(_ n: String) -> Bool { fm.fileExists(atPath: folder.appendingPathComponent(n).path) }
        func missing(_ n: String, after: String) -> InstallError {
            InstallError(.missingPart, "Part \"\(n)\" of the multi-part archive is missing. Put all parts in the same folder (\"\(after)\" was found) and try again.", files: [n])
        }
        let siblings = (try? fm.contentsOfDirectory(atPath: folder.path)) ?? []

        // x.part1.rar, x.part2.rar ... (also part01 / part001)
        if let m = name.range(of: #"\.part(\d+)\.rar$"#, options: [.regularExpression, .caseInsensitive]) {
            let base = String(name[..<m.lowerBound])
            let digits = name[m].filter(\.isNumber).count
            let pattern = "^" + NSRegularExpression.escapedPattern(for: base) + #"\.part(\d+)\.rar$"#
            let numbers = siblings.compactMap { s -> Int? in
                guard let r = s.range(of: pattern, options: [.regularExpression, .caseInsensitive]) else { return nil }
                return Int(s[r].dropFirst(base.count + 5).dropLast(4))
            }
            let last = numbers.max() ?? 1
            var result: [URL] = []
            for i in 1...last {
                let n = base + ".part" + String(format: "%0\(digits)d", i) + ".rar"
                guard exists(n) else { throw missing(n, after: name) }
                result.append(folder.appendingPathComponent(n))
            }
            return result
        }
        // x.zip.001, x.7z.001 ... (plain byte splits)
        if let m = name.range(of: #"\.(\d{3})$"#, options: .regularExpression) {
            let base = String(name[..<m.lowerBound])
            var result: [URL] = []
            var i = 1
            while true {
                let n = base + "." + String(format: "%03d", i)
                if exists(n) { result.append(folder.appendingPathComponent(n)); i += 1; continue }
                if siblings.contains(where: { s in s.hasPrefix(base + ".") && (Int(s.dropFirst(base.count + 1)) ?? 0) > i }) {
                    throw missing(n, after: name)
                }
                break
            }
            return result
        }
        // Old rar naming: x.rar, x.r00, x.r01 ...
        if name.lowercased().hasSuffix(".rar") {
            let base = String(name.dropLast(4))
            var result = [file]
            var i = 0
            while exists(base + String(format: ".r%02d", i)) || exists(base + String(format: ".R%02d", i)) {
                let n = exists(base + String(format: ".r%02d", i)) ? base + String(format: ".r%02d", i) : base + String(format: ".R%02d", i)
                result.append(folder.appendingPathComponent(n)); i += 1
            }
            return result
        }
        // Split zip: x.z01, x.z02, ..., x.zip (the .zip is the last part).
        if name.lowercased().hasSuffix(".zip") || name.range(of: #"\.z\d{2}$"#, options: [.regularExpression, .caseInsensitive]) != nil {
            let base = String(name.dropLast(4))
            if exists(base + ".z01") {
                var result: [URL] = []
                var i = 1
                while exists(base + String(format: ".z%02d", i)) { result.append(folder.appendingPathComponent(base + String(format: ".z%02d", i))); i += 1 }
                let zip = siblings.first { $0.lowercased() == (base + ".zip").lowercased() }
                guard let zip else { throw missing(base + ".zip", after: name) }
                result.append(folder.appendingPathComponent(zip))
                return result
            }
        }
        return [file]
    }
}
