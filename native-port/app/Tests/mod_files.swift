import Foundation

@main struct ModFilesTests {
    static func main() throws {
        let fm = FileManager.default
        let root = fm.temporaryDirectory.appendingPathComponent("MugoatModTests-" + UUID().uuidString)
        defer { try? fm.removeItem(at: root) }
        let files = ["README.txt", "readme.TXT.disabled", "notes.pdf", "package.zip", "car/dlc.rpf",
                     "car/README.txt", "car/model.YFT", "handling.meta.disabled", "car/texture.ytd",
                     "old.disabled/dlc.rpf", "name.disabled-copy/dlc.rpf", ".hidden.rpf", "script.lua"]
        for path in files {
            let url = root.appendingPathComponent(path)
            try fm.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try Data([1, 2, 3]).write(to: url)
        }
        // A directory named like an asset and a symlink must not become installed mods.
        try fm.createDirectory(at: root.appendingPathComponent("directory.rpf"), withIntermediateDirectories: true)
        try fm.createSymbolicLink(at: root.appendingPathComponent("linked.rpf"), withDestinationURL: root.appendingPathComponent("README.txt"))
        let entries = ModFiles.scan(root)
        precondition(Set(entries.map(\.name)) == Set([
            "car/dlc.rpf", "car/model.YFT", "handling.meta.disabled", "car/texture.ytd",
            "name.disabled-copy/dlc.rpf", "script.lua"
        ]), "Unexpected mod entries: \(entries.map(\.name))")
        precondition(entries.first(where: { $0.name == "handling.meta.disabled" })?.isEnabled == false)
        precondition(entries.filter(\.isEnabled).count == 5)
        precondition(entries.allSatisfy { $0.size == 3 })
        precondition(!ModFiles.importExtensions.contains("txt"))
        precondition(ModFiles.importExtensions.contains("zip"))
        precondition(ModFiles.importExtensions.contains("yft"))
        // Toggling a file must retain it in the list and keep README excluded after refresh.
        let dlc = root.appendingPathComponent("car/dlc.rpf")
        try fm.moveItem(at: dlc, to: dlc.appendingPathExtension("disabled"))
        let disabled = ModFiles.scan(root)
        precondition(disabled.count == entries.count)
        precondition(disabled.first(where: { $0.name == "car/dlc.rpf.disabled" })?.isEnabled == false)
        try fm.moveItem(at: dlc.appendingPathExtension("disabled"), to: dlc)
        precondition(ModFiles.scan(root).filter(\.isEnabled).count == 5)
        print("Mod file scanning, README filtering and toggle checks passed")
    }
}
