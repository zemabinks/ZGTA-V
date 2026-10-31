"""Execute the native controller's actual readiness/failure block with lightweight UI doubles.

This checks UI ordering, not native trap recovery, Metal output or device gameplay.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2] / 'app'

class NativeBootPresentationTests(unittest.TestCase):
    def test_failure_is_terminal_despite_late_frames_and_animation_completion(self):
        source = (ROOT / 'App/NativePortViewController.swift').read_text()
        start = source.index('        // Engine readiness is terminally rejected')
        end = source.index('        if !written { LogWriter.shared.write(line) }', start)
        actual_handler = source[start:end]
        harness = r'''
import Foundation
func CACurrentMediaTime() -> Double { 1 }
func PGCaptureNativeFrame(_ name: String) {}
func PGSetTargetingMode(_ mode: Int32) {}
struct PGPadState {}
enum L10n { static func text(_ value: String) -> String { value } }
final class GameSettings {
    static let shared = GameSettings()
    var targetingMode = 0
    var stable = 0
    func markBootStable() { stable += 1 }
}
final class Layer { var cancelled = 0; func removeAllAnimations() { cancelled += 1 } }
class View { var isHidden = false; var alpha = 1.0; let layer = Layer() }
final class Button: View {
    var isEnabled = true
    var title = "Play"
    enum State { case disabled }
    func setTitle(_ value: String, for state: State) { title = value }
    func setNeedsUpdateConfiguration() {}
}
final class Home: View { let settingsButton = Button(); let layoutButton = Button() }
final class Metal { var isPaused = false }
final class Audio { var stops = 0; func stop() { stops += 1 } }
final class AVAudioSession {
    enum Option { case notifyOthersOnDeactivation }
    static func sharedInstance() -> AVAudioSession { AVAudioSession() }
    func setActive(_ value: Bool, options: Option) throws {}
}
enum UIView {
    static var completions: [(Bool) -> Void] = []
    static func animate(withDuration: Double, animations: () -> Void, completion: @escaping (Bool) -> Void) {
        animations(); completions.append(completion)
    }
    static func finish() { let pending = completions; completions = []; pending.forEach { $0(true) } }
}
final class Controller {
    var engineFailed = false, movementProofStarted = false, touchControlsAvailable = false, proofInputActive = false
    var worldReadyAt: Double?
    var healthTimer: Timer?
    let home = Home(), launchButton = Button(), audioEngine = Audio(), metalView = Metal()
    var diagnosticsOverlay: View? = View()
    let touchControls = View(), fpsLabel = View()
    var padProof: PGPadState?
    var proofController: Int?
    var releases = 0, alerts = 0
    func releaseTouchControls() { releases += 1 }
    func runPadScript(_ script: String) {}
    func verifyVirtualPad() {}
    func verifyMovement() {}
    func logHealth() {}
    func showWhenFree(title: String, message: String) { alerts += 1 }
    func handle(_ line: String) {
'''
        assertions = r'''
    }
}
// Healthy readiness still displays the game and marks a world launch stable.
let healthy = Controller()
healthy.handle("WORLD_READY")
precondition(GameSettings.shared.stable == 1 && healthy.healthTimer != nil)
UIView.finish()
precondition(healthy.home.isHidden && healthy.touchControlsAvailable && !healthy.fpsLabel.isHidden)
let timer = healthy.healthTimer!
healthy.handle("Native trap 5; app image base 0x100cc8000")
precondition(healthy.engineFailed && !timer.isValid && healthy.healthTimer == nil)
precondition(!healthy.home.isHidden && healthy.home.alpha == 1)
precondition(!healthy.touchControlsAvailable && healthy.touchControls.isHidden && healthy.fpsLabel.isHidden)
precondition(healthy.worldReadyAt == nil && healthy.releases == 1 && healthy.alerts == 1)
healthy.handle("WORLD_READY")
healthy.handle("{\"label\":\"First frame\"}")
healthy.handle("{\"world\":true}")
UIView.finish()
precondition(GameSettings.shared.stable == 1 && healthy.healthTimer == nil)
precondition(!healthy.home.isHidden && !healthy.touchControlsAvailable && healthy.fpsLabel.isHidden)
// Failure arriving during a readiness animation must win even if its completion is delivered later.
let racing = Controller()
racing.handle("{\"label\":\"First frame\"}")
precondition(!UIView.completions.isEmpty)
racing.handle("Native trap 5; app image base 0x100cc8000")
UIView.finish()
precondition(!racing.home.isHidden && racing.home.alpha == 1 && racing.home.layer.cancelled == 1)
precondition(!racing.touchControlsAvailable && racing.touchControls.isHidden)
// Later trap/boot-stop lines remain in logs but do not stack failure dialogs.
racing.handle("Native boot stopped: unreachable executed")
precondition(racing.alerts == 1 && racing.releases == 1)
// A boot failure before any frame also remains terminal when a surviving worker reports readiness.
let early = Controller()
early.handle("Native boot stopped: unreachable executed")
early.handle("WORLD_READY")
UIView.finish()
precondition(early.engineFailed && !early.home.isHidden && !early.touchControlsAvailable)
precondition(GameSettings.shared.stable == 1)
// Both real renderer startup failures use the same terminal transition. A
// surviving game worker must not mark either failed launch stable afterward.
for message in ["Metal renderer could not start.", "The Metal shader library is missing from the app: rebuild with the game's shaders."] {
    let graphics = Controller()
    graphics.handle(message)
    graphics.handle("WORLD_READY")
    graphics.handle("{\"label\":\"First frame\"}")
    graphics.handle("{\"world\":true}")
    graphics.handle(message)
    UIView.finish()
    precondition(graphics.engineFailed && !graphics.home.isHidden && graphics.home.alpha == 1)
    precondition(!graphics.touchControlsAvailable && graphics.touchControls.isHidden && graphics.fpsLabel.isHidden)
    precondition(graphics.healthTimer == nil && graphics.worldReadyAt == nil)
    precondition(graphics.alerts == 1 && graphics.releases == 1 && graphics.metalView.isPaused)
    let graphicsRace = Controller()
    graphicsRace.handle("{\"label\":\"First frame\"}")
    graphicsRace.handle(message)
    UIView.finish()
    precondition(graphicsRace.engineFailed && !graphicsRace.home.isHidden && !graphicsRace.touchControlsAvailable)
}
precondition(GameSettings.shared.stable == 1)
// Similar diagnostic text does not turn a healthy launch into a fatal one.
let diagnostic = Controller()
diagnostic.handle("Metal renderer: shader diagnostics")
diagnostic.handle("Warning: Metal renderer could not start.")
precondition(!diagnostic.engineFailed && diagnostic.alerts == 0)
print("NATIVE_BOOT_PRESENTATION_PASS")
'''
        with tempfile.TemporaryDirectory(prefix='zema-native-boot-') as folder:
            directory = Path(folder)
            swift = directory / 'main.swift'
            swift.write_text(harness + actual_handler + assertions)
            binary = directory / 'presentation'
            subprocess.run(['/usr/bin/swiftc', '-module-cache-path', str(directory / 'module-cache'), str(swift), '-o', str(binary)], check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
            self.assertIn('NATIVE_BOOT_PRESENTATION_PASS', result.stdout)
        # Fatal state must stop per-frame native input queries, not only hide their views.
        self.assertIn('@objc private func pollController() {\n        guard !engineFailed else { PGSetPerformanceSampling(0); return }', source)
        # Bind these two integration cases to the actual native emitters.
        renderer = (ROOT / 'Source/MetalRenderer/MRRenderer.mm').read_text()
        host = (ROOT / 'Source/MetalGraphicsHost.mm').read_text()
        self.assertIn('pg_log("Metal renderer could not start.")', renderer)
        self.assertIn('pg_log("The Metal shader library is missing from the app: rebuild with the game\'s shaders.")', host)

if __name__ == '__main__':
    unittest.main()
