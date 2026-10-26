import UIKit

/// What the player is doing; picked automatically from engine state.
enum ControlContext: Equatable {
    case onFoot, car, bike, bicycle, boat, sub, heli, plane, menu

    /// `vehicle` is PGCurrentTouchContext(): 0 on foot, else vehicle type + 1.
    init(vehicle: UInt32, pauseMenu: Bool) {
        if pauseMenu { self = .menu; return }
        switch vehicle {
        case 0: self = .onFoot
        case 2, 17: self = .plane
        case 9, 10, 11, 16: self = .heli
        case 12: self = .bike
        case 13: self = .bicycle
        case 14, 15: self = .boat
        case 1: self = .car
        default: self = .car
        }
    }
    var driving: Bool { [.car, .bike, .bicycle, .boat, .sub].contains(self) }
    var flying: Bool { self == .heli || self == .plane }
}

enum ControlStyle {
    /// GTA V's HUD blue, the only accent colour in the overlay.
    static let accent = UIColor(red: 0.365, green: 0.714, blue: 0.898, alpha: 1)
    /// SF Symbols for controls that have no generated icon.
    static let fallbackSymbol: [String: String] = [
        "radio": "radio", "look_back": "arrow.uturn.backward", "up": "chevron.up", "down": "chevron.down",
        "left": "chevron.left", "right": "chevron.right", "accept": "checkmark", "back": "arrow.uturn.left",
        "tab_left": "chevron.left.2", "tab_right": "chevron.right.2", "dive": "arrow.down.to.line",
        "surface": "arrow.up.to.line", "crouch": "figure.walk", "pedal": "bicycle",
        "switch_character": "person.2.fill", "special_ability": "bolt.circle.fill", "interact": "hand.point.right.fill",
        "detonate": "burst.fill", "zoom_in": "plus.magnifyingglass", "zoom_out": "minus.magnifyingglass",
        "weapon_prev": "chevron.left", "weapon_next": "chevron.right", "throttle_up": "chevron.up.2",
        "throttle_down": "chevron.down.2", "yaw_left": "rotate.left.fill", "yaw_right": "rotate.right.fill",
        "cheat": "puzzlepiece.extension.fill", "speaker": "speaker.wave.2.fill", "speaker_muted": "speaker.slash.fill",
        "mic": "mic.fill", "mic_muted": "mic.slash.fill", "buy_weapon": "cart.fill",
        "tow_hook": "car.side.rear.tow.hitch.fill", "tow_arm_up": "arrow.up.to.line", "tow_arm_down": "arrow.down.to.line", "roof": "convertible.side.arrowtriangle.up.arrowtriangle.down.fill",
        "steer_left": "arrowtriangle.left.fill", "steer_right": "arrowtriangle.right.fill",
        "phone_option": "circle.grid.3x3.fill", "taxi_hurry": "hare.fill", "taxi_stop": "stop.fill",
        "missile": "flame.fill"]
    /// iOS 15-17 have no tow hitch or convertible symbols (they came in iOS 18).
    static let olderSymbol: [String: String] = [
        "tow_hook": "truck.pickup.side.fill", "roof": "car.side.arrowtriangle.up.arrowtriangle.down.fill"]
    /// Model name hashes (joaat) from the game's vehicles.meta: tow trucks, whose hook releases
    /// with INPUT_VEH_GRAPPLING_HOOK, and cars with an animated convertible roof (animConvRoofDictName).
    /// (From GTA V Port 1.3.2-1.3.3.)
    static let towTrucks: Set<UInt32> = [0xB12314E0 /* towtruck */, 0xE5A2D6C6 /* towtruck2 */]
    static let taxi: UInt32 = 0xC703DB5F
    static let convertibles: Set<UInt32> = [
        0xA8E38B01 /* ninef2 */, 0x7B8AB45F /* carbonizzare */, 0x13B57D8A /* cogcabrio */, 0xFAAD85EE /* felon2 */,
        0xB9CB3B69 /* issi2 */, 0x679450AF /* rapidgt2 */, 0x3412AE2D /* sentinel2 */, 0xB8E2AE18 /* zion2 */,
        0x16E478C1 /* surano */, 0x5B42A5C4 /* tornado2 */]
}

/// One on-screen control: a glyph in a circle (or a rounded pedal), no caption.
final class ControlButton: UIView {
    let name: String
    var isPedal = false
    /// A finger already down may slide onto this control (pedals).
    var slideTarget = false
    private let icon = UIImageView()
    private let controllerLabel = UILabel()
    private var controllerCaption: String?
    private var controllerAppearance = TouchButtonAppearance.icons
    private let halo = CAShapeLayer()
    private let ring = CAShapeLayer()
    private let progress = CAShapeLayer()
    private(set) var pressed = false
    var active = false { didSet { if active != oldValue { updateAppearance() } } }
    private var currentIcon: String?

    init(_ name: String, icon iconName: String, label: String) {
        self.name = name
        super.init(frame: .zero)
        isUserInteractionEnabled = false
        isAccessibilityElement = true
        accessibilityLabel = L10n.text(label)
        accessibilityTraits = .button
        layer.shadowColor = UIColor.black.cgColor
        layer.shadowOpacity = 0.25
        layer.shadowRadius = 6
        layer.shadowOffset = .zero
        for shape in [halo, ring, progress] { shape.fillColor = nil; layer.addSublayer(shape) }
        halo.strokeColor = UIColor.white.withAlphaComponent(0.35).cgColor
        halo.lineWidth = 2
        halo.opacity = 0
        ring.strokeColor = ControlStyle.accent.cgColor
        ring.lineWidth = 2.5
        progress.strokeColor = UIColor.white.withAlphaComponent(0.9).cgColor
        progress.lineWidth = 3
        progress.lineCap = .round
        progress.strokeEnd = 0
        icon.contentMode = .scaleAspectFit
        addSubview(icon)
        controllerLabel.isAccessibilityElement = false
        controllerLabel.textAlignment = .center
        controllerLabel.font = .systemFont(ofSize: 28, weight: .bold)
        controllerLabel.adjustsFontSizeToFitWidth = true
        controllerLabel.minimumScaleFactor = 0.45
        controllerLabel.isHidden = true
        addSubview(controllerLabel)
        setIcon(iconName)
        updateAppearance()
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    func setIcon(_ iconName: String) {
        guard iconName != currentIcon else { return }
        currentIcon = iconName
        let image = UIImage(named: "icon_" + iconName)
            ?? UIImage(systemName: ControlStyle.fallbackSymbol[iconName] ?? "circle", withConfiguration: UIImage.SymbolConfiguration(weight: .bold))
            ?? UIImage(systemName: ControlStyle.olderSymbol[iconName] ?? "circle", withConfiguration: UIImage.SymbolConfiguration(weight: .bold))
        icon.image = image?.withRenderingMode(.alwaysTemplate)
    }

    func setControllerCaption(_ caption: String?, appearance: TouchButtonAppearance) {
        guard caption != controllerCaption || appearance != controllerAppearance else { return }
        controllerCaption = caption
        controllerAppearance = appearance
        controllerLabel.text = caption
        controllerLabel.font = .systemFont(ofSize: (caption?.count ?? 0) > 3 ? 18 : 28, weight: .bold)
        controllerLabel.isHidden = caption == nil
        icon.isHidden = caption != nil
        accessibilityHint = caption.map { appearance.accessibilityHint(for: $0) }
        updateAppearance()
        setNeedsLayout()
    }

    private var faceColor: UIColor {
        switch controllerCaption {
        case "A": return .systemGreen
        case "B": return .systemRed
        case "X": return .systemBlue
        case "Y": return .systemYellow
        case "×": return .systemBlue
        case "○": return .systemRed
        case "□": return .systemPink
        case "△": return .systemGreen
        default: return .white
        }
    }

    private var cornerRadius: CGFloat { isPedal ? 18 : bounds.width / 2 }

    override func layoutSubviews() {
        super.layoutSubviews()
        layer.cornerRadius = cornerRadius
        let side = min(bounds.width, bounds.height) * 0.56
        icon.bounds.size = CGSize(width: side, height: side)
        icon.center = CGPoint(x: bounds.midX, y: bounds.midY)
        controllerLabel.frame = bounds.insetBy(dx: bounds.width * 0.08, dy: bounds.height * 0.15)
        let path = UIBezierPath(roundedRect: bounds, cornerRadius: cornerRadius).cgPath
        halo.path = UIBezierPath(roundedRect: bounds.insetBy(dx: -5, dy: -5), cornerRadius: cornerRadius + 5).cgPath
        ring.path = path
        progress.path = path
        layer.shadowPath = path
    }

    private func updateAppearance() {
        let base = UIColor.black.withAlphaComponent(UIAccessibility.isReduceTransparencyEnabled ? 0.7 : 0.3)
        backgroundColor = pressed ? UIColor.white.withAlphaComponent(0.85) : base
        layer.borderWidth = 1
        layer.borderColor = UIColor.white.withAlphaComponent(pressed ? 0.9 : 0.28).cgColor
        icon.tintColor = pressed ? UIColor.black.withAlphaComponent(0.9) : UIColor.white.withAlphaComponent(0.92)
        if controllerCaption != nil {
            controllerLabel.textColor = pressed ? .black : faceColor
            layer.borderColor = faceColor.withAlphaComponent(pressed ? 0.95 : 0.6).cgColor
            layer.borderWidth = 1.5
        }
        ring.opacity = active && !pressed ? 1 : 0
        accessibilityValue = pressed ? "Held" : active ? L10n.text("On") : nil
    }

    func setPressed(_ value: Bool) {
        guard value != pressed else { return }
        pressed = value
        updateAppearance()
        let reduce = UIAccessibility.isReduceMotionEnabled
        UIView.animate(withDuration: reduce ? 0 : 0.12, delay: 0, usingSpringWithDamping: 0.7, initialSpringVelocity: 0,
                       options: [.allowUserInteraction, .beginFromCurrentState]) {
            self.transform = value && !reduce ? CGAffineTransform(scaleX: 0.94, y: 0.94) : .identity
        }
        if value {
            halo.removeAllAnimations(); halo.opacity = 1
        } else {
            let fade = CABasicAnimation(keyPath: "opacity"); fade.fromValue = 1; fade.toValue = 0; fade.duration = 0.2
            halo.add(fade, forKey: "fade"); halo.opacity = 0
        }
    }

    /// 0...1 ring around the edge, e.g. hold-to-exit in the air.
    func setProgress(_ value: CGFloat) {
        CATransaction.begin(); CATransaction.setDisableActions(true)
        progress.strokeEnd = max(0, min(1, value))
        CATransaction.commit()
    }

    func contains(point: CGPoint, slop: CGFloat) -> Bool {
        frame.insetBy(dx: -slop, dy: -slop).contains(point)
    }
}

/// Ring and knob drawn where a thumb lands; hidden otherwise.
final class FloatingStick: UIView {
    private let base = UIView()
    private let knob = UIView()
    private let sprintHalo = UIView()
    var baseDiameter: CGFloat = 120
    var travel: CGFloat = 48
    private(set) var origin = CGPoint.zero
    private(set) var value = CGPoint.zero
    var sprinting = false { didSet { if sprinting != oldValue { sprintHalo.alpha = sprinting ? 1 : 0 } } }

    override init(frame: CGRect) {
        super.init(frame: frame)
        isUserInteractionEnabled = false
        for view in [sprintHalo, base, knob] { addSubview(view) }
        base.layer.borderWidth = 2
        base.layer.borderColor = UIColor.white.withAlphaComponent(0.3).cgColor
        base.backgroundColor = UIColor.black.withAlphaComponent(0.12)
        sprintHalo.layer.borderWidth = 3
        sprintHalo.layer.borderColor = ControlStyle.accent.withAlphaComponent(0.85).cgColor
        sprintHalo.alpha = 0
        knob.backgroundColor = UIColor.white.withAlphaComponent(0.45)
        knob.layer.shadowColor = UIColor.black.cgColor
        knob.layer.shadowOpacity = 0.25
        knob.layer.shadowRadius = 6
        alpha = 0
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    func begin(at point: CGPoint) {
        origin = point
        value = .zero
        layoutParts()
        UIView.animate(withDuration: 0.08) { self.alpha = 1 }
    }
    /// The base stays where the thumb landed until it lifts; dragging past
    /// the edge holds full deflection in that direction.
    func move(to point: CGPoint, horizontalOnly: Bool = false) {
        let dx = point.x - origin.x, dy = horizontalOnly ? 0 : point.y - origin.y
        let length = max(1, hypot(dx, dy) / travel)
        value = CGPoint(x: dx / travel / length, y: -dy / travel / length)
        layoutParts()
    }
    func end() {
        value = .zero
        sprinting = false
        UIView.animate(withDuration: 0.15) { self.alpha = 0 }
    }
    private func layoutParts() {
        base.bounds.size = CGSize(width: baseDiameter, height: baseDiameter)
        base.layer.cornerRadius = baseDiameter / 2
        base.center = origin
        sprintHalo.bounds.size = CGSize(width: baseDiameter + 12, height: baseDiameter + 12)
        sprintHalo.layer.cornerRadius = (baseDiameter + 12) / 2
        sprintHalo.center = origin
        let knobSize = baseDiameter * 0.43
        knob.bounds.size = CGSize(width: knobSize, height: knobSize)
        knob.layer.cornerRadius = knobSize / 2
        knob.center = CGPoint(x: origin.x + value.x * travel, y: origin.y - value.y * travel)
    }
}

/// Responsive pinch-to-zoom accumulator for pause map
private struct PinchTracker {
    private var remainder: Double = 0
    mutating func reset() { remainder = 0 }
    mutating func update(before: Double, after: Double) -> Int32 {
        guard before >= 10, after >= 10 else { return 0 }
        remainder += log(after / before) / log(1.08)
        let steps = Int32(trunc(remainder))
        remainder -= Double(steps)
        return steps
    }
}

/// The touch overlay. Every finger gets one role when it lands (a button, the
/// move stick, the look pad, ...), and the result is reported as a game
/// controller so the engine's own controller handling (assisted aim, analog
/// driving) applies. The layout follows the player's state automatically;
/// there is no manual mode switch.
final class TouchControlsView: UIView {
    var inputChanged: (() -> Void)?
    /// In the layout editor: controls are shown but not played, and hidden controls stay visible (dimmed).
    var editing = false
    /// The control selected in the layout editor (drawn with a highlight).
    weak var highlighted: ControlButton? { didSet { updateHighlight() } }
    var openSettings: (() -> Void)?
    var openCheat: (() -> Void)?
    var onVoiceMicChanged: ((Bool) -> Void)?
    /// A line for the log when the game state behind the situational buttons changes.
    var hintsChanged: ((String) -> Void)?
    private(set) var context = ControlContext.onFoot

    private enum Role {
        case button(ControlButton)
        case moveStick, look, steer
        /// Radio: a tap is the next station; held, the wheel opens and the same finger picks one.
        case radioWheel(start: CGPoint, current: CGPoint, since: CFTimeInterval)
        case weaponWheel(start: CGPoint, current: CGPoint)
        /// Character switch: D-pad down held, the same finger points at Michael, Franklin or Trevor.
        case characterWheel(start: CGPoint, current: CGPoint)
        case fireLook(ControlButton)
        case mapPointer(start: CGPoint, current: CGPoint, dragging: Bool)
    }
    private var roles: [ObjectIdentifier: Role] = [:]
    private var mapPinch = PinchTracker()
    private var lastPinchDist: Double?

    private let moveStick = FloatingStick()
    private let lookStick = FloatingStick()
    private var dragCamera = DragCamera()
    private var sprintSince: CFTimeInterval?
    private var aimToggled = false
    private var lastFireTime: CFTimeInterval = 0
    private var fireStartedAt: CFTimeInterval?
    /// Buttons sent for a set time (special ability, radio taps), so the game sees every tap.
    private var pulses: [(buttons: PadButtons, until: CFTimeInterval)] = []
    /// When each pad bit was last pressed: every press lasts at least `minimumPress`.
    private var pressedAt: [UInt32: CFTimeInterval] = [:]
    private var lastHeld = PadButtons()
    private var radioDirection: (Float, Float)?
    private static let minimumPress: CFTimeInterval = 0.07
    /// From the engine (PGReadControlHints): which situational buttons apply right now.
    private var hints = PGControlHints()
    private var exitHoldStart: CFTimeInterval?
    private var phoneDock = false
    private var lastDockInput: CFTimeInterval = 0
    /// Game state (PGGameStatus): the phone is out on screen, and a full-screen prompt waits for
    /// Accept/Back (player control off outside cutscenes, e.g. Mission failed, or a warning screen).
    private var gamePhoneOut = false
    private var phoneRequestedAt: CFTimeInterval?
    private var promptSince: CFTimeInterval?
    private var promptActive = false
    /// D-pad down: Story character selector and multiplayer player list.
    var characterSwitchEnabled = false { didSet { if characterSwitchEnabled != oldValue { updateVisibility() } } }
    private var pedalClock: Double = 0
    private let haptics = UIImpactFeedbackGenerator(style: .light)

    // On foot
    private let fire = ControlButton("fire", icon: "fire", label: "Fire")
    private let aim = ControlButton("aim", icon: "aim", label: "Aim")
    private let leftFire = ControlButton("leftFire", icon: "fire", label: "Fire, left hand")
    private let leftAim = ControlButton("leftAim", icon: "aim", label: "Aim, left hand")
    private let jump = ControlButton("jump", icon: "jump", label: "Jump")
    private let enter = ControlButton("enter", icon: "enter_exit", label: "Enter vehicle")
    private let weapons = ControlButton("weapons", icon: "weapons", label: "Weapon wheel")
    private let reload = ControlButton("reload", icon: "reload", label: "Reload")
    private let cover = ControlButton("cover", icon: "cover", label: "Take cover")
    private let crouch = ControlButton("crouch", icon: "crouch", label: "Stealth")
    private let switcher = ControlButton("switchCharacter", icon: "switch_character", label: "Characters / players")
    private let special = ControlButton("special", icon: "special_ability", label: "Special ability")
    private let interact = ControlButton("interact", icon: "interact", label: "Interact")
    private let detonate = ControlButton("detonate", icon: "detonate", label: "Detonate sticky bombs")
    private let zoomIn = ControlButton("zoomIn", icon: "zoom_in", label: "Zoom in")
    private let zoomOut = ControlButton("zoomOut", icon: "zoom_out", label: "Zoom out")
    private let weaponPrev = ControlButton("weaponPrev", icon: "weapon_prev", label: "Previous weapon in this slot")
    private let weaponNext = ControlButton("weaponNext", icon: "weapon_next", label: "Next weapon in this slot")
    // Vehicles
    private let gas = ControlButton("gas", icon: "gas", label: "Gas")
    private let brake = ControlButton("brake", icon: "brake", label: "Brake and reverse")
    private let handbrake = ControlButton("handbrake", icon: "handbrake", label: "Handbrake")
    private let driveBy = ControlButton("driveBy", icon: "fire", label: "Aim and shoot from vehicle")
    private let horn = ControlButton("horn", icon: "horn", label: "Horn")
    private let lookBack = ControlButton("lookBack", icon: "look_back", label: "Look behind")
    private let vehicleWeapon = ControlButton("vehicleWeapon", icon: "vehicle_weapon", label: "Next vehicle weapon")
    private let dive = ControlButton("dive", icon: "dive", label: "Dive")
    private let surface = ControlButton("surface", icon: "surface", label: "Surface")
    // Settings › Touch controls › Steering buttons: left/right buttons instead of the steering stick.
    private let steerLeft = ControlButton("steer_left", icon: "steer_left", label: "Steer Left")
    private let steerRight = ControlButton("steer_right", icon: "steer_right", label: "Steer Right")
    // Tow trucks and convertibles (the hook and the roof are D-pad right, like the headlights).
    private let towHook = ControlButton("towHook", icon: "tow_hook", label: "Release Tow Hook")
    private let roof = ControlButton("roof", icon: "roof", label: "Open / Close Roof")
    private let towArmUp = ControlButton("towArmUp", icon: "tow_arm_up", label: "Raise Tow Arm")
    private let towArmDown = ControlButton("towArmDown", icon: "tow_arm_down", label: "Lower Tow Arm")
    // Aircraft
    private let airFire = ControlButton("airFire", icon: "special", label: "Fire aircraft weapon")
    private let gear = ControlButton("gear", icon: "landing_gear", label: "Landing gear")
    private let throttleUp = ControlButton("throttleUp", icon: "throttle_up", label: "Throttle up, climb")
    private let throttleDown = ControlButton("throttleDown", icon: "throttle_down", label: "Throttle down, descend")
    private let yawLeft = ControlButton("yawLeft", icon: "yaw_left", label: "Rudder left")
    private let yawRight = ControlButton("yawRight", icon: "yaw_right", label: "Rudder right")
    // Utility bar
    private let camera = ControlButton("camera", icon: "camera", label: "Change camera")
    private let phone = ControlButton("phone", icon: "phone", label: "Phone")
    private let pause = ControlButton("pause", icon: "pause", label: "Pause menu")
    private let settings = ControlButton("settings", icon: "settings", label: L10n.text("Settings"))
    private let cheat = ControlButton("cheat", icon: "cheat", label: L10n.text("Mod Manager"))
    private let speaker = ControlButton("speaker", icon: "speaker", label: "Loa Voice Chat")
    private let mic = ControlButton("mic", icon: "mic", label: "Micro Voice Chat")
    private let buyWeapon = ControlButton("buyWeapon", icon: "buy_weapon", label: "Interact: buy weapon · police arrest · medic heal")
    private let lights = ControlButton("lights", icon: "lights", label: "Headlights")
    private let radio = ControlButton("radio", icon: "radio", label: "Radio")
    // Menu and phone dock
    private let up = ControlButton("up", icon: "up", label: "Up")
    private let down = ControlButton("down", icon: "down", label: "Down")
    private let left = ControlButton("left", icon: "left", label: "Left")
    private let right = ControlButton("right", icon: "right", label: "Right")
    private let accept = ControlButton("accept", icon: "accept", label: "Select")
    private let back = ControlButton("back", icon: "back", label: L10n.text("Back"))
    private let tabLeft = ControlButton("tabLeft", icon: "tab_left", label: "Previous tab")
    private let tabRight = ControlButton("tabRight", icon: "tab_right", label: "Next tab")
    // The phone's X: keypad for a custom number (cheats) and the phone's other options.
    private let phoneOption = ControlButton("phone_option", icon: "phone_option", label: "Phone Keypad")
    // Taxi ride (Story mode): X hurries the driver, B stops the taxi.
    private let taxiHurry = ControlButton("taxi_hurry", icon: "taxi_hurry", label: "Drive Faster")
    private let taxiStop = ControlButton("taxi_stop", icon: "taxi_stop", label: "Stop Taxi")

    private var allButtons: [ControlButton] {
        [fire, aim, leftFire, leftAim, jump, enter, weapons, reload, cover, crouch, switcher, special, interact, detonate, zoomIn, zoomOut,
         weaponPrev, weaponNext, gas, brake, handbrake, steerLeft, steerRight, driveBy, horn, lookBack,
         vehicleWeapon, towHook, towArmUp, towArmDown, roof, dive, surface, airFire, gear, throttleUp, throttleDown, yawLeft, yawRight, camera, phone, pause, settings, cheat,
         speaker, mic, buyWeapon, lights, radio,
         up, down, left, right, accept, back, phoneOption, taxiHurry, taxiStop, tabLeft, tabRight]
    }
    private var visible: [ControlButton] = []

    override init(frame: CGRect) {
        super.init(frame: frame)
        isMultipleTouchEnabled = true
        addSubview(moveStick)
        addSubview(lookStick)
        for button in allButtons { button.alpha = 0; addSubview(button) }
        for pedal in [gas, brake, dive, surface, throttleUp, throttleDown] { pedal.isPedal = true }
        for button in [gas, brake, handbrake, dive, surface, throttleUp, throttleDown] { button.slideTarget = true }
        updateVisibility()
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    // MARK: Context

    func updateContext(vehicle: UInt32, pauseMenu: Bool) {
        let next = ControlContext(vehicle: vehicle, pauseMenu: pauseMenu)
        guard next != context else { return }
        // A held action must not turn into a different action on entry/exit,
        // but a thumb on the move stick keeps steering the new vehicle.
        let carryStick = !next.flying && next != .menu && (next.driving != context.driving)
        reset(publish: false, keepStickFinger: carryStick)
        context = next
        if next == .menu || !gamePhoneOut { phoneDock = false }
        updateVisibility()
        setNeedsLayout()
    }

    private func computeVisible() -> [ControlButton] {
        var list = baseVisible()
        let playing = !phoneDock && !promptActive && context != .menu
        if characterSwitchEnabled, playing { list.append(switcher) }
        // In the layout editor every situational button shows, so it can be placed.
        if editing && !context.flying {
            list += context == .onFoot ? [special, interact, detonate, zoomIn, zoomOut, weaponPrev, weaponNext, leftFire, leftAim] : [special, interact, detonate, towHook, towArmUp, towArmDown, roof]
            return list
        }
        // Situational buttons, shown only while they do something (engine state, PGReadControlHints).
        if playing && !context.flying {
            if hints.specialShown && !aimActive { list.append(special) }
            if hints.canDetonate { list.append(detonate) }
            // "Press D-pad right to ..." prompts come in vehicles too (Los Santos Customs, garages).
            if hints.helpContext && !aimActive { list.append(interact) }
            if context == .onFoot && aimActive { list += [zoomIn, zoomOut] }
            if context == .onFoot && has(isWeaponWheel) { list += [weaponPrev, weaponNext] }
            // The hook and the roof are D-pad right like the headlights, so they get their own buttons.
            if context == .car && ControlStyle.towTrucks.contains(hints.vehicleModel) { list += [towHook, towArmUp, towArmDown] }
            if context == .car && ControlStyle.convertibles.contains(hints.vehicleModel) { list.append(roof) }
        }
        return list
    }

    /// Engine state for the situational buttons; called every frame.
    func updateHints(_ next: PGControlHints) {
        let changed = next.specialShown != hints.specialShown || next.canDetonate != hints.canDetonate || next.helpContext != hints.helpContext
            || next.vehicleModel != hints.vehicleModel || next.passenger != hints.passenger || next.taxiMenu != hints.taxiMenu
        if changed || next.specialReady != hints.specialReady || next.specialActive != hints.specialActive || next.radioWheelOpen != hints.radioWheelOpen {
            hintsChanged?("Control hints: special \(next.specialShown ? (next.specialActive ? "active" : next.specialReady ? "ready" : "charging") : "none") \(Int(next.specialFill * 100))%, detonate \(next.canDetonate), help \(next.helpShown ? (next.helpContext ? "asks for interact" : "shown") : "none"), radio wheel \(next.radioWheelOpen ? "open" : "closed")")
        }
        hints = next
        special.active = next.specialActive
        special.setProgress(next.specialActive ? 0 : CGFloat(next.specialFill))
        if changed { updateVisibility() }
    }
    /// A taxi ride with the destination menu (the taxiservice script runs, the player is a passenger).
    private var taxiRide: Bool { hints.passenger && hints.taxiMenu && hints.vehicleModel == ControlStyle.taxi }
    private func baseVisible() -> [ControlButton] {
        let steering: [ControlButton] = GameSettings.shared.steeringButtons ? [steerLeft, steerRight] : []
        let online = MugoatOnlineEnabled()
        let onlineButtons: [ControlButton] = [cheat] + (online ? [speaker, mic, buyWeapon] : [])
        let utility: [ControlButton] = context.driving ? [radio, lights, camera, phone, pause, settings] + onlineButtons : [camera, phone, pause, settings] + onlineButtons
        if context == .menu { return [pause, settings] + onlineButtons + [up, down, left, right, accept, back, tabLeft, tabRight] }
        if phoneDock { return [camera, phone, pause, settings] + onlineButtons + [up, down, left, right, accept, back, phoneOption] }
        // A prompt (Mission failed, warning screens) waits for Accept/Back; play controls do nothing then.
        // Shop menus (Ammu-Nation, clothes, Los Santos Customs) also lock player control and need the
        // D-pad to move through the items.
        if promptActive && !editing { return [camera, pause, settings] + onlineButtons + [up, down, left, right, accept, back] }
        // A taxi ride: the destination menu takes left/right to change and Select to choose.
        if taxiRide && !editing {
            return [camera, phone, pause, settings] + onlineButtons + [radio, left, right, accept, taxiHurry, taxiStop, enter, lookBack]
        }
        switch context {
        case .onFoot:
            return aimActive ? utility + [fire, aim, enter, weapons, reload, cover, leftFire, leftAim]
                             : utility + [fire, aim, jump, enter, weapons, reload, cover, crouch, leftAim]
        case .car, .boat:
            return utility + [gas, brake, handbrake, enter, driveBy, horn, lookBack, vehicleWeapon] + steering
        case .bike:
            return utility + [gas, brake, handbrake, enter, driveBy, horn, lookBack] + steering
        case .bicycle:
            return [camera, phone, pause, settings] + onlineButtons + [radio, gas, brake, handbrake, enter, lookBack] + steering
        case .sub:
            return utility + [gas, brake, enter, dive, surface, lookBack] + steering
        // Aircraft: the weapon button switches cannon/missiles directly (PGNextAircraftWeapon).
        case .heli:
            return utility + [airFire, vehicleWeapon, enter, throttleUp, throttleDown, yawLeft, yawRight]
        case .plane:
            return utility + [airFire, vehicleWeapon, gear, enter, throttleUp, throttleDown, yawLeft, yawRight]
        case .menu:
            return []
        }
    }

    /// Game state from the engine (PGGameStatus bits: 1 control off, 2 phone out, 4 cutscene,
    /// 8 warning screen, 16 no player).
    func updateGameState(_ status: UInt32, now: CFTimeInterval = CACurrentMediaTime()) {
        let phoneOut = status & 2 != 0
        if phoneOut != gamePhoneOut {
            gamePhoneOut = phoneOut
            if phoneOut { phoneDock = true; phoneRequestedAt = nil; lastDockInput = now }
            else if phoneDock { phoneDock = false }
            if context != .menu { reset(publish: false) }
            updateVisibility()
        }
        // Accept/Back prompt: player control off outside cutscenes (Mission failed and similar
        // screens), or a warning screen. Held for a moment so brief control locks don't flicker.
        let wanted = status & 16 == 0 && ((status & 1 != 0 && status & 4 == 0) || status & 8 != 0)
        if wanted { if promptSince == nil { promptSince = now } } else { promptSince = nil }
        let show = wanted && now - (promptSince ?? now) > 0.6
        if show != promptActive {
            promptActive = show
            reset(publish: false)
            updateVisibility()
        }
    }
    var showingPrompt: Bool { promptActive }

    /// The saved-layout group for the current controls: on foot, or any vehicle.
    var layoutGroup: String { context == .onFoot ? "foot" : "vehicle" }
    private func hiddenByPlayer(_ button: ControlButton) -> Bool {
        context != .menu && !phoneDock && (ControlsLayout.entry(group: layoutGroup, name: button.name)?.hidden ?? false)
    }

    func updateVisibility() {
        visible = computeVisible().filter { editing || !hiddenByPlayer($0) }
        let shown = Set(visible.map(ObjectIdentifier.init))
        let opacity = CGFloat(GameSettings.shared.controlOpacity)
        let appearance = TouchButtonAppearance.read()
        for button in allButtons {
            button.setControllerCaption(appearance.caption(for: button.name, bicycle: context == .bicycle, phoneOut: gamePhoneOut), appearance: appearance)
            let isShown = shown.contains(ObjectIdentifier(button))
            var target: CGFloat = isShown ? (button === fire || button === gas ? min(1, opacity + 0.1) : opacity) : 0
            if editing, isShown, hiddenByPlayer(button) { target = 0.3 }
            if abs(button.alpha - target) > 0.01 {
                UIView.animate(withDuration: UIAccessibility.isReduceMotionEnabled ? 0 : 0.15) { button.alpha = target }
            }
            button.isAccessibilityElement = isShown
        }
        weapons.setIcon("weapons")
        enter.accessibilityLabel = context == .onFoot ? "Enter vehicle" : context.flying ? "Hold to exit aircraft" : "Exit vehicle"
        gas.setIcon(context == .bicycle ? "pedal" : "gas")
        vehicleWeapon.setIcon(context.flying ? "missile" : "vehicle_weapon")
        vehicleWeapon.accessibilityLabel = context.flying ? "Switch aircraft weapons (missiles / cannons)" : "Next vehicle weapon"
        if MugoatOnlineEnabled() {
            let spkOn = MugoatVoiceIsSpeakerEnabled()
            speaker.setIcon(spkOn ? "speaker" : "speaker_muted")
            speaker.active = spkOn
            let micOn = MugoatVoiceIsMicEnabled()
            mic.setIcon(micOn ? "mic" : "mic_muted")
            mic.active = micOn
        }
        setNeedsLayout()
    }

    private var aimActive: Bool { aimToggled }

    // MARK: Layout

    override func layoutSubviews() {
        super.layoutSubviews()
        let safe = bounds.inset(by: safeAreaInsets)
        guard safe.width > 0, safe.height > 0 else { return }
        let scale = max(0.8, min(1.25, min(safe.width / 832, safe.height / 407))) * CGFloat(GameSettings.shared.controlScale)
        func point(_ fx: CGFloat, _ fy: CGFloat) -> CGPoint { CGPoint(x: safe.minX + fx * safe.width, y: safe.minY + fy * safe.height) }
        func place(_ button: ControlButton, _ fx: CGFloat, _ fy: CGFloat, _ size: CGFloat) {
            let d = max(44, size * scale)
            button.bounds.size = CGSize(width: d, height: d)
            button.center = point(fx, fy)
        }
        func pedal(_ button: ControlButton, _ fx: CGFloat, _ fy: CGFloat, _ w: CGFloat, _ h: CGFloat) {
            button.bounds.size = CGSize(width: w * scale, height: h * scale)
            button.center = point(fx, fy)
        }
        moveStick.frame = bounds
        lookStick.frame = bounds
        lookStick.baseDiameter = 120 * scale; lookStick.travel = 48 * scale
        moveStick.baseDiameter = 120 * scale; moveStick.travel = 48 * scale

        // Utility bar, top centre: rare actions in the hard-to-reach zone.
        let order = [radio, lights, camera, phone, pause, settings, cheat, speaker, mic, buyWeapon]
        let bar = order.filter { visible.contains($0) }
        for (i, button) in bar.enumerated() {
            let offset = (CGFloat(i) - CGFloat(bar.count - 1) / 2) * 54 * scale / safe.width
            place(button, 0.5 + offset, 0.08, 40)
        }

        // On foot: the primary action sits under the resting right thumb.
        place(fire, 0.885, 0.70, 78)
        place(aim, 0.735, 0.76, 62)
        place(jump, 0.80, 0.43, 56)
        place(enter, 0.955, 0.42, 54)
        place(weapons, 0.955, 0.17, 50)
        place(reload, 0.69, 0.50, 50)
        place(cover, 0.60, 0.82, 52)
        place(crouch, 0.58, 0.60, 44)
        place(leftFire, 0.10, 0.36, 58)
        place(leftAim, 0.10, 0.50, 58)
        place(switcher, context.flying ? 0.84 : 0.955, context.flying ? 0.14 : 0.295, 46)
        place(special, 0.86, 0.24, 48)
        place(interact, 0.60, 0.38, 52)
        place(detonate, 0.52, 0.68, 48)
        place(zoomIn, 0.66, 0.24, 44)
        place(zoomOut, 0.74, 0.24, 44)
        // In the middle of the weapon wheel, which the game draws at the centre of the screen.
        let centreX = (bounds.midX - safe.minX) / safe.width, centreY = (bounds.midY - safe.minY) / safe.height
        let gap = 34 * scale / safe.width
        place(weaponPrev, centreX - gap, centreY, 50)
        place(weaponNext, centreX + gap, centreY, 50)

        // Ground vehicles: analog steering on the left, pedals on the right.
        pedal(gas, 0.905, 0.72, 74, 108)
        pedal(brake, 0.775, 0.80, 74, 78)
        place(handbrake, 0.79, 0.52, 56)
        place(driveBy, 0.655, 0.50, 58)
        place(horn, 0.06, 0.36, 46)
        place(lookBack, 0.155, 0.36, 44)
        if !context.flying {
            place(vehicleWeapon, 0.955, 0.17, 48)
        }
        pedal(surface, 0.655, 0.64, 62, 66)
        pedal(dive, 0.655, 0.84, 62, 66)
        place(steerLeft, 0.08, 0.76, 80)
        place(steerRight, 0.215, 0.76, 80)
        place(towHook, 0.655, 0.27, 50)
        place(roof, 0.575, 0.27, 50)
        place(towArmUp, 0.575, 0.27, 46)
        place(towArmDown, 0.495, 0.27, 46)

        // Aircraft: the left stick flies; the right thumb works throttle pedals and the rudder, and
        // anywhere else on the right looks around.
        place(airFire, 0.80, 0.30, 62)
        if context.flying {
            place(vehicleWeapon, 0.935, 0.26, 54)
        }
        place(gear, 0.655, 0.24, 46)
        pedal(throttleUp, 0.905, 0.56, 74, 96)
        pedal(throttleDown, 0.905, 0.85, 74, 64)
        place(yawLeft, 0.655, 0.86, 54)
        place(yawRight, 0.775, 0.86, 54)

        // Menus and the phone: a D-pad on the left, accept/back on the right.
        let stepX = 58 * scale / safe.width, stepY = 58 * scale / safe.height
        place(up, 0.12, 0.70 - stepY, 52)
        place(down, 0.12, 0.70 + stepY, 52)
        place(left, 0.12 - stepX, 0.70, 52)
        place(right, 0.12 + stepX, 0.70, 52)
        place(accept, 0.905, 0.70, 68)
        place(back, 0.765, 0.84, 56)
        place(phoneOption, 0.765, 0.56, 56)
        place(taxiHurry, 0.765, 0.52, 58)
        place(taxiStop, 0.765, 0.84, 58)
        place(tabLeft, 0.05, 0.12, 46)
        place(tabRight, 0.95, 0.12, 46)

        // The player's own layout (Edit controls layout): moved and resized controls. Hit areas
        // follow, since touches test each control's frame.
        if context != .menu && !phoneDock {
            for button in visible {
                guard let entry = ControlsLayout.entry(group: layoutGroup, name: button.name) else { continue }
                let size = button.bounds.size
                button.bounds.size = CGSize(width: max(36, size.width * entry.scale), height: max(36, size.height * entry.scale))
                button.center = point(entry.x, entry.y)
            }
        }
        updateHighlight()
    }

    // MARK: Layout editor support

    private let highlightLayer: CAShapeLayer = {
        let layer = CAShapeLayer()
        layer.fillColor = nil
        layer.strokeColor = UIColor.systemYellow.cgColor
        layer.lineWidth = 3
        layer.lineDashPattern = [6, 4]
        return layer
    }()
    private func updateHighlight() {
        if highlightLayer.superlayer == nil { layer.addSublayer(highlightLayer) }
        guard let button = highlighted, visible.contains(where: { $0 === button }) else { highlightLayer.path = nil; return }
        let frame = button.frame.insetBy(dx: -6, dy: -6)
        highlightLayer.path = UIBezierPath(roundedRect: frame, cornerRadius: button.isPedal ? 22 : frame.width / 2).cgPath
    }
    /// The visible control under a point (layout editor).
    func editableButton(at point: CGPoint) -> ControlButton? { button(at: point) }
    func button(named name: String) -> ControlButton? { allButtons.first { $0.name == name } }
    /// A point as a fraction of the safe area (what the saved layout stores).
    func normalized(_ point: CGPoint) -> CGPoint {
        let safe = bounds.inset(by: safeAreaInsets)
        guard safe.width > 0, safe.height > 0 else { return CGPoint(x: 0.5, y: 0.5) }
        return CGPoint(x: (point.x - safe.minX) / safe.width, y: (point.y - safe.minY) / safe.height)
    }
    func clampedToSafeArea(_ point: CGPoint) -> CGPoint {
        let safe = bounds.inset(by: safeAreaInsets).insetBy(dx: 24, dy: 24)
        return CGPoint(x: min(max(point.x, safe.minX), safe.maxX), y: min(max(point.y, safe.minY), safe.maxY))
    }

    override func hitTest(_ point: CGPoint, with event: UIEvent?) -> UIView? {
        isHidden ? nil : self
    }

    // MARK: Touches

    private func button(at point: CGPoint, slidingOnly: Bool = false) -> ControlButton? {
        // Nearest centre wins where the enlarged hit areas overlap.
        visible.filter { (!slidingOnly || $0.slideTarget) && $0.contains(point: point, slop: $0 === fire || $0.isPedal ? 10 : 4) }
            .min { hypot($0.center.x - point.x, $0.center.y - point.y) < hypot($1.center.x - point.x, $1.center.y - point.y) }
    }

    private func currentMapTouches() -> [(id: ObjectIdentifier, start: CGPoint, current: CGPoint, dragging: Bool)] {
        var list: [(ObjectIdentifier, CGPoint, CGPoint, Bool)] = []
        for (id, role) in roles {
            if case .mapPointer(let s, let c, let d) = role {
                list.append((id, s, c, d))
            }
        }
        return list
    }

    private func sendMenuPointer(at point: CGPoint, buttons: Int32) {
        var rw: Int32 = 0, rh: Int32 = 0
        PGGetRenderSize(&rw, &rh)
        if rw < 320 || rh < 180 { rw = 1280; rh = 720 }
        let boundsSize = bounds.size
        guard boundsSize.width > 0, boundsSize.height > 0 else { return }
        let rx = Int32(clamping: Int((point.x / boundsSize.width) * CGFloat(rw)))
        let ry = Int32(clamping: Int((point.y / boundsSize.height) * CGFloat(rh)))
        PGSetMousePosition(rx, ry, buttons)
    }

    private func has(_ check: (Role) -> Bool) -> Bool { roles.values.contains(where: check) }
    private func isStick(_ role: Role) -> Bool { if case .moveStick = role { return true }; if case .steer = role { return true }; return false }
    private func isWeaponWheel(_ role: Role) -> Bool { if case .weaponWheel = role { return true }; return false }
    private func isLook(_ role: Role) -> Bool { if case .look = role { return true }; return false }

    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
        if editing { return }
        let safe = bounds.inset(by: safeAreaInsets)
        for touch in touches {
            let point = touch.location(in: self)
            let id = ObjectIdentifier(touch)
            let leftZone = point.x < safe.minX + safe.width * 0.45
            if let button = button(at: point) {
                press(button, touch: touch, at: point)
            } else if context == .menu {
                let existing = currentMapTouches()
                if existing.isEmpty {
                    roles[id] = .mapPointer(start: point, current: point, dragging: false)
                    sendMenuPointer(at: point, buttons: 0)
                } else if existing.count == 1 {
                    roles[id] = .mapPointer(start: point, current: point, dragging: false)
                    mapPinch.reset()
                    let other = existing[0].current
                    lastPinchDist = Double(hypot(other.x - point.x, other.y - point.y))
                    let center = CGPoint(x: (other.x + point.x) / 2, y: (other.y + point.y) / 2)
                    sendMenuPointer(at: center, buttons: 0)
                }
            } else if phoneDock {
                if !has(isLook) { roles[id] = .look; lookStick.begin(at: point) }
            } else if context.flying, leftZone {
                if !has(isStick) { roles[id] = .moveStick; moveStick.begin(at: point) }
            } else if leftZone, context.driving, GameSettings.shared.steeringButtons {
                // Steering buttons replace the steering stick; the rest of the left side does nothing.
            } else if leftZone, point.y > safe.minY + safe.height * 0.2, !has(isStick) {
                roles[id] = context.driving ? .steer : .moveStick
                moveStick.begin(at: point)
            } else if !has(isLook) {
                roles[id] = .look
                dragCamera.begin(id, at: point)
            }
        }
        publish()
    }

    private func press(_ button: ControlButton, touch: UITouch, at point: CGPoint) {
        let id = ObjectIdentifier(touch)
        let now = CACurrentMediaTime()
        haptics.impactOccurred(intensity: 0.6)
        button.setPressed(true)
        roles[id] = .button(button)
        defer { if case .fireLook = roles[id] { dragCamera.begin(id, at: point) } }
        switch button {
        case weapons:
            roles[id] = .weaponWheel(start: point, current: point)
            updateVisibility()
        case vehicleWeapon where context.flying:
            // Cycle aircraft weapons: send .x (Square/X) to GTA V's vehicle weapon manager,
            // with script fallback via PGNextAircraftWeapon().
            pulse(.x, for: 0.15)
            PGNextAircraftWeapon()
        case roof:
            // INPUT_VEH_ROOF is D-pad right held (a short press is the headlights).
            pulse(.right, for: 0.8)
        case radio where context.driving:
            roles[id] = .radioWheel(start: point, current: point, since: now)
        case special:
            // L3 + R3 together, fresh presses within the game's 100 ms window; again to stop.
            pulse([.l3, .r3], for: 0.13)
        case switcher:
            roles[id] = .characterWheel(start: point, current: point)
        case fire, driveBy:
            roles[id] = .fireLook(button)
            fireStartedAt = now
            lastFireTime = now
        case leftFire:
            roles[id] = .fireLook(button)
            lastFireTime = now
        case aim:
            // Aim is a toggle, so the same thumb is free for Fire. Keeping
            // the thumb down and dragging aims, like dragging from Fire.
            aimToggled.toggle()
            aim.active = aimToggled
            leftAim.active = aimToggled
            roles[id] = .fireLook(button)
            updateVisibility()
        case leftAim:
            aimToggled.toggle()
            aim.active = aimToggled
            leftAim.active = aimToggled
            roles[id] = .button(button)
            updateVisibility()
        case enter where context.flying:
            exitHoldStart = now
        case phone:
            if gamePhoneOut {
                // The phone is out: this button now puts it away (Back), the dock follows the game.
                phoneRequestedAt = nil
            } else {
                phoneDock.toggle()
                phoneRequestedAt = phoneDock ? now : nil
            }
            lastDockInput = now
            updateVisibility()
        case settings:
            DispatchQueue.main.async { self.openSettings?() }
        case cheat:
            DispatchQueue.main.async { self.openCheat?() }
        case speaker:
            let enabled = !MugoatVoiceIsSpeakerEnabled()
            MugoatVoiceSetSpeakerEnabled(enabled)
            speaker.setIcon(enabled ? "speaker" : "speaker_muted")
            speaker.active = enabled
        case mic:
            let enabled = !MugoatVoiceIsMicEnabled()
            MugoatVoiceSetMicEnabled(enabled)
            mic.setIcon(enabled ? "mic" : "mic_muted")
            mic.active = enabled
            DispatchQueue.main.async { self.onVoiceMicChanged?(enabled) }
        case buyWeapon:
            MugoatTriggerAmmuBuy()
        case up, down, left, right, accept, back:
            lastDockInput = now
        default:
            break
        }
    }

    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent?) {
        for touch in touches {
            let id = ObjectIdentifier(touch)
            guard let role = roles[id] else { continue }
            let point = touch.location(in: self)
            switch role {
            case .moveStick:
                moveStick.move(to: point)
            case .steer:
                // Up/down tilts a car in the air and leans a bike.
                moveStick.move(to: point)
            case .radioWheel(let start, _, let since):
                roles[id] = .radioWheel(start: start, current: point, since: since)
            case .look:
                if context == .menu || phoneDock { lookStick.move(to: point) }
                else { dragCamera.move(id, to: point) }
            case .fireLook:
                dragCamera.move(id, to: point)
            case .weaponWheel(let start, _):
                roles[id] = .weaponWheel(start: start, current: point)
            case .characterWheel(let start, _):
                roles[id] = .characterWheel(start: start, current: point)
            case .mapPointer(let start, _, var dragging):
                let mapTouches = currentMapTouches()
                if mapTouches.count >= 2 {
                    let pts = mapTouches.map { $0.id == id ? point : $0.current }
                    let dist = Double(hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y))
                    let center = CGPoint(x: (pts[0].x + pts[1].x) / 2, y: (pts[0].y + pts[1].y) / 2)
                    sendMenuPointer(at: center, buttons: 0)
                    if let prev = lastPinchDist {
                        let steps = mapPinch.update(before: prev, after: dist)
                        if steps != 0 {
                            PGMouseWheel(steps)
                        }
                    }
                    lastPinchDist = dist
                    roles[id] = .mapPointer(start: start, current: point, dragging: true)
                } else {
                    let travel = hypot(point.x - start.x, point.y - start.y)
                    if travel > 6 { dragging = true }
                    roles[id] = .mapPointer(start: start, current: point, dragging: dragging)
                    sendMenuPointer(at: point, buttons: dragging ? 1 : 0)
                }
            case .button(let button):
                // Pedals: a finger may roll from one to another without lifting.
                if button.slideTarget, !button.contains(point: point, slop: 10),
                   let next = self.button(at: point, slidingOnly: true), next !== button {
                    button.setPressed(false)
                    next.setPressed(true)
                    haptics.impactOccurred(intensity: 0.4)
                    roles[id] = .button(next)
                }
            }
        }
        publish()
    }

    override func touchesEnded(_ touches: Set<UITouch>, with event: UIEvent?) { finish(touches) }
    override func touchesCancelled(_ touches: Set<UITouch>, with event: UIEvent?) { finish(touches) }

    private func finish(_ touches: Set<UITouch>) {
        for touch in touches {
            guard let role = roles.removeValue(forKey: ObjectIdentifier(touch)) else { continue }
            dragCamera.end(ObjectIdentifier(touch))
            switch role {
            case .moveStick, .steer: moveStick.end(); sprintSince = nil
            case .look: lookStick.end()
            case .weaponWheel: weapons.setPressed(false); updateVisibility()
            case .radioWheel(_, _, let since):
                radio.setPressed(false)
                // Released quickly without picking: a tap, the next station.
                if CACurrentMediaTime() - since < 0.25 { pulse(.left, for: 0.1) }
            case .characterWheel: switcher.setPressed(false)
            case .mapPointer(let start, _, let dragging):
                let remaining = currentMapTouches().filter { $0.id != ObjectIdentifier(touch) }
                if remaining.isEmpty {
                    lastPinchDist = nil
                    mapPinch.reset()
                }
                let pt = touch.location(in: self)
                let travel = hypot(pt.x - start.x, pt.y - start.y)
                if !dragging && travel <= 8 {
                    sendMenuPointer(at: pt, buttons: 1)
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
                        self.sendMenuPointer(at: pt, buttons: 0)
                    }
                } else {
                    sendMenuPointer(at: pt, buttons: 0)
                }
            case .fireLook(let button):
                button.setPressed(false)
                if button === fire || button === driveBy { fireStartedAt = nil }
                if button !== aim && button !== leftAim { lastFireTime = CACurrentMediaTime() }
            case .button(let button):
                button.setPressed(false)
                if button === enter { exitHoldStart = nil; enter.setProgress(0) }
            }
        }
        publish()
    }

    private func publish() { inputChanged?() }

    private func pulse(_ buttons: PadButtons, for duration: CFTimeInterval) {
        pulses.append((buttons, CACurrentMediaTime() + duration))
    }

    func reset(publish: Bool = true, keepStickFinger: Bool = false) {
        for (id, role) in roles {
            switch role {
            case .moveStick, .steer:
                if keepStickFinger { roles[id] = context.driving ? .moveStick : .steer; continue }
                moveStick.end()
            case .button(let button), .fireLook(let button): button.setPressed(false)
            case .radioWheel: radio.setPressed(false)
            case .weaponWheel: weapons.setPressed(false)
            case .characterWheel: switcher.setPressed(false)
            case .look: lookStick.end()
            case .mapPointer: break
            }
            roles[id] = nil
        }
        aimToggled = false; aim.active = false; leftAim.active = false
        lastPinchDist = nil; mapPinch.reset()
        if context == .menu { PGSetMousePosition(0, 0, 0) }
        fireStartedAt = nil; exitHoldStart = nil
        enter.setProgress(0)
        sprintSince = nil; moveStick.sprinting = false
        dragCamera.reset()
        PGTouchCameraEnabled(false)
        if publish { self.publish() }
    }

    // MARK: Output

    /// Whether the player is aiming; gyro aim runs only then by default.
    var aiming: Bool { aimActive || fire.pressed || leftFire.pressed || driveBy.pressed || leftAim.pressed }
    /// Aircraft are flown with the left stick and buttons now; kept for the gyro check.
    var flyingWithRightStick: Bool { false }

    func sendCameraMotion() {
        let available = context != .menu && !phoneDock && !has(isWeaponWheel) &&
            !roles.values.contains { if case .radioWheel = $0 { return true }; if case .characterWheel = $0 { return true }; return false }
        PGTouchCameraEnabled(available)
        let sensitivity = aiming ? GameSettings.shared.aimSensitivity : GameSettings.shared.lookSensitivity
        let delta = dragCamera.motion(sensitivity: sensitivity, invertedY: GameSettings.shared.invertLookY)
        if available { PGTouchCameraDrag(delta.x, delta.y) }
    }

    /// The current controller state. `elapsed` turns finger travel into a
    /// stick deflection, so the camera turns about as far as the finger moves.
    func padState(elapsed: Double) -> PGPadState {
        var state = PGPadState()
        var held = PadButtons()
        let now = CACurrentMediaTime()

        let speed = CGFloat(aimActive ? GameSettings.shared.aimSensitivity : GameSettings.shared.lookSensitivity)
        if context == .menu || phoneDock {
            (state.rightX, state.rightY) = Self.cameraStick(has(isLook) ? lookStick.value : .zero, speed: speed)
        } else {
            // Drag motion is queued separately so UIKit cannot overwrite it
            // before the engine samples pad 0. Gyro/gamepad axes remain here.
            state.rightX = 0; state.rightY = 0
        }

        switch context {
        case .onFoot:
            state.leftX = Float(moveStick.value.x); state.leftY = Float(moveStick.value.y)
            // Sprint: hold the stick at its edge.
            if hypot(moveStick.value.x, moveStick.value.y) > 0.92 {
                if sprintSince == nil { sprintSince = now }
                if now - (sprintSince ?? now) > 0.25 { held.insert(.a); moveStick.sprinting = true }
            } else { sprintSince = nil; moveStick.sprinting = false }
            let firing = fire.pressed || leftFire.pressed
            if firing { lastFireTime = now }
            if aimToggled && moveStick.sprinting {
                aimToggled = false; aim.active = false; leftAim.active = false; updateVisibility()
            }
            let fireAims = GameSettings.shared.fireAlsoAims
            if aimActive || leftAim.pressed || (firing && fireAims) { state.leftTrigger = 1 }
            if firing {
                // When Fire also aims, give the lock-on a moment before the first shot.
                let lockDelay = !aimActive && fireAims && fire.pressed ? 0.09 : 0
                if now - (fireStartedAt ?? 0) >= lockDelay || leftFire.pressed { state.rightTrigger = 1 }
            }
            if jump.pressed { held.insert(.x) }
            if enter.pressed { held.insert(.y) }
            if reload.pressed { held.insert(.b) }
            if cover.pressed { held.insert(.r1) }
            if crouch.pressed { held.insert(.l3) }
            if interact.pressed { held.insert(.right) }
            if zoomIn.pressed { held.insert(.up) }
            if zoomOut.pressed { held.insert(.down) }
            // With the weapon wheel open, D-pad left/right step through the weapons in a slot.
            if weaponPrev.pressed { held.insert(.left) }
            if weaponNext.pressed { held.insert(.right) }
            for role in roles.values {
                guard case .weaponWheel(let start, let current) = role else { continue }
                // Hold the wheel button; the same finger points at a slot.
                held.insert(.l1)
                let d = CGPoint(x: current.x - start.x, y: current.y - start.y), length = hypot(d.x, d.y)
                state.rightX = length > 24 ? Float(d.x / length) : 0
                state.rightY = length > 24 ? Float(-d.y / length) : 0
            }
        case .car, .bike, .bicycle, .boat, .sub:
            let steer = GameSettings.shared.steeringButtons ? CGFloat((steerRight.pressed ? 1 : 0) - (steerLeft.pressed ? 1 : 0)) : moveStick.value.x
            state.leftX = Float(copysign(pow(abs(steer), 1.3), steer))
            let tilt = moveStick.value.y
            if context == .bike || context == .bicycle {
                state.leftY = Float(tilt)
            } else {
                // Cars, boats and subs: up/down pitches in the air or underwater. A wide dead zone keeps
                // sloppy steering from tilting.
                state.leftY = abs(tilt) < 0.35 ? 0 : Float(copysign((abs(tilt) - 0.35) / 0.65, tilt))
            }
            if context == .bicycle {
                // Pedal by tapping A at a steady cadence while Gas is held.
                if gas.pressed {
                    pedalClock += elapsed
                    if pedalClock.truncatingRemainder(dividingBy: 0.3) < 0.15 { held.insert(.a) }
                } else { pedalClock = 0 }
                if brake.pressed { state.leftTrigger = 1 }
                if handbrake.pressed { state.rightTrigger = 1 }
            } else {
                if gas.pressed { state.rightTrigger = 1 }
                if brake.pressed { state.leftTrigger = 1 }
                if handbrake.pressed { held.insert(.r1) }
            }
            if driveBy.pressed {
                // Aim with L1; R1 shoots while aiming.
                held.insert(.l1)
                if now - (fireStartedAt ?? now) > 0.12 { held.insert(.r1) }
            }
            if enter.pressed { held.insert(.y) }
            if interact.pressed { held.insert(.right) }
            if horn.pressed { held.insert(.l3) }
            if lookBack.pressed { held.insert(.r3) }
            if vehicleWeapon.pressed { held.insert(.x) }
            if dive.pressed { held.insert(.a) }
            if surface.pressed { held.insert(.x) }
            if lights.pressed { held.insert(.right) }
            // INPUT_VEH_GRAPPLING_HOOK, D-pad right in the game's standard pad layout.
            if towHook.pressed { held.insert(.right) }
            // The tow arm moves with the left stick up/down, as on a controller.
            if towArmUp.pressed { state.leftY = 1 } else if towArmDown.pressed { state.leftY = -1 }
            if detonate.pressed { held.insert(.left) }
            for role in roles.values {
                guard case .radioWheel(_, let current, let since) = role, now - since >= 0.25 else { continue }
                // Held: the wheel is open around the middle of the screen, and the station picked is the
                // one the finger points at from there. It goes straight into the wheel's own inputs
                // (PGSetRadioWheelDirection); camera and steering stay still while choosing.
                held.insert(.left)
                let d = CGPoint(x: current.x - bounds.midX, y: current.y - bounds.midY), length = hypot(d.x, d.y)
                radioDirection = length > 40 ? (Float(d.x / length), Float(-d.y / length)) : (0, 0)
                state.rightX = 0; state.rightY = 0
                state.leftX = 0; state.leftY = 0
            }
        case .heli, .plane:
            state.leftX = Float(moveStick.value.x); state.leftY = Float(moveStick.value.y)
            // GTA V's controller flight: RT throttle up / climb, LT down / descend, LB/RB rudder.
            if throttleUp.pressed { state.rightTrigger = 1 }
            if throttleDown.pressed { state.leftTrigger = 1 }
            if yawLeft.pressed { held.insert(.l1) }
            if yawRight.pressed { held.insert(.r1) }
            if airFire.pressed { held.insert(.a) }
            if vehicleWeapon.pressed { held.insert(.x) }
            if gear.pressed { held.insert(.l3) }
            if let start = exitHoldStart {
                // Leaving an aircraft needs a short hold, so a slip cannot bail out.
                let progress = (now - start) / 0.4
                enter.setProgress(CGFloat(progress))
                if progress >= 1 { held.insert(.y) }
            }
        case .menu:
            break
        }

        for role in roles.values {
            guard case .characterWheel(let start, let current) = role else { continue }
            // Hold D-pad down (the selector opens); the same finger points at a character.
            held.insert(.down)
            let d = CGPoint(x: current.x - start.x, y: current.y - start.y), length = hypot(d.x, d.y)
            state.rightX = length > 24 ? Float(d.x / length) : 0
            state.rightY = length > 24 ? Float(-d.y / length) : 0
        }
        if camera.pressed { held.insert(.select) }
        if pause.pressed { held.insert(.start) }
        if phone.pressed && phoneDock && !gamePhoneOut { held.insert(.up) }
        if phone.pressed && gamePhoneOut { held.insert(.b) }
        if up.pressed { held.insert(.up) }
        if down.pressed { held.insert(.down) }
        if taxiRide {
            // The taxi's destination menu reads the left stick (D-pad left would change the station).
            if left.pressed { state.leftX = -1 }
            if right.pressed { state.leftX = 1 }
        } else {
            if left.pressed { held.insert(.left) }
            if right.pressed { held.insert(.right) }
        }
        if accept.pressed { held.insert(.a) }
        if back.pressed { held.insert(.b) }
        if phoneOption.pressed { held.insert(.x) }
        if taxiHurry.pressed { held.insert(.x) }
        if taxiStop.pressed { held.insert(.b) }
        if tabLeft.pressed { held.insert(.l1) }
        if tabRight.pressed { held.insert(.r1) }
        // Without a phone on screen the dock closes itself: after a moment when the phone did not
        // come up, or after 20 s without input as before.
        if phoneDock && !gamePhoneOut {
            if let asked = phoneRequestedAt, now - asked > 2.5 { phoneDock = false; phoneRequestedAt = nil; updateVisibility() }
            else if phoneRequestedAt == nil && now - lastDockInput > 20 { phoneDock = false; updateVisibility() }
        }

        if context == .onFoot && detonate.pressed { held.insert(.left) }
        // The radio wheel's own inputs (see PGSetRadioWheelDirection).
        PGSetRadioWheelDirection(radioDirection?.0 ?? 0, radioDirection?.1 ?? 0, radioDirection != nil)
        radioDirection = nil
        pulses.removeAll { $0.until <= now }
        for pulse in pulses { held.formUnion(pulse.buttons) }
        // Every press reaches the game: a bit stays down at least `minimumPress` after it went down,
        // since the engine samples the pad once per game frame.
        let raw = held
        for bit in 0..<16 {
            let value = UInt32(1) << UInt32(bit)
            if raw.rawValue & value != 0 && lastHeld.rawValue & value == 0 { pressedAt[value] = now }
            if raw.rawValue & value == 0, let at = pressedAt[value], now - at < Self.minimumPress { held.insert(PadButtons(rawValue: value)) }
        }
        lastHeld = raw
        state.padButtons = held
        return state
    }

    /// Thumb offset (-1...1) to the engine's right stick. A small inner dead
    /// zone ignores a resting thumb; beyond it, output starts just past the
    /// engine's own dead zone so gentle pushes turn slowly instead of not at
    /// all. `speed` above 1 reaches full turning speed with less travel.
    static func cameraStick(_ value: CGPoint, speed: CGFloat) -> (Float, Float) {
        let length = hypot(value.x, value.y)
        guard length > 0.08 else { return (0, 0) }
        let x = min(1, (length - 0.08) / 0.92 * max(0.3, speed))
        let deadZone: CGFloat = 0.24
        let out = deadZone + (1 - deadZone) * pow(x, 1.4)
        return (Float(value.x / length * out), Float(value.y / length * out))
    }

    /// Finger speed (points/second) to stick deflection. About 320 pt/s is a
    /// full stick. Any real movement starts just past the engine's stick dead
    /// zone, so slow, precise drags still move the camera.
    static func lookAxis(_ velocity: CGFloat) -> Float {
        let speed = abs(velocity)
        guard speed > 4 else { return 0 }
        let x = min(1, speed / 320)
        let deadZone: CGFloat = 0.24
        return Float(copysign(deadZone + (1 - deadZone) * pow(x, 0.75), velocity))
    }
}
