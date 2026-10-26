import Foundation
import GameController

// Isolated settings double: never reads or changes the user's saved preferences.
final class GameSettings {
    static let shared = GameSettings()
    var lookSensitivity = 2.5, aimSensitivity = 2.5
    var invertLookY = false
}

// C bridge shape from EngineHost.h; exercise the unchanged production mapping.
struct PGPadState {
    var buttons: UInt32 = 0
    var leftX: Float = 0, leftY: Float = 0, rightX: Float = 0, rightY: Float = 0
    var leftTrigger: Float = 0, rightTrigger: Float = 0
}

@main struct NativeControllerFixture {
    static func main() {
        let controller = GCController.withExtendedGamepad()
        guard let pad = controller.extendedGamepad else { fatalError("No virtual extended pad") }
        let mapping: [(GCControllerButtonInput, PadButtons)] = [
            (pad.buttonA, .a), (pad.buttonB, .b), (pad.buttonX, .x), (pad.buttonY, .y),
            (pad.leftShoulder, .l1), (pad.rightShoulder, .r1), (pad.buttonMenu, .start)]
        for (button, expected) in mapping {
            button.setValue(1)
            RunLoop.current.run(until: Date().addingTimeInterval(0.05))
            guard PGPadState(gamepad: pad).padButtons.contains(expected) else {
                print("VIRTUAL_API_SAMPLE_UNAVAILABLE expected=\(expected.rawValue) value=\(button.value) pressed=\(button.isPressed)")
                exit(2)
            }
            button.setValue(0)
            RunLoop.current.run(until: Date().addingTimeInterval(0.05))
            precondition(!PGPadState(gamepad: pad).padButtons.contains(expected))
        }
        // The framework's virtual d-pad accepts direction-pad axis setters;
        // setting an individual d-pad child button is ignored on this Mac.
        for (x, y, expected): (Float, Float, PadButtons) in [(0, 1, .up), (1, 0, .right), (0, -1, .down), (-1, 0, .left)] {
            pad.dpad.setValueForXAxis(x, yAxis: y)
            RunLoop.current.run(until: Date().addingTimeInterval(0.05))
            precondition(PGPadState(gamepad: pad).padButtons.contains(expected))
            pad.dpad.setValueForXAxis(0, yAxis: 0)
            RunLoop.current.run(until: Date().addingTimeInterval(0.05))
            precondition(!PGPadState(gamepad: pad).padButtons.contains(expected))
        }
        for (button, expected) in [(pad.buttonOptions, PadButtons.select), (pad.leftThumbstickButton, .l3), (pad.rightThumbstickButton, .r3)] {
            if let button { button.setValue(1); RunLoop.current.run(until: Date().addingTimeInterval(0.05)); precondition(PGPadState(gamepad: pad).padButtons.contains(expected)); button.setValue(0); RunLoop.current.run(until: Date().addingTimeInterval(0.05)) }
        }
        pad.leftThumbstick.setValueForXAxis(0.5, yAxis: -0.75)
        pad.rightThumbstick.setValueForXAxis(-0.25, yAxis: 0.8)
        pad.leftTrigger.setValue(0.6); pad.rightTrigger.setValue(0.9)
        RunLoop.current.run(until: Date().addingTimeInterval(0.05))
        let state = PGPadState(gamepad: pad)
        precondition(abs(state.leftX-0.5)<0.001 && abs(state.leftY+0.75)<0.001)
        precondition(abs(state.rightX+0.25)<0.001 && abs(state.rightY-0.8)<0.001)
        precondition(abs(state.leftTrigger-0.6)<0.001 && abs(state.rightTrigger-0.9)<0.001)
        var mixed = PGPadState(); mixed.leftX = -0.9; mixed.buttons = PadButtons.a.rawValue
        mixed.merge(state); precondition(mixed.leftX == -0.9 && mixed.rightY == state.rightY)
        precondition(mixed.padButtons.contains(.a))
        // Exercise the actual production initializer with independently selected
        // aim/look settings. Movement, analog triggers and touch merge stay intact.
        pad.leftTrigger.setValue(0)
        RunLoop.current.run(until: Date().addingTimeInterval(0.05))
        GameSettings.shared.lookSensitivity = 5
        GameSettings.shared.aimSensitivity = 0.5
        let faster = PGPadState(gamepad: pad)
        precondition(abs(faster.rightX + 0.5) < 0.001 && faster.rightY == 1)
        precondition(faster.leftX == state.leftX && faster.leftY == state.leftY)
        GameSettings.shared.invertLookY = true
        precondition(PGPadState(gamepad: pad).rightY == -1)
        pad.leftTrigger.setValue(0.6)
        RunLoop.current.run(until: Date().addingTimeInterval(0.05))
        let aimed = PGPadState(gamepad: pad)
        precondition(abs(aimed.rightX + 0.05) < 0.001 && abs(aimed.rightY + 0.16) < 0.001)
        precondition(abs(aimed.leftTrigger - 0.6) < 0.001 && abs(aimed.rightTrigger - 0.9) < 0.001)
        var touch = PGPadState(); touch.rightX = 0.75; touch.rightY = 0.9; touch.padButtons = .x
        var merged = aimed; merged.merge(touch)
        precondition(merged.rightX == 0.75 && merged.rightY == 0.9 && merged.padButtons.contains(.x))
        GameSettings.shared.aimSensitivity = .nan
        precondition(abs(PGPadState(gamepad: pad).rightX + 0.25) < 0.001)
        GameSettings.shared.lookSensitivity = 2.5; GameSettings.shared.aimSensitivity = 2.5
        GameSettings.shared.invertLookY = false
        // A neutral/disconnected source starts from a fresh state each poll.
        pad.leftThumbstick.setValueForXAxis(0, yAxis: 0)
        pad.rightThumbstick.setValueForXAxis(0, yAxis: 0)
        pad.leftTrigger.setValue(0); pad.rightTrigger.setValue(0)
        RunLoop.current.run(until: Date().addingTimeInterval(0.05))
        let neutral = PGPadState(gamepad: pad)
        precondition(neutral.leftX == 0 && neutral.leftY == 0 && neutral.rightX == 0 && neutral.rightY == 0 && neutral.leftTrigger == 0 && neutral.rightTrigger == 0)
        print("NATIVE_CONTROLLER_CAMERA_SETTINGS_AND_TOUCH_MERGE_PASS")
        print("NATIVE_CONTROLLER_BUTTONS_ANALOG_TRIGGERS_AND_MERGE_PASS")
    }
}
