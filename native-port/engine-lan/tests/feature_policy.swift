@main struct FeaturePolicyTests {
    static func main() {
        for name in ["buyWeapon"] {
            precondition(EngineLanFeaturePolicy.unavailableMessage(button:name,engineLAN:true) != nil)
            precondition(EngineLanFeaturePolicy.unavailableMessage(button:name,engineLAN:false) == nil)
        }
        for name in ["speaker", "mic", "fire", "jump", "enter", "aim", "weapons", "camera", "pause", "phone", "settings", "cheat", "gas", "gear", "unknown"] {
            precondition(EngineLanFeaturePolicy.unavailableMessage(button:name,engineLAN:true) == nil)
        }
        print("ONLY_LEGACY_ROLE_ACTIONS_REPORT_UNAVAILABLE_ON_LAN_PASS")
    }
}
