import Foundation

enum ModRuntime {
    struct Catalog {
        var packs: [ModPack] = []
        var problems: [String] = []
        var models: [String] { packs.flatMap(\.models).sorted() }
        /// Spawnable vehicle model names (vehicles.meta), for the spawner lists.
        var vehicleModels: [String] { packs.flatMap(\.vehicleModels).sorted() }
    }
    static func catalog(_ directory: URL) -> Catalog {
        var result = Catalog(), names = Set<String>(), models = Set<String>()
        let files = ModFiles.scan(directory).filter { $0.isEnabled && $0.url.pathExtension.lowercased() == "rpf" }.sorted { $0.name < $1.name }
        for file in files {
            do {
                let pack = try ModPack(url: file.url)
                guard names.insert(pack.name).inserted else { throw ModError("Duplicate DLC package %@. Enable only one version.", pack.name) }
                guard models.isDisjoint(with: pack.models) else { throw ModError("Duplicate vehicle models across mods: %@.", pack.models.joined(separator: ", ")) }
                models.formUnion(pack.models); result.packs.append(pack)
            } catch let error as ModError {
                if file.url.lastPathComponent.lowercased() == "dlc.rpf" || error.message.contains("Enhanced") || error.message.hasPrefix("Duplicate ") {
                    result.problems.append(file.name + ": " + error.localizedDescription)
                }
            } catch {
                if file.url.lastPathComponent.lowercased() == "dlc.rpf" {
                    result.problems.append(file.name + ": " + error.localizedDescription)
                }
            }
        }
        return result
    }

    /// Builds a manifest overlay. Original game files and their sizes remain untouched.
    static func prepare(baseManifest: URL, mods: URL, runtime: URL, dlcList: Data) throws -> (URL, Catalog) {
        let catalog = catalog(mods)
        if !catalog.problems.isEmpty { throw ModError(catalog.problems.joined(separator: "\n")) }
        guard !catalog.packs.isEmpty else { return (baseManifest, catalog) }
        guard var manifest = try JSONSerialization.jsonObject(with: Data(contentsOf: baseManifest)) as? [String: Any],
              var files = manifest["files"] as? [[Any]],
              var xml = String(data: dlcList, encoding: .utf8),
              xml.range(of: "</Paths>", options: .caseInsensitive) != nil else { throw ModError("A valid original DLC list is missing.") }
        try FileManager.default.createDirectory(at: runtime, withIntermediateDirectories: true)
        var overrides = manifest["_mugoatOverrides"] as? [String: String] ?? [:]
        func add(_ path: String, file: URL) throws {
            let size = try file.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0
            if let index = files.firstIndex(where: { ($0.first as? String)?.lowercased() == path.lowercased() }) {
                // Preserve indices used by preloader/cache and by the engine.
                let original = files[index][0] as! String
                files[index][1] = size; overrides[original] = file.path
            } else { files.append([path, size, 0]); overrides[path] = file.path }
        }
        for pack in catalog.packs {
            let prefix = "x64/dlcPacks/" + pack.name + "/"
            try add(prefix + "dlc.rpf", file: pack.url)
            for name in ["setup2.xml", "content.xml"] {
                guard let entry = pack.archive.entries.first(where: { $0.path == name }) else { throw ModError("DLC is missing %@", name) }
                let target = runtime.appendingPathComponent(pack.name + "-" + name)
                try pack.archive.metadata(entry).write(to: target, options: .atomic)
                try add(prefix + name, file: target)
            }
            // This engine mounts DLC through platform:\dlcPacks, not update/x64/dlcpacks.
            let path = "platform:\\dlcPacks\\" + pack.name + "\\"
            if !xml.lowercased().contains(path.lowercased()) {
                if let range = xml.range(of: "</Paths>", options: .caseInsensitive) {
                    xml.replaceSubrange(range, with: "\t<Item>" + path + "</Item>\n" + xml[range])
                }
            }
        }
        let list = runtime.appendingPathComponent("dlcList.xml")
        try Data(xml.utf8).write(to: list, options: .atomic)
        try add("common/data/dlcList.xml", file: list)
        manifest["files"] = files; manifest["_mugoatOverrides"] = overrides
        let output = runtime.appendingPathComponent("manifest.json")
        try JSONSerialization.data(withJSONObject: manifest, options: [.sortedKeys]).write(to: output, options: .atomic)
        return (output, catalog)
    }

    static func importPack(_ source: URL, into mods: URL) throws -> ModPack {
        let pack = try ModPack(url: source), directory = mods.appendingPathComponent(pack.name)
        let fm = FileManager.default
        try fm.createDirectory(at: directory, withIntermediateDirectories: true)
        let temporary = directory.appendingPathComponent("import-" + UUID().uuidString + ".rpf")
        let target = directory.appendingPathComponent("dlc.rpf")
        try fm.copyItem(at: source, to: temporary)
        defer { try? fm.removeItem(at: temporary) }
        if fm.fileExists(atPath: target.path) { _ = try fm.replaceItemAt(target, withItemAt: temporary) }
        else { try fm.moveItem(at: temporary, to: target) }
        return try ModPack(url: target)
    }
}
