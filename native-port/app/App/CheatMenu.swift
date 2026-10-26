import UIKit

struct CheatItem: Identifiable {
    let id = UUID()
    let code: String
    let name: String
    let desc: String
    let category: String
}

let CHEAT_LIST: [CheatItem] = [
    // MARK: - Character (12)
    CheatItem(code: "UNFREEZE", name: "Unstick Scene / Exit Cutscene", desc: "Force exit the cutscene, unlock controls and unfreeze the screen", category: "Player"),
    CheatItem(code: "PAINKILLER", name: "Invincibility for 5 Minutes", desc: "Take no damage for 5 minutes", category: "Player"),
    CheatItem(code: "TURTLE", name: "Full Health & Armor", desc: "Restore 100% health and armor, and repair your vehicle", category: "Player"),
    CheatItem(code: "TOOLUP", name: "All Weapons", desc: "Receive all weapons and ammunition", category: "Player"),
    CheatItem(code: "LAWYERUP", name: "Clear Wanted Stars", desc: "Reduce wanted level to 0", category: "Player"),
    CheatItem(code: "FUGITIVE", name: "Add 1 Wanted Star", desc: "Increase wanted level by 1", category: "Player"),
    CheatItem(code: "POWERUP", name: "Full Special Ability", desc: "Refill the character's special ability meter", category: "Player"),
    CheatItem(code: "CATCHME", name: "Fast Run", desc: "Increase maximum movement speed", category: "Player"),
    CheatItem(code: "GOTGILLS", name: "Fast Swim", desc: "Increase underwater swimming speed", category: "Player"),
    CheatItem(code: "HOPTOIT", name: "Super Jump", desc: "Jump 10 times higher than normal", category: "Player"),
    CheatItem(code: "SKYDIVE", name: "Equip Parachute", desc: "Receive a parachute for jumping from heights", category: "Player"),
    CheatItem(code: "LIQUOR", name: "Drunk Mode", desc: "Stagger with a drunken effect", category: "Player"),

    // MARK: - Vehicles (13)
    CheatItem(code: "BUZZOFF", name: "Buzzard Helicopter", desc: "Attack helicopter with guns & missiles", category: "Vehicles"),
    CheatItem(code: "COMET", name: "Comet Sports Car", desc: "High-speed two-door Porsche", category: "Vehicles"),
    CheatItem(code: "RAPIDGT", name: "Rapid GT Race Car", desc: "Premium sports car", category: "Vehicles"),
    CheatItem(code: "ROCKET", name: "PCJ-600 Racing Motorcycle", desc: "High-speed, large-displacement motorcycle", category: "Vehicles"),
    CheatItem(code: "OFFROAD", name: "Sanchez Dirt Bike", desc: "Off-road motorcycle for riding over hills", category: "Vehicles"),
    CheatItem(code: "BANDIT", name: "BMX Bicycle", desc: "Bicycle for acrobatic stunts", category: "Vehicles"),
    CheatItem(code: "BARNSTORM", name: "Stunt Plane", desc: "Propeller stunt plane", category: "Vehicles"),
    CheatItem(code: "VINEWOOD", name: "Limousine", desc: "Stretch luxury car", category: "Vehicles"),
    CheatItem(code: "TRASHED", name: "Trashmaster Garbage Truck", desc: "Armored garbage truck for ramming other vehicles", category: "Vehicles"),
    CheatItem(code: "DEATHCAR", name: "Duke O'Death Armored Car", desc: "Muscle car with extremely strong bullet and explosion resistance", category: "Vehicles"),
    CheatItem(code: "BUBBLES", name: "Kraken Submarine", desc: "Submersible for exploring the ocean floor", category: "Vehicles"),
    CheatItem(code: "FLYSPRAY", name: "Duster Plane", desc: "Classic propeller plane", category: "Vehicles"),
    CheatItem(code: "EXTINCT", name: "Dodo Seaplane", desc: "Plane that lands on water", category: "Vehicles"),

    // MARK: - Combat (4)
    CheatItem(code: "HOTHANDS", name: "Explosive Fists", desc: "Punch enemies away and make them explode", category: "Combat"),
    CheatItem(code: "INCENDIARY", name: "Incendiary Bullets", desc: "Fire bullets that ignite targets", category: "Combat"),
    CheatItem(code: "HIGHEX", name: "Explosive Bullets", desc: "Each shot creates a large explosion", category: "Combat"),
    CheatItem(code: "DEADEYE", name: "Slow-Motion Aim", desc: "Slow time while holding the aim button", category: "Combat"),

    // MARK: - World (5)
    CheatItem(code: "SKYFALL", name: "Skyfall", desc: "Drop the character from high above the clouds", category: "World"),
    CheatItem(code: "SLOWMO", name: "Slow the Entire Game", desc: "Cinematic slow-motion effect", category: "World"),
    CheatItem(code: "FLOATER", name: "Moon Gravity", desc: "Vehicles and people float lightly", category: "World"),
    CheatItem(code: "MAKEITRAIN", name: "Change Weather", desc: "Switch between sunshine, rain and thunderstorms", category: "World"),
    CheatItem(code: "SNOW", name: "Snowfall", desc: "Enable snowfall across the entire map", category: "World")
]

struct SpawnerPreset: Identifiable {
    let id = UUID()
    let name: String
    let model: String
    let icon: String
    let category: String
}

// Legacy consumers share the same complete catalog as the Mod Manager.
let COMMON_VEHICLES: [SpawnerPreset] = VehicleCatalog.vehicles.filter(\.canSpawn).map { vehicle in
    let category = VehicleCatalog.categories.first { $0.id == vehicle.category }!
    return SpawnerPreset(name: vehicle.name, model: vehicle.model, icon: category.icon, category: category.name)
}

enum CheatInputMode: String, CaseIterable, Identifiable {
    case auto = "Auto"
    case console = "Console (`)"
    case gamepad = "Gamepad"
    var id: String { rawValue }
}

enum CheatMenuTab: String, CaseIterable, Identifiable {
    case cheats = "Cheats"
    case spawner = "🚗 Vehicle Spawner"
    var id: String { rawValue }
}

final class CheatManager {
    static let shared = CheatManager()
    static var isApplying: Bool { PGIsCheatInProgress() }

    /// Applies a cheat code via Gamepad combo, Console typing, or Auto selection.
    static func apply(code: String, mode: CheatInputMode = .console, completion: ((Bool) -> Void)? = nil) {
        if MugoatOnlineEnabled() {
            completion?(false)
            return
        }
        let trimmed = code.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        guard !trimmed.isEmpty else {
            completion?(false)
            return
        }

        trimmed.withCString { cStr in
            switch mode {
            case .auto, .console:
                PGApplyCheatConsole(cStr)
            case .gamepad:
                PGApplyCheatGamepad(cStr)
            }
        }

        DispatchQueue.main.async {
            completion?(true)
        }
    }
}
