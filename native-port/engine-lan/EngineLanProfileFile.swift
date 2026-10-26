import Foundation
import Darwin
import ZemaLanBackend

/// Explicit isolated profile storage. No default application directory, migration,
/// automatic restore, Story-save access or networking. The caller owns the path.
final class EngineLanProfileFile {
    enum Failure: Error {
        case unsafePath, symlink(String), fileOpen(Int32), unsafeDirectory, unsafeFile, corrupt, unavailable, changed, io, renameLocked, renameRollback
        var message: String {
            switch self {
            case .unsafePath: return "The multiplayer profile path is invalid."
            case .symlink: return "A link was found in the multiplayer profile path."
            case .fileOpen(let code): return "Profile storage could not be opened (error \(code))."
            case .unsafeDirectory: return "The profile folder has unexpected ownership or permissions."
            case .unsafeFile: return "A profile file has unexpected ownership, permissions or size."
            case .corrupt: return "The saved multiplayer profile failed its integrity check."
            case .unavailable: return "The multiplayer profile is not ready."
            case .changed: return "The profile changed outside this session; it was not overwritten."
            case .io: return "A multiplayer profile disk operation failed."
            case .renameLocked: return "Reopen ZGTA V before changing this session’s player name. Your character and progress are preserved."
            case .renameRollback: return "The name change could not be saved or fully rolled back. Multiplayer was not joined; keep the profile and previous snapshot for recovery."
            }
        }
    }
    private let directory: URL
    private let lock = NSLock()
    private var expected: Data?
    private let directorySync: (Int32) -> Int32
    private static let maximum = 8 * 1024 * 1024 + 36

    /// Resolve only the OS-supplied app Documents anchor. Foundation can retain
    /// the system /var alias even after resolvingSymlinksInPath(). Do not resolve
    /// the profile child or its files: their no-symlink checks remain mandatory.
    static func profileDirectory(inAppDocuments documents: URL) throws -> URL {
        guard documents.isFileURL else { throw Failure.unsafePath }
        let canonical = documents.withUnsafeFileSystemRepresentation { path in
            path.flatMap { realpath($0, nil) }
        }
        guard let canonical else { throw Failure.fileOpen(errno) }
        defer { free(canonical) }
        return URL(fileURLWithPath: String(cString: canonical), isDirectory: true)
            .appendingPathComponent("zema-engine-lan-profile-v1", isDirectory: true)
    }

    init(directory: URL, directorySync: @escaping (Int32) -> Int32 = { Darwin.fsync($0) }) throws {
        self.directorySync = directorySync
        guard directory.isFileURL, directory.lastPathComponent.hasPrefix("zema-engine-lan-"),
              !directory.path.split(separator: "/").contains(where: { $0 == "." || $0 == ".." }) else { throw Failure.unsafePath }
        // Foundation standardization changes an existing /private/var path to
        // its /var symlink alias on macOS. Preserve the explicitly checked path.
        self.directory = directory
        try Self.checkComponents(self.directory)
        var info = stat()
        if lstat(self.directory.path, &info) == 0 {
            guard info.st_uid == getuid(), info.st_mode & S_IFMT == S_IFDIR,
                  info.st_mode & 0o777 == 0o700 else { throw Failure.unsafeDirectory }
        } else {
            guard errno == ENOENT, mkdir(self.directory.path, 0o700) == 0 else { throw Failure.io }
        }
    }
    private static func checkComponents(_ path: URL) throws {
        var current = path
        while current.path != "/" {
            var info = stat()
            if lstat(current.path, &info) == 0 {
                guard info.st_mode & S_IFMT != S_IFLNK else { throw Failure.symlink(current.lastPathComponent) }
            } else if errno != ENOENT { throw Failure.io }
            current.deleteLastPathComponent()
        }
    }
    private func read(_ name: String) throws -> Data? {
        try Self.checkComponents(directory)
        var dirInfo = stat()
        guard lstat(directory.path, &dirInfo) == 0, dirInfo.st_uid == getuid(), dirInfo.st_mode & 0o777 == 0o700 else { throw Failure.unsafeDirectory }
        let path = directory.appendingPathComponent(name).path
        let fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK)
        if fd < 0 { if errno == ENOENT { return nil }; throw Failure.fileOpen(errno) }
        defer { close(fd) }
        var info = stat()
        guard fstat(fd, &info) == 0, info.st_mode & S_IFMT == S_IFREG, info.st_uid == getuid(),
              info.st_mode & 0o777 == 0o600, info.st_size >= 0, info.st_size <= Self.maximum else { throw Failure.unsafeFile }
        var bytes = Data(count: Int(info.st_size))
        try bytes.withUnsafeMutableBytes { raw in
            var offset = 0
            while offset < raw.count {
                let n = Darwin.read(fd, raw.baseAddress!.advanced(by: offset), raw.count - offset)
                if n < 0 && errno == EINTR { continue }
                guard n > 0 else { throw Failure.io }; offset += n
            }
        }
        var extra: UInt8 = 0
        guard Darwin.read(fd, &extra, 1) == 0 else { throw Failure.changed }
        return bytes
    }
    /// Load only the exact current snapshot. Corruption never silently selects a
    /// backup or overwrites the file. Import refuses an already modified profile.
    func load() throws -> Bool {
        lock.lock(); defer { lock.unlock() }
        guard let bytes = try read("profile.zemapf") else { expected = nil; return false }
        let accepted = bytes.withUnsafeBytes { ZemaProfileImport($0.bindMemory(to: UInt8.self).baseAddress, $0.count) }
        guard accepted == 1 else { throw Failure.corrupt }
        expected = bytes; return true
    }
    private func atomic(_ bytes: Data, name: String) throws {
        let temp = directory.appendingPathComponent(".write-" + UUID().uuidString)
        let fd = open(temp.path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0o600)
        guard fd >= 0 else { throw Failure.io }
        defer { close(fd); unlink(temp.path) }
        try bytes.withUnsafeBytes { raw in
            var offset = 0
            while offset < raw.count {
                let n = Darwin.write(fd, raw.baseAddress!.advanced(by: offset), raw.count - offset)
                if n < 0 && errno == EINTR { continue }
                guard n > 0 else { throw Failure.io }; offset += n
            }
        }
        guard fsync(fd) == 0, Darwin.rename(temp.path, directory.appendingPathComponent(name).path) == 0 else { throw Failure.io }
    }
    private func syncDirectory() throws {
        let fd = open(directory.path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW)
        guard fd >= 0 else { throw Failure.io }
        defer { close(fd) }
        guard directorySync(fd) == 0 else { throw Failure.io }
    }
    private func snapshot() throws -> Data {
        let needed = Int(ZemaProfileExport(nil, 0))
        guard needed < 0, -needed <= Self.maximum else { throw Failure.unavailable }
        var bytes = Data(count: -needed)
        let written = bytes.withUnsafeMutableBytes { ZemaProfileExport($0.bindMemory(to: UInt8.self).baseAddress, $0.count) }
        guard written == bytes.count else { throw Failure.changed }
        return bytes
    }
    /// Rename only before this process's first admission. No character/stat
    /// record is replaced. Failure restores the old name and exact current
    /// snapshot; an external writer is never overwritten during rollback.
    func rename(to name: String) throws {
        lock.lock(); defer { lock.unlock() }
        var oldBytes = [UInt8](repeating: 0, count: 17)
        let count = oldBytes.withUnsafeMutableBufferPointer { ZemaProfileName($0.baseAddress, $0.count) }
        guard count > 0 else { throw Failure.unavailable }
        let oldName = Array(oldBytes.prefix(Int(count)))
        let requested = Array(name.utf8)
        guard try read("profile.zemapf") == expected else { throw Failure.changed }
        if requested == oldName { return }
        let before = try snapshot()
        guard before == expected else { throw Failure.changed }
        guard requested.withUnsafeBufferPointer({ ZemaProfileRename($0.baseAddress, $0.count) }) == 1 else { throw Failure.renameLocked }
        let candidate: Data
        do { candidate = try snapshot() }
        catch {
            guard oldName.withUnsafeBufferPointer({ ZemaProfileRename($0.baseAddress, $0.count) }) == 1 else { throw Failure.renameRollback }
            throw error
        }
        do { try commitLocked() }
        catch {
            let originalError = error
            guard oldName.withUnsafeBufferPointer({ ZemaProfileRename($0.baseAddress, $0.count) }) == 1,
                  (try? snapshot()) == before else { throw Failure.renameRollback }
            do {
                let actual = try read("profile.zemapf")
                if actual == candidate && expected == candidate {
                    // commit reached the atomic replacement, then directory sync
                    // failed. Restore the old current without replacing its backup.
                    try atomic(before, name: "profile.zemapf"); expected = before
                    try syncDirectory()
                } else if actual != before {
                    // CAS failed or an external writer intervened: do not erase it.
                    throw Failure.changed
                }
            } catch Failure.changed { throw Failure.changed }
            catch { throw Failure.renameRollback }
            throw originalError
        }
    }
    /// Single-writer, compare-before-replace transaction. A known-good previous
    /// snapshot is retained. External changes require review instead of overwrite.
    func commit() throws {
        lock.lock(); defer { lock.unlock() }
        try commitLocked()
    }
    private func commitLocked() throws {
        guard try read("profile.zemapf") == expected else { throw Failure.changed }
        _ = try read("profile.previous.zemapf") // Refuse symlink/nonprivate backup.
        let bytes = try snapshot()
        if bytes == expected { try syncDirectory(); return }
        if let previous = expected { try atomic(previous, name: "profile.previous.zemapf") }
        // Recheck after backup preparation; never discard another writer's file.
        guard try read("profile.zemapf") == expected else { throw Failure.changed }
        try atomic(bytes, name: "profile.zemapf"); expected = bytes
        try syncDirectory()
    }
}
