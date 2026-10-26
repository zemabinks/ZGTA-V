import Foundation

/// Presentation only. Existing touch actions and saved positions stay intact.
enum TouchButtonAppearance: String, CaseIterable {
    case icons, xbox, playstation
    static let preferenceKey = "touchButtonAppearance"
    static func read(in defaults: UserDefaults = .standard) -> Self {
        defaults.string(forKey: preferenceKey).flatMap(Self.init(rawValue:)) ?? .icons
    }
    func save(in defaults: UserDefaults = .standard) { defaults.set(rawValue, forKey: Self.preferenceKey) }

    var title: String {
        switch self {
        case .icons: return "Icons"
        case .xbox: return "Xbox"
        case .playstation: return "PlayStation"
        }
    }
    var menuTitle: String {
        self == .icons ? "Original icons" : title + "-style buttons"
    }
    func caption(for name: String, bicycle: Bool = false, phoneOut: Bool = false) -> String? {
        guard self != .icons, let xbox = Self.xboxCaption(for: name, bicycle: bicycle, phoneOut: phoneOut) else { return nil }
        guard self == .playstation else { return xbox }
        // Convert equivalent physical pad inputs, not letters with similar names:
        // Xbox X is PlayStation Square; Xbox A is PlayStation Cross.
        return ["A":"×", "B":"○", "X":"□", "Y":"△", "LT":"L2", "RT":"R2",
                "LB":"L1", "RB":"R1", "LB+RB":"L1+R1", "View":"Touch", "☰":"Options"][xbox] ?? xbox
    }
    func accessibilityHint(for caption: String) -> String {
        let spoken = ["×":"Cross", "○":"Circle", "□":"Square", "△":"Triangle"][caption] ?? caption
        return title + " button " + spoken
    }

    /// Matches the pad bits already emitted by TouchControlsView, including its
    /// vehicle/phone variations. Compound actions retain compound captions.
    static func xboxCaption(for name: String, bicycle: Bool = false, phoneOut: Bool = false) -> String? {
        if name == "gas" { return bicycle ? "A" : "RT" }
        if name == "handbrake" { return bicycle ? "RT" : "RB" }
        if name == "phone" { return phoneOut ? "B" : "↑" }
        return [
            "fire":"RT", "leftFire":"RT", "aim":"LT", "leftAim":"LT",
            "jump":"X", "enter":"Y", "weapons":"LB", "reload":"B", "cover":"RB",
            "crouch":"L3", "switchCharacter":"↓", "special":"L3+R3", "interact":"→",
            "detonate":"←", "zoomIn":"↑", "zoomOut":"↓", "weaponPrev":"←", "weaponNext":"→",
            "brake":"LT", "driveBy":"LB+RB", "horn":"L3", "lookBack":"R3", "vehicleWeapon":"X",
            "dive":"A", "surface":"X", "towHook":"→", "roof":"→", "towArmUp":"LS↑", "towArmDown":"LS↓",
            "steer_left":"LS←", "steer_right":"LS→", "airFire":"A", "gear":"L3",
            "throttleUp":"RT", "throttleDown":"LT", "yawLeft":"LB", "yawRight":"RB",
            "camera":"View", "pause":"☰", "lights":"→", "radio":"←",
            "up":"↑", "down":"↓", "left":"←", "right":"→", "accept":"A", "back":"B",
            "tabLeft":"LB", "tabRight":"RB", "phone_option":"X", "taxi_hurry":"X", "taxi_stop":"B"
        ][name]
    }
}
