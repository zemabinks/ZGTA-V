/// The UDP snapshot bridge implements these features; the Engine LAN relay does
/// not. Keep the controls present and explain the boundary without toggling a
/// microphone or sending an unrelated backend command.
enum EngineLanFeaturePolicy {
    static func unavailableMessage(button: String, engineLAN: Bool) -> String? {
        guard engineLAN else { return nil }
        switch button {
        case "speaker", "mic":
            return "Engine LAN voice chat is not implemented. Voice remains available with the existing multiplayer bridge."
        case "buyWeapon":
            return "This role/wallet action belongs to the existing multiplayer bridge. It is not implemented in Engine LAN."
        default: return nil
        }
    }
}
