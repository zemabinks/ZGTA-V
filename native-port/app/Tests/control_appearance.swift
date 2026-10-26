import Foundation

final class AppearanceDefaults: UserDefaults {
    private var values: [String:Any] = [:]
    override func string(forKey key: String) -> String? { values[key] as? String }
    override func object(forKey key: String) -> Any? { values[key] }
    override func set(_ value: Any?, forKey key: String) { values[key] = value }
}
@main struct AppearanceTests {
    static func main() {
        let defaults = AppearanceDefaults()
        defaults.set(["foot.jump":[0.4,0.6,1.2,0.0]], forKey:"controlsLayout")
        let before = defaults.object(forKey:"controlsLayout") as! [String:[Double]]
        precondition(TouchButtonAppearance.read(in:defaults) == .icons)
        precondition(TouchButtonAppearance.allCases == [.icons, .xbox, .playstation])
        for style in TouchButtonAppearance.allCases {
            style.save(in:defaults)
            precondition(TouchButtonAppearance.read(in:defaults) == style)
            precondition((defaults.object(forKey:"controlsLayout") as! [String:[Double]]) == before)
        }
        TouchButtonAppearance.xbox.save(in:defaults)
        precondition(TouchButtonAppearance.read(in:defaults) == .xbox)
        precondition((defaults.object(forKey:"controlsLayout") as! [String:[Double]]) == before)
        TouchButtonAppearance.icons.save(in:defaults)
        precondition(TouchButtonAppearance.read(in:defaults) == .icons)
        defaults.set("unknown-future-style",forKey:TouchButtonAppearance.preferenceKey)
        precondition(TouchButtonAppearance.read(in:defaults) == .icons)
        precondition(defaults.string(forKey:TouchButtonAppearance.preferenceKey) == "unknown-future-style")
        for (name,label) in [("jump","X"),("enter","Y"),("reload","B"),("accept","A"),("aim","LT"),("fire","RT"),("weapons","LB"),("cover","RB"),("special","L3+R3"),("driveBy","LB+RB"),("airFire","A"),("gear","L3"),("tabLeft","LB"),("tabRight","RB")] {
            precondition(TouchButtonAppearance.xboxCaption(for:name) == label)
        }
        precondition(TouchButtonAppearance.xboxCaption(for:"gas",bicycle:true) == "A")
        precondition(TouchButtonAppearance.xboxCaption(for:"gas") == "RT")
        precondition(TouchButtonAppearance.xboxCaption(for:"handbrake",bicycle:true) == "RT")
        precondition(TouchButtonAppearance.xboxCaption(for:"handbrake") == "RB")
        precondition(TouchButtonAppearance.xboxCaption(for:"phone",phoneOut:true) == "B")
        precondition(TouchButtonAppearance.xboxCaption(for:"phone") == "↑")
        let playstation = TouchButtonAppearance.playstation
        for (name,label) in [("jump","□"),("enter","△"),("reload","○"),("accept","×"),("aim","L2"),("fire","R2"),("weapons","L1"),("cover","R1"),("special","L3+R3"),("driveBy","L1+R1"),("airFire","×"),("gear","L3"),("tabLeft","L1"),("tabRight","R1"),("camera","Touch"),("pause","Options")] {
            precondition(playstation.caption(for:name) == label)
            precondition(TouchButtonAppearance.icons.caption(for:name) == nil)
            precondition(TouchButtonAppearance.xbox.caption(for:name) == TouchButtonAppearance.xboxCaption(for:name))
        }
        precondition(playstation.caption(for:"gas",bicycle:true) == "×")
        precondition(playstation.caption(for:"gas") == "R2")
        precondition(playstation.caption(for:"handbrake",bicycle:true) == "R2")
        precondition(playstation.caption(for:"handbrake") == "R1")
        precondition(playstation.caption(for:"phone",phoneOut:true) == "○")
        precondition(playstation.caption(for:"phone") == "↑")
        precondition(playstation.caption(for:"towArmUp") == "LS↑")
        precondition(playstation.accessibilityHint(for:"×") == "PlayStation button Cross")
        precondition(playstation.accessibilityHint(for:"□") == "PlayStation button Square")
        precondition(playstation.accessibilityHint(for:"○") == "PlayStation button Circle")
        precondition(playstation.accessibilityHint(for:"△") == "PlayStation button Triangle")
        precondition(TouchButtonAppearance.xbox.accessibilityHint(for:"X") == "Xbox button X")
        precondition(playstation.title == "PlayStation" && playstation.menuTitle == "PlayStation-style buttons")
        for name in ["settings","cheat","speaker","mic","buyWeapon","unknown-future-control"] {
            for style in TouchButtonAppearance.allCases { precondition(style.caption(for:name) == nil) }
        }
        print("PASS: three-style appearance persistence, original-layout preservation, Xbox/PlayStation pad labels, contextual variants and spoken symbols; memory-only preferences.")
    }
}
