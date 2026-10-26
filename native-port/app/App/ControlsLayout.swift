import UIKit

/// The player's own touch-control layout. Each moved control is stored by group ("foot" or
/// "vehicle") and name, as its centre in the safe area (0...1 on both axes), a size factor and
/// whether it is hidden. Controls without an entry use the default layout.
struct ControlsLayout {
    struct Entry: Equatable {
        var x: CGFloat, y: CGFloat, scale: CGFloat, hidden: Bool
    }
    private static let key = "controlsLayout"
    /// Never hidden: the game cannot be played (or left) without them.
    static let essential: Set<String> = ["fire", "aim", "enter", "gas", "brake", "pause", "settings", "airFire", "vehicleWeapon", "cheat", "speaker", "mic", "buyWeapon"]

    static var entries: [String: Entry] {
        get {
            guard let raw = UserDefaults.standard.dictionary(forKey: key) as? [String: [Double]] else { return [:] }
            return raw.compactMapValues { v in
                v.count >= 4 ? Entry(x: CGFloat(v[0]), y: CGFloat(v[1]), scale: CGFloat(v[2]), hidden: v[3] != 0) : nil
            }
        }
        set {
            let raw = newValue.mapValues { [Double($0.x), Double($0.y), Double($0.scale), $0.hidden ? 1 : 0] }
            UserDefaults.standard.set(raw, forKey: key)
        }
    }
    static func entry(group: String, name: String) -> Entry? { entries["\(group).\(name)"] }
    static func set(_ entry: Entry?, group: String, name: String) {
        var all = entries
        all["\(group).\(name)"] = entry
        entries = all
    }
    static func reset(group: String) { entries = entries.filter { !$0.key.hasPrefix(group + ".") } }
    static var isCustomized: Bool { !entries.isEmpty }
}

/// Full-screen editor: drag a control to move it, pinch (or the slider) to resize it, hide the
/// ones you don't use. Shows the on-foot and the vehicle controls (switch at the bottom).
final class ControlsLayoutEditorController: UIViewController {
    var onDone: (() -> Void)?
    private let controls = TouchControlsView(frame: .zero)
    private let background = UIImageView()
    private let toolbar = UIStackView()
    private let groupPicker = UISegmentedControl(items: ["On foot", "In a vehicle", "Aircraft"])
    private let sizeSlider = UISlider()
    private let appearanceButton = UIButton(type: .system)
    private let hideButton = UIButton(type: .system)
    private let hint = UILabel()
    private var selected: ControlButton? { didSet { refreshSelection() } }
    private var dragOffset = CGPoint.zero
    private var pinchStartScale: CGFloat = 1

    override var supportedInterfaceOrientations: UIInterfaceOrientationMask { .landscape }
    override var prefersStatusBarHidden: Bool { true }
    override var prefersHomeIndicatorAutoHidden: Bool { true }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = Theme.night
        // A game-like backdrop: the title art when the game folder provides it, otherwise a gradient.
        background.contentMode = .scaleAspectFill
        background.clipsToBounds = true
        background.alpha = 0.15
        background.image = UIImage(named: "LosSantosMap")
        background.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(background)
        controls.translatesAutoresizingMaskIntoConstraints = false
        controls.editing = true
        controls.characterSwitchEnabled = true
        controls.isUserInteractionEnabled = false
        view.addSubview(controls)
        NSLayoutConstraint.activate([
            background.leadingAnchor.constraint(equalTo: view.leadingAnchor), background.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            background.topAnchor.constraint(equalTo: view.topAnchor), background.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            controls.leadingAnchor.constraint(equalTo: view.leadingAnchor), controls.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            controls.topAnchor.constraint(equalTo: view.topAnchor), controls.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])

        // One configuration-owned background. A tinted configuration plus a
        // UIView background draws two differently sized boxes on iOS.
        var appearance = UIButton.Configuration.plain()
        appearance.baseForegroundColor = .white
        appearance.background = .clear()
        appearance.background.backgroundColor = UIColor.black.withAlphaComponent(0.7)
        appearance.background.cornerRadius = 10
        appearance.contentInsets = NSDirectionalEdgeInsets(top: 10, leading: 14, bottom: 10, trailing: 14)
        appearance.image = UIImage(systemName: "chevron.down")
        appearance.imagePlacement = .trailing
        appearance.imagePadding = 8
        appearance.titleTextAttributesTransformer = UIConfigurationTextAttributesTransformer { incoming in
            var attributes = incoming
            attributes.font = .systemFont(ofSize: 15, weight: .semibold)
            return attributes
        }
        appearanceButton.configuration = appearance
        appearanceButton.tintColor = .white
        appearanceButton.showsMenuAsPrimaryAction = true
        appearanceButton.accessibilityLabel = "Button appearance"
        refreshAppearanceMenu()
        appearanceButton.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(appearanceButton)
        NSLayoutConstraint.activate([
            appearanceButton.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 16),
            appearanceButton.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 12)
        ])

        hint.text = "Drag a button to move it · pinch to resize"
        hint.font = .preferredFont(forTextStyle: .footnote)
        hint.textColor = UIColor.white.withAlphaComponent(0.85)
        hint.textAlignment = .center
        hint.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(hint)

        groupPicker.selectedSegmentIndex = 0
        groupPicker.overrideUserInterfaceStyle = .dark
        groupPicker.addAction(UIAction { [weak self] _ in self?.showGroup() }, for: .valueChanged)
        groupPicker.addTarget(self, action: #selector(groupChanged), for: .valueChanged)
        sizeSlider.minimumValue = 0.6
        sizeSlider.maximumValue = 1.8
        sizeSlider.accessibilityLabel = "Size of the selected button"
        sizeSlider.addAction(UIAction { [weak self] _ in self?.sizeChanged() }, for: .valueChanged)
        sizeSlider.widthAnchor.constraint(equalToConstant: 110).isActive = true
        hideButton.addAction(UIAction { [weak self] _ in self?.toggleHidden() }, for: .touchUpInside)
        let reset = UIButton(type: .system)
        reset.setTitle("Reset", for: .normal)
        reset.addAction(UIAction { [weak self] _ in self?.resetGroup() }, for: .touchUpInside)
        let done = UIButton(type: .system)
        done.setTitle(L10n.text("Done"), for: .normal)
        done.titleLabel?.font = .preferredFont(forTextStyle: .headline)
        done.addAction(UIAction { [weak self] _ in self?.finish() }, for: .touchUpInside)
        for item in [groupPicker, sizeSlider, hideButton, reset, done] as [UIView] { toolbar.addArrangedSubview(item) }
        toolbar.axis = .horizontal
        toolbar.spacing = 12
        toolbar.alignment = .center
        toolbar.isLayoutMarginsRelativeArrangement = true
        toolbar.directionalLayoutMargins = NSDirectionalEdgeInsets(top: 8, leading: 16, bottom: 8, trailing: 16)
        toolbar.backgroundColor = UIColor.black.withAlphaComponent(0.7)
        toolbar.layer.cornerRadius = 14
        toolbar.overrideUserInterfaceStyle = .dark
        toolbar.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(toolbar)
        NSLayoutConstraint.activate([
            // Bottom-left: the move-stick area, which has no buttons to cover.
            toolbar.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 8),
            toolbar.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -8),
            hint.leadingAnchor.constraint(equalTo: toolbar.leadingAnchor, constant: 8),
            hint.bottomAnchor.constraint(equalTo: toolbar.topAnchor, constant: -8),
        ])

        let pan = UIPanGestureRecognizer(target: self, action: #selector(panned(_:)))
        pan.maximumNumberOfTouches = 1
        let pinch = UIPinchGestureRecognizer(target: self, action: #selector(pinched(_:)))
        let tap = UITapGestureRecognizer(target: self, action: #selector(tapped(_:)))
        for gesture in [pan, pinch, tap] as [UIGestureRecognizer] { gesture.delegate = self; view.addGestureRecognizer(gesture) }
        showGroup()
        applyLaunchArguments()
    }

    private func refreshAppearanceMenu() {
        let selected = TouchButtonAppearance.read()
        appearanceButton.configuration?.title = "Buttons: " + selected.title
        appearanceButton.accessibilityValue = selected.title
        appearanceButton.menu = UIMenu(title: "Button appearance", children: TouchButtonAppearance.allCases.map { style in
            UIAction(title: style.menuTitle, state: selected == style ? .on : .off) { [weak self] _ in
                style.save()
                self?.controls.updateVisibility()
                self?.refreshAppearanceMenu()
            }
        })
    }

    private var group: String { groupPicker.selectedSegmentIndex == 0 ? "foot" : "vehicle" }

    private func showGroup() {
        // Aircraft share the vehicle layout, but show their own buttons (plane: vehicle type 1 + 1).
        controls.updateContext(vehicle: [0, 1, 2][max(0, groupPicker.selectedSegmentIndex)], pauseMenu: false)
        selected = nil
        controls.updateVisibility()
        controls.setNeedsLayout()
    }

    @objc private func groupChanged() {
        showGroup()
    }

    private func refreshSelection() {
        controls.highlighted = selected
        sizeSlider.isEnabled = selected != nil
        let entry = selected.flatMap { ControlsLayout.entry(group: group, name: $0.name) }
        sizeSlider.value = Float(entry?.scale ?? 1)
        if let selected {
            let hidden = entry?.hidden ?? false
            hideButton.setTitle(hidden ? "Show" : "Hide", for: .normal)
            hideButton.isEnabled = !ControlsLayout.essential.contains(selected.name)
            hint.text = "\(selected.accessibilityLabel ?? selected.name)\(hidden ? " (hidden in game)" : "")"
        } else {
            hideButton.setTitle("Hide", for: .normal)
            hideButton.isEnabled = false
            hint.text = "Drag a button to move it · pinch to resize"
        }
    }

    /// Writes the selected control's current place, keeping its size and hidden state.
    private func store(_ button: ControlButton, center: CGPoint? = nil, scale: CGFloat? = nil, hidden: Bool? = nil) {
        let old = ControlsLayout.entry(group: group, name: button.name)
        let normalized = controls.normalized(center ?? button.center)
        ControlsLayout.set(ControlsLayout.Entry(x: normalized.x, y: normalized.y,
                                                scale: scale ?? old?.scale ?? 1, hidden: hidden ?? old?.hidden ?? false),
                           group: group, name: button.name)
        controls.updateVisibility()
        controls.setNeedsLayout()
        controls.layoutIfNeeded()
    }

    @objc private func tapped(_ gesture: UITapGestureRecognizer) {
        selected = controls.editableButton(at: gesture.location(in: controls))
    }
    @objc private func panned(_ gesture: UIPanGestureRecognizer) {
        let point = gesture.location(in: controls)
        switch gesture.state {
        case .began:
            // The pan is recognized after the finger has already moved a little: look where it landed.
            let moved = gesture.translation(in: controls)
            let start = CGPoint(x: point.x - moved.x, y: point.y - moved.y)
            selected = controls.editableButton(at: start)
            if let selected { dragOffset = CGPoint(x: selected.center.x - start.x, y: selected.center.y - start.y) }
        case .changed:
            guard let selected else { return }
            store(selected, center: controls.clampedToSafeArea(CGPoint(x: point.x + dragOffset.x, y: point.y + dragOffset.y)))
        default:
            break
        }
    }
    @objc private func pinched(_ gesture: UIPinchGestureRecognizer) {
        switch gesture.state {
        case .began:
            if selected == nil { selected = controls.editableButton(at: gesture.location(in: controls)) }
            pinchStartScale = selected.flatMap { ControlsLayout.entry(group: group, name: $0.name)?.scale } ?? 1
        case .changed:
            guard let selected else { return }
            let scale = max(0.6, min(1.8, pinchStartScale * gesture.scale))
            store(selected, scale: scale)
            sizeSlider.value = Float(scale)
        default:
            break
        }
    }
    private func sizeChanged() {
        guard let selected else { return }
        store(selected, scale: CGFloat(sizeSlider.value))
    }
    private func toggleHidden() {
        guard let selected, !ControlsLayout.essential.contains(selected.name) else { return }
        let hidden = !(ControlsLayout.entry(group: group, name: selected.name)?.hidden ?? false)
        store(selected, hidden: hidden)
        refreshSelection()
    }
    private func resetGroup() {
        ControlsLayout.reset(group: group)
        selected = nil
        controls.updateVisibility()
        controls.setNeedsLayout()
    }
    private func finish() {
        onDone?()
        dismiss(animated: true)
    }

    /// Automation: --layout-demo moves and enlarges Jump (on foot) so the result can be checked
    /// without touching the screen; --layout-vehicle opens the vehicle set.
    private func applyLaunchArguments() {
        let arguments = ProcessInfo.processInfo.arguments
        if arguments.contains("--layout-vehicle") { groupPicker.selectedSegmentIndex = 1; showGroup() }
        if arguments.contains("--layout-demo") {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                self.controls.layoutIfNeeded()
                if let jump = self.controls.button(named: "jump") {
                    self.selected = jump
                    ControlsLayout.set(ControlsLayout.Entry(x: 0.5, y: 0.45, scale: 1.6, hidden: false), group: "foot", name: "jump")
                    self.controls.updateVisibility(); self.controls.setNeedsLayout(); self.controls.layoutIfNeeded()
                    self.refreshSelection()
                }
            }
        }
    }
}

extension ControlsLayoutEditorController: UIGestureRecognizerDelegate {
    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldReceive touch: UITouch) -> Bool {
        // The toolbar keeps its own taps.
        guard let view = touch.view else { return true }
        return !view.isDescendant(of: toolbar) && !view.isDescendant(of: appearanceButton)
    }
    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith other: UIGestureRecognizer) -> Bool {
        gestureRecognizer is UIPinchGestureRecognizer || other is UIPinchGestureRecognizer
    }
}
