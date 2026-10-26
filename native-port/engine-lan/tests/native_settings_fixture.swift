// Compile only in the separate UIKit simulator preview target.
// Exercises the real Settings controller/model; game backends are inert adapters.
import UIKit

func settingsPreviewChecks(_ root: SettingsViewController, navigation: UINavigationController) -> [String: Any] {
    func all(_ view: UIView) -> [UIView] { [view] + view.subviews.flatMap(all) }
    root.view.layoutIfNeeded()
    let buttons = all(root.view).compactMap { $0 as? UIButton }.filter { $0.accessibilityIdentifier?.hasPrefix("settings.category.") == true }
    var failures = [String](); var checks = [String]()
    func check(_ value: Bool, _ name: String) { if value { checks.append(name) } else { failures.append(name) } }
    check(buttons.count == 8, "Eight categories rendered")
    let safe = root.view.bounds.inset(by: root.view.safeAreaInsets)
    check(buttons.allSatisfy { safe.insetBy(dx: -1, dy: -1).contains($0.convert($0.bounds, to: root.view)) && $0.bounds.height >= 44 }, "All category cards fit and meet touch size")
    var resolutionCalls = 0; var layoutCalls = 0; var savesCalls = 0
    root.resolutionChanged = { resolutionCalls += 1 }; root.editLayout = { layoutCalls += 1 }; root.openSaves = { savesCalls += 1 }
    let model = GameSettings.shared
    let preset = model.graphicsPreset; let fill = model.matchScreenShape; let sensitivity = model.lookSensitivity
    UIView.setAnimationsEnabled(false)
    defer { UIView.setAnimationsEnabled(true); model.graphicsPreset = preset; model.matchScreenShape = fill; model.lookSensitivity = sensitivity; navigation.popToRootViewController(animated: false) }
    func open(_ index: Int) -> SettingsViewController? {
        navigation.popToRootViewController(animated: false)
        RunLoop.main.run(until: Date().addingTimeInterval(0.15))
        root.view.layoutIfNeeded()
        (all(root.view).first { $0.accessibilityIdentifier == "settings.category.\(index)" } as? UIControl)?.sendActions(for: .touchUpInside)
        RunLoop.main.run(until: Date().addingTimeInterval(0.15))
        navigation.view.layoutIfNeeded()
        return navigation.topViewController as? SettingsViewController
    }
    if let graphics = open(0), graphics !== root {
        let changed = preset.rawValue == 0 ? 1 : 0
        graphics.tableView(graphics.tableView, didSelectRowAt: IndexPath(row: changed, section: 2))
        check(model.graphicsPreset.rawValue == changed && resolutionCalls == 1, "Preset persistence and forwarded callback")
        let cell = graphics.tableView(graphics.tableView, cellForRowAt: IndexPath(row: model.tier.allowed.count + 1, section: 2))
        if let control = cell.accessoryView as? UISwitch {
            control.isOn = !fill; control.sendActions(for: .valueChanged)
            check(model.matchScreenShape == !fill && resolutionCalls == 2, "Resolution switch persistence and callback")
        } else { check(false, "Resolution switch exists") }
    } else { check(false, "Graphics navigation") }
    if let controls = open(1), controls !== root {
        let cell = controls.tableView(controls.tableView, cellForRowAt: IndexPath(row: 0, section: 3))
        if let slider = cell.accessoryView.flatMap({ all($0).compactMap { $0 as? UISlider }.first }) {
            slider.value = 1.5; slider.sendActions(for: .valueChanged)
            check(abs(model.lookSensitivity - 1.5) < 0.01, "Slider writes the saved preference")
            check(cell.accessoryView.map { all($0).compactMap { $0 as? UILabel }.contains { $0.text == "1.5×" } } ?? false, "Slider numeric label updates")
        } else { check(false, "Slider exists") }
        controls.tableView(controls.tableView, didSelectRowAt: IndexPath(row: 7, section: 3))
        check(layoutCalls == 1, "Layout editor callback forwarded")
    } else { check(false, "Controls navigation") }
    if let support = open(6), support !== root {
        support.tableView(support.tableView, didSelectRowAt: IndexPath(row: 3, section: 6))
        check(savesCalls == 1, "Saves callback forwarded")
    } else { check(false, "Support navigation") }
    if let files = open(5), files !== root {
        let previous = AssetPreloader.shared.phase
        AssetPreloader.shared.phase = .downloading
        NotificationCenter.default.post(name: .assetPreloadChanged, object: nil)
        check(files.tableView(files.tableView, numberOfRowsInSection: 0) == 3, "File progress updates the displayed detail section")
        AssetPreloader.shared.phase = previous
        NotificationCenter.default.post(name: .assetPreloadChanged, object: nil)
    } else { check(false, "Files navigation") }
    return ["pass": failures.isEmpty, "passed": checks, "failures": failures, "backend": "Inert preview game-service adapters; real controller, localization, graphics sizing and saved-settings model"]
}
