import Foundation

// Only error-message translation is stubbed; serialization and restore use
// the unmodified SaveStore shipped in the iPhone app.
enum L10n { static func text(_ value: String) -> String { value } }
@main struct SaveTransferFixture {
    static func main() throws {
        let fm = FileManager.default
        let base = URL(fileURLWithPath: CommandLine.arguments[1])
        let store = SaveStore(root: base.appendingPathComponent("EngineFiles"), backups: base.appendingPathComponent("Backups"))
        let suffix = "/Documents/Rockstar Games/GTA V/Profiles/12345678/SGTA50000"
        for mode in ["userdata", "sandbox"] {
            let target = store.root.appendingPathComponent(mode + suffix)
            try fm.createDirectory(at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
            try Data("previous save".utf8).write(to: target)
        }
        try store.restore(from: base.appendingPathComponent("browser.mugoatsave"))
        for mode in ["userdata", "sandbox"] {
            let data = try Data(contentsOf: store.root.appendingPathComponent(mode + suffix))
            precondition(data == Data([0,1,2,255,0,128]))
        }
        let backups = try fm.contentsOfDirectory(at: store.backups, includingPropertiesForKeys: nil)
        precondition(backups.count == 1)
        let old = try JSONDecoder().decode(SaveStore.Archive.self, from: Data(contentsOf: backups[0]))
        precondition(old.entries.count == 2 && old.entries.allSatisfy { $0.data == Data("previous save".utf8) })
        let native = try store.export()
        try fm.copyItem(at: native, to: base.appendingPathComponent("iphone.mugoatsave"))
        print("PASS: unmodified iPhone SaveStore restored browser exports, retained originals in rollback, and exported both profiles for browser import.")
    }
}
