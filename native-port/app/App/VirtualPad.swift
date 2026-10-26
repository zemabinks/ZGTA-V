import GameController

/// Buttons of the engine's own pad (see PGPadState in EngineHost.h). Actions
/// follow GTA V's standard controller layout (data/control/standard*.meta).
struct PadButtons: OptionSet {
    let rawValue: UInt32
    static let l2 = PadButtons(rawValue: 1 << 0)
    static let r2 = PadButtons(rawValue: 1 << 1)
    static let l1 = PadButtons(rawValue: 1 << 2)
    static let r1 = PadButtons(rawValue: 1 << 3)
    static let y = PadButtons(rawValue: 1 << 4)       // Enter/exit vehicle
    static let b = PadButtons(rawValue: 1 << 5)       // Reload, melee, back
    static let a = PadButtons(rawValue: 1 << 6)       // Sprint, accept, aircraft fire
    static let x = PadButtons(rawValue: 1 << 7)       // Jump, vehicle weapon
    static let select = PadButtons(rawValue: 1 << 8)  // Camera view
    static let l3 = PadButtons(rawValue: 1 << 9)      // Crouch, horn, landing gear
    static let r3 = PadButtons(rawValue: 1 << 10)     // Look behind
    static let start = PadButtons(rawValue: 1 << 11)  // Pause
    static let up = PadButtons(rawValue: 1 << 12)     // Phone
    static let right = PadButtons(rawValue: 1 << 13)  // Headlights
    static let down = PadButtons(rawValue: 1 << 14)
    static let left = PadButtons(rawValue: 1 << 15)   // Radio, aircraft weapon
}

extension PGPadState {
    var padButtons: PadButtons {
        get { PadButtons(rawValue: buttons) }
        set { buttons = newValue.rawValue }
    }

    /// Combine two sources: buttons merge, the larger deflection wins.
    mutating func merge(_ other: PGPadState) {
        buttons |= other.buttons
        func pick(_ a: Float, _ b: Float) -> Float { abs(b) > abs(a) ? b : a }
        leftX = pick(leftX, other.leftX); leftY = pick(leftY, other.leftY)
        rightX = pick(rightX, other.rightX); rightY = pick(rightY, other.rightY)
        leftTrigger = max(leftTrigger, other.leftTrigger)
        rightTrigger = max(rightTrigger, other.rightTrigger)
    }

    /// Physical buttons and movement retain the engine mapping. Camera settings
    /// apply here before touch input is merged, so touch look is not scaled twice.
    init(gamepad pad: GCExtendedGamepad) {
        self.init()
        leftX = pad.leftThumbstick.xAxis.value; leftY = pad.leftThumbstick.yAxis.value
        leftTrigger = pad.leftTrigger.value; rightTrigger = pad.rightTrigger.value
        let settings = GameSettings.shared
        let requestedSpeed = leftTrigger > 0.2 ? settings.aimSensitivity : settings.lookSensitivity
        let speed = Float(requestedSpeed.isFinite ? min(max(requestedSpeed, 0.5), 10) : 2.5) / 2.5
        func look(_ value: Float) -> Float { value.isFinite ? max(-1, min(1, value * speed)) : 0 }
        rightX = look(pad.rightThumbstick.xAxis.value)
        rightY = look(pad.rightThumbstick.yAxis.value) * (settings.invertLookY ? -1 : 1)
        var held = PadButtons()
        let map: [(GCControllerButtonInput?, PadButtons)] = [
            (pad.buttonA, .a), (pad.buttonB, .b), (pad.buttonX, .x), (pad.buttonY, .y),
            (pad.leftShoulder, .l1), (pad.rightShoulder, .r1), (pad.buttonMenu, .start), (pad.buttonOptions, .select),
            (pad.leftThumbstickButton, .l3), (pad.rightThumbstickButton, .r3),
            (pad.dpad.up, .up), (pad.dpad.right, .right), (pad.dpad.down, .down), (pad.dpad.left, .left)]
        for (button, bit) in map where button?.isPressed == true { held.insert(bit) }
        padButtons = held
    }
}
