/// Only role/wallet actions remain specific to the legacy snapshot bridge.
enum EngineLanFeaturePolicy {
    static func unavailableMessage(button: String, engineLAN: Bool) -> String? {
        guard engineLAN else { return nil }
        switch button {
        case "buyWeapon":
            return "This role/wallet action belongs to the existing multiplayer bridge. It is not implemented in Engine LAN."
        default: return nil
        }
    }
}
