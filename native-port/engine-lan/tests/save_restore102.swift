import Foundation
import CryptoKit

enum L10n { static func text(_ value: String) -> String { value } }
@main struct RestoreAudit {
    static let fm = FileManager.default
    static func digest(_ data: Data) -> String { SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined() }
    static func entry(_ path: String, _ data: Data) -> SaveStore.Entry {
        SaveStore.Entry(path: path, data: data, sha256: digest(data))
    }
    static func write(_ store: SaveStore, _ path: String, _ data: Data) throws {
        let url = store.root.appendingPathComponent(path)
        try fm.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: url)
    }
    static func snapshot(_ root: URL) throws -> [String: Data] {
        var result: [String: Data] = [:]
        if let scan = fm.enumerator(at: root, includingPropertiesForKeys: [.isRegularFileKey]) {
            for case let url as URL in scan where (try url.resourceValues(forKeys: [.isRegularFileKey])).isRegularFile == true {
                result[String(url.path.dropFirst(root.path.count))] = try Data(contentsOf: url)
            }
        }
        return result
    }
    static func main() throws {
        let base = URL(fileURLWithPath: CommandLine.arguments[1])
        let payload = Data([1, 2, 3])
        func run(_ name: String, existing: [(String, Data)], incoming: [SaveStore.Entry], success: Bool) throws {
            let folder = base.appendingPathComponent(name)
            let store = SaveStore(root: folder.appendingPathComponent("EngineFiles"), backups: folder.appendingPathComponent("Backups"))
            try fm.createDirectory(at: folder, withIntermediateDirectories: true)
            for (path, data) in existing { try write(store, path, data) }
            let backup = base.appendingPathComponent(name + ".zgtasave")
            try JSONEncoder().encode(SaveStore.Archive(schema: 1, created: Date(), entries: incoming)).write(to: backup)
            let before = try snapshot(folder)
            do {
                try store.restore(from: backup)
                precondition(success, "Invalid restore accepted: " + name)
            } catch {
                precondition(!success, "Valid restore rejected: \(name): \(error)")
                let after = try snapshot(folder)
                precondition(after == before, "Rejected restore changed saves/backups: " + name)
                return
            }
            let exported = try store.export()
            let result = try JSONDecoder().decode(SaveStore.Archive.self, from: Data(contentsOf: exported))
            precondition(result.entries.count <= 256)
            precondition(result.entries.reduce(0, { $0 + $1.data.count }) <= SaveStore.totalLimit)
            for item in incoming {
                let restored = try Data(contentsOf: store.root.appendingPathComponent(item.path))
                precondition(restored == item.data)
            }
        }
        let a = "userdata/Documents/A", b = "sandbox/Documents/B"
        let nine = Data(repeating: 7, count: 9 * 1024 * 1024)
        let eight = Data(repeating: 8, count: 8 * 1024 * 1024)
        try run("over-bytes", existing: [(a, nine)], incoming: [entry(b, eight)], success: false)
        try run("exact-bytes", existing: [(a, eight)], incoming: [entry(b, eight)], success: true)
        try run("replace-large", existing: [(a, nine)], incoming: [entry(a, nine)], success: true)
        let existing = (0..<256).map { ("userdata/Documents/file\($0)", Data()) }
        try run("over-count", existing: existing, incoming: [entry(b, payload)], success: false)
        try run("exact-count-replacement", existing: existing, incoming: [entry("userdata/Documents/file0", payload)], success: true)
        try run("case-duplicate", existing: [], incoming: [entry(a, payload), entry("userdata/Documents/a", payload)], success: false)
        try run("unicode-duplicate", existing: [], incoming: [entry("userdata/Documents/é", payload), entry("userdata/Documents/e\u{301}", payload)], success: false)
        for (left, right) in [("σ", "ς"), ("ss", "ß"), ("ff", "ﬀ")] {
            try run("fold-\(UUID().uuidString)", existing: [], incoming: [entry("userdata/Documents/" + left, payload), entry("userdata/Documents/" + right, payload)], success: false)
            try run("fold-existing-\(UUID().uuidString)", existing: [("userdata/Documents/" + left, payload)], incoming: [entry("userdata/Documents/" + right, payload)], success: false)
        }
        try run("case-existing", existing: [(a, payload)], incoming: [entry("userdata/Documents/a", payload)], success: false)
        let recovery = SaveStore(root: base.appendingPathComponent("recovery/EngineFiles"), backups: base.appendingPathComponent("recovery/Backups"))
        for index in 0..<257 { try write(recovery, "userdata/Documents/save\(index)", payload) }
        let listed = try recovery.files(limit: 4096)
        precondition(listed.count == 257)
        let small = try Data(contentsOf: listed[0].url)
        precondition(small == payload)
        do { _ = try recovery.export(); preconditionFailure("Oversized full backup accepted") } catch {}
        precondition(!fm.fileExists(atPath: recovery.backups.path))
        for path in ["userdata/Documents/settings.xml", "userdata/Documents/a\u{85}b", "userdata/Documents/a\u{1}b", "userdata/Documents/../outside", "userdata/Documents/a\\b"] {
            try run("invalid-\(UUID().uuidString)", existing: [(a, payload)], incoming: [entry(path, payload)], success: false)
        }
        print("NATIVE_RESTORE_UNION_LIMITS_ALIAS_REJECTION_AND_UNCHANGED_FAILURE_PASS")
    }
}
