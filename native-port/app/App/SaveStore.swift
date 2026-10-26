import Foundation
import CryptoKit

/// Backs up files the engine has already saved; it does not invent a GTA save.
struct SaveStore {
    struct Entry: Codable {
        let path: String
        let data: Data
        let sha256: String
    }
    struct Archive: Codable {
        let schema: Int
        let created: Date
        let entries: [Entry]
    }
    struct File {
        let url: URL
        let path: String
        let size: Int
        let modified: Date
    }
    enum Failure: LocalizedError {
        case invalid, empty, changed, tooLarge
        var errorDescription: String? {
            switch self {
            case .invalid: return L10n.text("Invalid backup or unsupported file paths.")
            case .empty: return L10n.text("No save files yet. Save using the phone or a save point in GTA V first.")
            case .changed: return L10n.text("The game is writing a save. Wait for the save icon to disappear, then try again.")
            case .tooLarge: return L10n.text("Save data exceeds 16 MB; export individual files instead.")
            }
        }
    }
    let root: URL
    let backups: URL
    private let manager = FileManager.default
    static let totalLimit = 16 * 1024 * 1024

    private func destination(_ path: String) throws -> URL {
        let parts = path.split(separator: "/", omittingEmptySubsequences: false)
        guard parts.count > 1, parts[1] == "Documents", ["userdata", "sandbox"].contains(String(parts[0])),
              parts.allSatisfy({ !$0.isEmpty && $0 != "." && $0 != ".." }),
              !path.contains("\\"), !path.contains("\0"), path.utf8.count < 1024 else { throw Failure.invalid }
        let base = root.standardizedFileURL.resolvingSymlinksInPath()
        let url = base.appendingPathComponent(path).standardizedFileURL
        guard url.resolvingSymlinksInPath().path.hasPrefix(base.path + "/") else { throw Failure.invalid }
        // Never restore through an existing symbolic link, even within the root.
        var current = base
        for part in parts {
            current.appendPathComponent(String(part))
            if (try? current.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink) == true { throw Failure.invalid }
        }
        return url
    }

    func files() throws -> [File] {
        var result: [File] = []
        for mode in ["userdata", "sandbox"] {
            let folder = try destination(mode + "/Documents")
            guard let scan = manager.enumerator(at: folder, includingPropertiesForKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey, .contentModificationDateKey], options: [.skipsHiddenFiles]) else { continue }
            for case let url as URL in scan {
                let values = try url.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey, .contentModificationDateKey])
                if values.isSymbolicLink == true { scan.skipDescendants(); continue }
                guard values.isRegularFile == true, url.lastPathComponent.lowercased() != "settings.xml" else { continue }
                let basePath = folder.resolvingSymlinksInPath().standardizedFileURL.path
                let canonicalPath = url.resolvingSymlinksInPath().standardizedFileURL.path
                guard canonicalPath.hasPrefix(basePath + "/") else { throw Failure.invalid }
                let path = mode + "/Documents/" + String(canonicalPath.dropFirst(basePath.count + 1))
                _ = try destination(path)
                result.append(File(url: url, path: path, size: values.fileSize ?? 0, modified: values.contentModificationDate ?? .distantPast))
                if result.count > 256 { throw Failure.tooLarge }
            }
        }
        return result.sorted { $0.modified > $1.modified }
    }

    private static func digest(_ data: Data) -> String { SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined() }

    func export() throws -> URL {
        let list = try files()
        guard !list.isEmpty else { throw Failure.empty }
        guard list.allSatisfy({ $0.size >= 0 && $0.size <= Self.totalLimit }), list.reduce(0, { $0 + $1.size }) <= Self.totalLimit else { throw Failure.tooLarge }
        let entries = try list.map { file -> Entry in
            let data = try Data(contentsOf: file.url)
            guard data.count == file.size else { throw Failure.changed }
            return Entry(path: file.path, data: data, sha256: Self.digest(data))
        }
        // Reject a copy that changed while it was being read; do not report an
        // incomplete autosave as a successful backup.
        let after = try files()
        guard Set(after.map(\.path)) == Set(list.map(\.path)) else { throw Failure.changed }
        for entry in entries {
            guard Self.digest(try Data(contentsOf: destination(entry.path))) == entry.sha256 else { throw Failure.changed }
        }
        try manager.createDirectory(at: backups, withIntermediateDirectories: true)
        let formatter = DateFormatter(); formatter.dateFormat = "yyyyMMdd-HHmmss"
        let url = backups.appendingPathComponent("ZGTA V-\(formatter.string(from: Date()))-\(UUID().uuidString.prefix(6)).zgtasave")
        try JSONEncoder().encode(Archive(schema: 1, created: Date(), entries: entries)).write(to: url, options: .atomic)
        return url
    }

    func restore(from source: URL) throws {
        let size = try source.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? Self.totalLimit * 3
        guard size <= Self.totalLimit * 2 else { throw Failure.tooLarge }
        let archive = try JSONDecoder().decode(Archive.self, from: Data(contentsOf: source))
        guard archive.schema == 1, !archive.entries.isEmpty, archive.entries.count <= 256 else { throw Failure.invalid }
        var paths = Set<String>(), total = 0
        for entry in archive.entries {
            guard entry.path.split(separator: "/").count > 2 else { throw Failure.invalid }
            _ = try destination(entry.path)
            guard paths.insert(entry.path).inserted, entry.sha256 == Self.digest(entry.data) else { throw Failure.invalid }
            total += entry.data.count
            guard total <= Self.totalLimit else { throw Failure.tooLarge }
        }
        // Verify the entire package before touching existing saves. Save a
        // rollback copy first, and roll back each replaced file on I/O failure.
        if !(try files()).isEmpty { _ = try export() }
        var originals: [(URL, Data?)] = []
        do {
            for entry in archive.entries {
                let target = try destination(entry.path)
                let old = manager.fileExists(atPath: target.path) ? try Data(contentsOf: target) : nil
                originals.append((target, old))
                try manager.createDirectory(at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
                try entry.data.write(to: target, options: .atomic)
            }
        } catch {
            for (target, old) in originals.reversed() {
                if let old { try? old.write(to: target, options: .atomic) }
                else { try? manager.removeItem(at: target) }
            }
            throw error
        }
    }
}
