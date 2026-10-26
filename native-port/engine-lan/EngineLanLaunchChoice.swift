/// LAN selection is explicit and process-local. It does not replace the saved
/// Story/Free Roam preference or change either engine start-mode raw value.
struct EngineLanLaunchChoice {
    private(set) var isLAN = false
    private(set) var legacyBridgeSelected = false
    mutating func select(index: Int) -> Int? {
        switch index {
        case 0: isLAN = false; legacyBridgeSelected = false; return 1
        case 1: isLAN = false; legacyBridgeSelected = false; return 2
        case 2: isLAN = true; legacyBridgeSelected = false; return nil
        default: return nil
        }
    }
    mutating func selectLegacyBridge() { isLAN = false; legacyBridgeSelected = true }
    mutating func offlineModeChanged() { isLAN = false }
    func selectedIndex(savedMode: Int?) -> Int? {
        if isLAN { return 2 }
        switch savedMode {
        case 1: return 0
        case 2: return 1
        default: return nil
        }
    }
    func engineMode(savedMode: Int?) -> Int32 { isLAN ? 1 : (savedMode == 1 ? 1 : 2) }
}
