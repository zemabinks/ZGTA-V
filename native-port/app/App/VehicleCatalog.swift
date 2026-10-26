import Foundation

/// Reference names are not an asset installer. The engine still validates every spawn.
enum VehicleCatalog {
    struct Category { let id: String; let name: String; let icon: String }
    struct Entry {
        let model: String
        let name: String
        let category: String
        let base: Bool
        let kind: String
        /// Official artwork or an explicitly supplied image for this exact mod model.
        var thumbnailURL: URL? {
            if kind == "mod" {
                guard let file = VehicleCatalog.modPreviews[model]?.file else { return nil }
                return Bundle.main.url(forResource: file, withExtension: nil)
            }
            guard kind != "mod", VehicleCatalog.vehicles.contains(where: { $0.model == model }),
                  model.range(of: "^[a-z][a-z0-9_]{0,62}$", options: .regularExpression) != nil else { return nil }
            return URL(string: VehicleCatalog.thumbnailBaseURL + model + ".webp")
        }
        var thumbnailCredit: String {
            if kind == "mod" { return VehicleCatalog.modPreviews[model]?.credit ?? "Installed mod vehicle" }
            return "Vehicle reference: FiveM / Cfx.re. Pictures do not install game models."
        }
        var canSpawn: Bool { kind != "train" }
        var detail: String {
            if kind == "train" { return "\(model) · Requires a dedicated train spawner" }
            let source = kind == "mod" ? "Detected mod · matching pack must be loaded" : base ? "Base game" : "DLC · matching game files required"
            return "\(model) · \(source)" + (kind == "trailer" ? " · No driving seat" : "")
        }
    }
    enum Row {
        case custom
        case dlcFilter
        case category(Category, Int, Bool)
        case vehicle(Entry)
        case emptyMods

        var id: String {
            switch self {
            case .custom: return "custom"
            case .dlcFilter: return "dlc-filter"
            case let .category(category, _, _): return "category:" + category.id
            case let .vehicle(vehicle): return "vehicle:" + vehicle.category + ":" + vehicle.model
            case .emptyMods: return "empty-mods"
            }
        }
    }

    /// Removal offsets refer to the old snapshot; insertion offsets to the new.
    /// Stable identities retain category cells when their expanded state changes.
    static func rowChanges(from old: [Row], to new: [Row]) -> (removed: [Int], inserted: [Int]) {
        var removed: [Int] = [], inserted: [Int] = []
        for change in new.map(\.id).difference(from: old.map(\.id)) {
            switch change {
            case let .remove(offset, _, _): removed.append(offset)
            case let .insert(offset, _, _): inserted.append(offset)
            }
        }
        return (removed, inserted)
    }
    static func rows(query: String, expanded: Set<String>, includeDLC: Bool, modModels: [String]) -> [Row] {
        let query = query.trimmingCharacters(in: .whitespacesAndNewlines)
        var result: [Row] = [.custom, .dlcFilter]
        let mods = Set(modModels.map { $0.lowercased() }).filter { model in
            model.range(of: "^[a-z][a-z0-9_]{0,62}$", options: .regularExpression) != nil
        }.sorted().map { Entry(model: $0, name: $0, category: "Installed mods", base: false, kind: "mod") }
        let allCategories = categories + [Category(id: "Installed mods", name: "Installed mod vehicles", icon: "puzzlepiece.extension.fill")]
        for category in allCategories {
            let pool = category.id == "Installed mods" ? mods : vehicles.filter { $0.category == category.id && (includeDLC || $0.base) }
            let entries = pool.filter { query.isEmpty || [$0.name, $0.model, category.name].contains { $0.localizedCaseInsensitiveContains(query) } }
                .sorted { ($0.name.lowercased(), $0.model) < ($1.name.lowercased(), $1.model) }
            if entries.isEmpty && (category.id != "Installed mods" || !query.isEmpty) { continue }
            let open = !query.isEmpty || expanded.contains(category.id)
            result.append(.category(category, entries.count, open))
            if open {
                if entries.isEmpty { result.append(.emptyMods) }
                else { result += entries.map { .vehicle($0) } }
            }
        }
        return result
    }
}
