import Foundation
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

/// Add one compatible Story save. Existing manual slots and autosave are never
/// replaced. Version/title validation is not a converter for newer game builds.
enum StorySave {
    private static let importLock = NSLock()
    static let minimum = 64 * 1024, maximum = 8 * 1024 * 1024
    static let components = ["userdata", "Documents", "Rockstar Games", "GTA V", "Default"]
    struct Imported { let title: String; let slot: Int; let path: String }
    enum Failure: LocalizedError {
        case invalid, full, storage(String)
        var errorDescription: String? {
            switch self {
            case .invalid: return "Choose a compatible GTA V Story save (SGTA5…), between 64 KB and 8 MB."
            case .full: return "All 15 manual save slots are occupied. Existing saves and autosave were kept."
            case .storage(let detail): return "The Story save could not be added. Existing saves were kept. " + detail
            }
        }
    }
    static func title(_ data: Data) throws -> String {
        guard data.count >= minimum && data.count <= maximum else { throw Failure.invalid }
        return try data.withUnsafeBytes { raw -> String in
            let bytes = raw.bindMemory(to: UInt8.self)
            guard Array(bytes.prefix(4)) == [0, 0, 0, 1] else { throw Failure.invalid }
            var units: [UInt16] = [], terminated = false
            for i in stride(from: 4, to: min(data.count - 1, 516), by: 2) {
                let value = UInt16(bytes[i]) | UInt16(bytes[i + 1]) << 8
                if value == 0 { terminated = true; break }
                units.append(value)
            }
            if units.first == 0xfeff { units.removeFirst() }
            let rawTitle = String(decoding: units, as: UTF16.self)
            guard terminated, !rawTitle.contains("\u{FFFD}"), !rawTitle.unicodeScalars.contains(where: { $0.value < 32 || (127...159).contains($0.value) }) else { throw Failure.invalid }
            let result = rawTitle.trimmingCharacters(in: .whitespacesAndNewlines)
            guard result.unicodeScalars.count >= 3 else { throw Failure.invalid }
            return result
        }
    }
    static func candidates(filename: String, occupied: Set<String>) -> [Int] {
        let names = Set(occupied.map { $0.lowercased() })
        var order = Array(0..<15)
        let name = filename.uppercased()
        if name.range(of: #"^SGTA500(?:0[0-9]|1[0-4])(?:\.BAK)?$"#, options: .regularExpression) != nil,
           let own = Int(String(name.prefix(9).suffix(2))) {
            order.removeAll { $0 == own }; order.insert(own, at: 0)
        }
        return order.filter { slot in
            let name = String(format: "sgta500%02d", slot)
            return !names.contains(name) && !names.contains(name + ".bak")
        }
    }
    typealias Writer = (Int32, UnsafeRawPointer, Int) -> Int
    typealias Sync = (Int32) -> Int32
    static func systemWrite(_ fd: Int32, _ pointer: UnsafeRawPointer, _ count: Int) -> Int {
        #if canImport(Darwin)
        return Darwin.write(fd, pointer, count)
        #else
        return Glibc.write(fd, pointer, count)
        #endif
    }
    static func systemSync(_ fd: Int32) -> Int32 { fsync(fd) }
    private static func storageError() -> Failure { .storage(String(cString: strerror(errno))) }

    static func read(_ url: URL) throws -> Data {
        let fd = open(url.path, O_RDONLY | O_NONBLOCK | O_CLOEXEC)
        guard fd >= 0 else { throw storageError() }
        let handle = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
        defer { try? handle.close() }
        var before = stat()
        guard fstat(handle.fileDescriptor, &before) == 0,
              (before.st_mode & S_IFMT) == S_IFREG,
              before.st_size >= minimum, before.st_size <= maximum else { throw Failure.invalid }
        var bytes = Data()
        while bytes.count <= maximum {
            guard let chunk = try handle.read(upToCount: min(65536, maximum + 1 - bytes.count)), !chunk.isEmpty else { break }
            bytes.append(chunk)
        }
        var after = stat()
        guard fstat(handle.fileDescriptor, &after) == 0, before.st_size == after.st_size,
              bytes.count == before.st_size else { throw Failure.storage("The selected file changed while it was being read.") }
        #if canImport(Darwin)
        guard before.st_mtimespec.tv_sec == after.st_mtimespec.tv_sec && before.st_mtimespec.tv_nsec == after.st_mtimespec.tv_nsec else { throw Failure.storage("The selected file changed while it was being read.") }
        #else
        guard before.st_mtim.tv_sec == after.st_mtim.tv_sec && before.st_mtim.tv_nsec == after.st_mtim.tv_nsec else { throw Failure.storage("The selected file changed while it was being read.") }
        #endif
        _ = try title(bytes)
        return bytes
    }

    static func install(_ data: Data, filename: String, root: URL,
                        writer: Writer = systemWrite, sync: Sync = systemSync) throws -> Imported {
        let label = try title(data)
        importLock.lock()
        defer { importLock.unlock() }
        // Anchor every child lookup to an already opened directory. A changed
        // path or linked child must not redirect writes outside this save tree.
        let canonical = root.standardizedFileURL.resolvingSymlinksInPath()
        var directory = open(canonical.path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
        guard directory >= 0 else { throw storageError() }
        defer { close(directory) }
        for part in components {
            var next = openat(directory, part, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
            if next < 0 && errno == ENOENT {
                guard mkdirat(directory, part, 0o700) == 0 || errno == EEXIST else { throw storageError() }
                next = openat(directory, part, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
            }
            guard next >= 0 else { throw storageError() }
            close(directory); directory = next
        }
        let duplicate = dup(directory)
        guard duplicate >= 0 else { throw storageError() }
        guard let stream = fdopendir(duplicate) else { close(duplicate); throw storageError() }
        var occupied = Set<String>()
        errno = 0
        while let entry = readdir(stream) {
            let name = withUnsafePointer(to: &entry.pointee.d_name) { pointer in
                pointer.withMemoryRebound(to: CChar.self, capacity: 256) { String(cString: $0) }
            }
            occupied.insert(name)
            if occupied.count > 4096 { closedir(stream); throw Failure.storage("The save folder contains too many entries.") }
            errno = 0
        }
        let scanError = errno
        closedir(stream)
        guard scanError == 0 else { errno = scanError; throw storageError() }
        for slot in candidates(filename: filename, occupied: occupied) {
            let name = String(format: "SGTA500%02d", slot)
            var file = openat(directory, name, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
            if file < 0 && errno == EEXIST { continue }
            guard file >= 0 else { throw storageError() }
            var original = stat()
            var stated: Int32
            repeat { stated = fstat(file, &original) } while stated < 0 && errno == EINTR
            guard stated == 0 else { let error = storageError(); close(file); throw error }
            do {
                try data.withUnsafeBytes { raw in
                    guard let start = raw.baseAddress else { throw Failure.invalid }
                    var offset = 0
                    while offset < raw.count {
                        let count = writer(file, start.advanced(by: offset), raw.count - offset)
                        if count < 0 && errno == EINTR { continue }
                        if count < 0 { throw storageError() }
                        guard count > 0 && count <= raw.count - offset else { throw Failure.storage("The save write was incomplete.") }
                        offset += count
                    }
                }
                guard sync(file) == 0 else { throw storageError() }
                var current = stat()
                guard fstatat(directory, name, &current, AT_SYMLINK_NOFOLLOW) == 0,
                      current.st_dev == original.st_dev, current.st_ino == original.st_ino,
                      (current.st_mode & S_IFMT) == S_IFREG else { throw Failure.storage("The destination changed during the import.") }
                let result = close(file); file = -1
                guard result == 0 && sync(directory) == 0 else { throw storageError() }
                return Imported(title: label, slot: slot + 1, path: (components + [name]).joined(separator: "/"))
            } catch {
                // Remove only the incomplete file this call created. A file
                // replaced by another writer is never unlinked through its name.
                var current = stat()
                if fstatat(directory, name, &current, AT_SYMLINK_NOFOLLOW) == 0,
                   current.st_dev == original.st_dev, current.st_ino == original.st_ino {
                    _ = unlinkat(directory, name, 0); _ = systemSync(directory)
                }
                if file >= 0 { close(file) }
                throw error
            }
        }
        throw Failure.full
    }
}
