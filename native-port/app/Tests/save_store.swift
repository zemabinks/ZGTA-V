import Foundation
import CryptoKit

@main struct SaveStoreTests {
    static func check(_ condition: Bool) { precondition(condition) }
    static func hash(_ data: Data) -> String { SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined() }
    static func main() throws {
        let catalog = try JSONDecoder().decode([String: [String: String]].self,
            from: Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1])))
        check(L10n.text("Play", language: "en", catalog: catalog) == "Play")
        check(L10n.text("Play", language: "vi", catalog: catalog) == "Play")
        let fm = FileManager.default
        let temp = fm.temporaryDirectory.appendingPathComponent("MugoatSaveTests-" + UUID().uuidString)
        defer { try? fm.removeItem(at: temp) }
        let root = temp.appendingPathComponent("EngineFiles")
        let store = SaveStore(root: root, backups: temp.appendingPathComponent("SaveBackups"))
        let path = "userdata/Documents/Rockstar Games/GTA V/Profiles/12345678/SGTA50000"
        let target = root.appendingPathComponent(path)
        try fm.createDirectory(at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
        let original = Data([0, 1, 2, 255, 0, 128])
        try original.write(to: target)
        let settings = target.deletingLastPathComponent().appendingPathComponent("settings.xml")
        try Data("graphics".utf8).write(to: settings)
        check(try store.files().count == 1)
        check(try store.files()[0].path == path)
        let backup = try store.export()
        try Data("new save".utf8).write(to: target)
        try store.restore(from: backup)
        check(try Data(contentsOf: target) == original)
        check(try Data(contentsOf: settings) == Data("graphics".utf8))
        check(try fm.contentsOfDirectory(at: store.backups, includingPropertiesForKeys: nil).count == 2)

        let bad = temp.appendingPathComponent("bad.mugoatsave")
        func rejected(_ entries: [SaveStore.Entry], schema: Int = 1) throws {
            try JSONEncoder().encode(SaveStore.Archive(schema: schema, created: Date(), entries: entries)).write(to: bad)
            do { try store.restore(from: bad); assertionFailure("Invalid package was accepted") } catch {}
            check(try Data(contentsOf: target) == original)
        }
        let value = Data("injected".utf8)
        try rejected([.init(path: "userdata/Documents/../../../outside", data: value, sha256: hash(value))])
        try rejected([.init(path: "userdata/Documents/a\\b", data: value, sha256: hash(value))])
        try rejected([.init(path: "sandbox/../userdata/Documents/x", data: value, sha256: hash(value))])
        try rejected([.init(path: path, data: value, sha256: "wrong")])
        try rejected([.init(path: path, data: value, sha256: hash(value)), .init(path: path, data: value, sha256: hash(value))])
        try rejected([], schema: 2)
        try rejected(Array(repeating: .init(path: path, data: value, sha256: hash(value)), count: 257))

        let outside = temp.appendingPathComponent("outside")
        try original.write(to: outside)
        let link = root.appendingPathComponent("userdata/Documents/link")
        try fm.createSymbolicLink(at: link, withDestinationURL: outside)
        try rejected([.init(path: "userdata/Documents/link", data: value, sha256: hash(value))])
        check(try Data(contentsOf: outside) == original)

        // An I/O failure after replacing one file restores that file's old bytes.
        let directory = root.appendingPathComponent("userdata/Documents/blocked")
        try fm.createDirectory(at: directory, withIntermediateDirectories: true)
        try rejected([.init(path: path, data: value, sha256: hash(value)), .init(path: "userdata/Documents/blocked", data: value, sha256: hash(value))])
        print("PASS: binary save round trip, backup before restore, settings exclusion, checksum/schema/duplicate/count validation, traversal and symlink rejection, I/O rollback.")
    }
}
