import UIKit
import SwiftUI
import MetalKit
import GameController
import AVFAudio
import UniformTypeIdentifiers
import os

private func engineLog(_ message: UnsafePointer<CChar>?, _ context: UnsafeMutableRawPointer?) {
    guard let message, let context else { return }
    let controller = Unmanaged<NativePortViewController>.fromOpaque(context).takeUnretainedValue()
    LogWriter.shared.engine(String(cString: message), to: controller)
}

/// The log file and the engine's lines (from GTA V Port 1.3.3). The engine can print thousands of
/// lines a second; one main-thread hop per line, each opening the file and calling NSLog, starved the
/// UI: the app lagged, frames dropped and touch releases arrived late (buttons acted held). Each line
/// is written at once through one open file handle on the thread that logs it (a crash's last lines
/// must reach the file), and the UI gets the lines in batches at most every 50 ms.
final class LogWriter {
    static let shared = LogWriter()
    private let queue = DispatchQueue(label: "log-writer", qos: .utility)
    private var handle: FileHandle?
    private let lock = NSLock()
    private var pending: [String] = []
    private var flushScheduled = false

    func open(_ file: URL) {
        lock.lock(); try? handle?.close(); handle = try? FileHandle(forWritingTo: file); _ = try? handle?.seekToEnd(); lock.unlock()
    }
    /// One line from the app itself, written in order with the engine's.
    func write(_ line: String) {
        guard let data = (line + "\n").data(using: .utf8) else { return }
        lock.lock(); try? handle?.write(contentsOf: data); lock.unlock()
    }
    func engine(_ line: String, to controller: NativePortViewController) {
        let data = (line + "\n").data(using: .utf8)
        lock.lock()
        if let data { try? handle?.write(contentsOf: data) }
        pending.append(line); let schedule = !flushScheduled; flushScheduled = true
        lock.unlock()
        guard schedule else { return }
        queue.asyncAfter(deadline: .now() + 0.05) {
            self.lock.lock(); let batch = self.pending; self.pending.removeAll(keepingCapacity: true); self.flushScheduled = false; self.lock.unlock()
            DispatchQueue.main.async { controller.engineLines(batch) }
        }
    }
}

final class NativePortViewController: UIViewController, MTKViewDelegate {
    private var metalView: MTKView!
    private var queue: MTLCommandQueue?
    private let output = UITextView()
    private let fpsLabel = UILabel()
    private var lastFPSLabelUpdate: CFTimeInterval = 0
    private let performanceRun = PerformanceRun()
    /// The start screen; it hides once the game's world is up.
    private lazy var home = HomeView(modes: GameMode.allCases.map { ($0.title, $0 == .story ? "book.fill" : "map.fill") }, log: output)
    private var launchButton: UIButton { home.playButton }
    private var preloadLabel: UILabel { home.preloadLabel }
    private var controllerLabel: UILabel { home.controllerLabel }
    private var diagnosticsOverlay: UIView? { home }
    private let audioEngine = AVAudioEngine()
    private var audioSource: AVAudioSourceNode?
    /// Mic toggles and audio configuration changes touch the same session and engine: one at a time.
    private let audioQueue = DispatchQueue(label: "mugoat.audio", qos: .userInitiated)
    private var isMicTapInstalled = false
    private var displayLink: CADisplayLink?
    private var lastControllerPoll: CFTimeInterval?
    private var lines: [String] = []
    private var metrics: [String: String] = [:]
    private var logFile: URL?
    private let touchControls = TouchControlsView(frame: .zero)
    private let gyro = GyroInput()
    private var engineStarted = false
    private var loadedModVehicleModels = Set<String>()
    /// The engine stopped with an error: it can only start again in a new app process.
    private var engineFailed = false
    private var bootedPreset = GameSettings.shared.graphicsPreset
    private var bootedFrameRateCap = 60
    private var bootedBackend = "offline"
    private var requestedFrameInterval: Int32 = 1
    /// Render height multiplier while the phone is hot (1 = the chosen resolution).
    private var thermalScale = 1.0
    /// Requested engine size, not a claim about the GPU's completed frame dimensions.
    private var requestedRenderSize: (width: Int, height: Int)?
    private var bootedMode: GameMode?
    private var stableTimer: Timer?
    private var healthTimer: Timer?
    private var lastHealth: [UInt64] = [0, 0, 0, 0, 0, 0, 0]
    private var padProof: PGPadState?
    private var lastGameStatus: UInt32 = 999
    private var worldReadyAt: CFTimeInterval?
    private var tiltNeutral: Double?
    private var tiltSince: CFTimeInterval?
    private var tiltSmoothed: Double = 0
    private var touchControlsAvailable = false
    private var lastTouchInputTrace = ""
    private var movementProofStarted = false
    private var proofController: GCController?
    private var proofInputSamples = 0
    private var proofInputActive = false
    private var hardwareKeys = Set<UIKeyboardHIDUsage>()
    override var canBecomeFirstResponder: Bool { true }
    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        becomeFirstResponder()
    }
    override func pressesBegan(_ presses: Set<UIPress>, with event: UIPressesEvent?) {
        // With keyboard and mouse on, keys reach the game as PC keys instead (KeyboardMouse).
        let pcKeys = KeyboardMouse.shared.isPCMode
        for press in presses { if let key = press.key, !pcKeys { hardwareKeys.insert(key.keyCode) } }
        super.pressesBegan(presses, with: event)
    }
    override func pressesEnded(_ presses: Set<UIPress>, with event: UIPressesEvent?) {
        for press in presses { if let key = press.key { hardwareKeys.remove(key.keyCode) } }
        super.pressesEnded(presses, with: event)
    }
    override func pressesCancelled(_ presses: Set<UIPress>, with event: UIPressesEvent?) {
        hardwareKeys.removeAll()
        super.pressesCancelled(presses, with: event)
    }

    override var prefersStatusBarHidden: Bool { true }
    /// While playing with a mouse (iPad), the pointer is captured so moving it looks around.
    override var prefersPointerLocked: Bool { engineStarted && GameSettings.shared.keyboardMouse && KeyboardMouse.shared.hasMouse }
    override var supportedInterfaceOrientations: UIInterfaceOrientationMask { .landscape }

    override func viewDidLoad() {
        super.viewDidLoad()
        UIApplication.shared.isIdleTimerDisabled = true
        let device = MTLCreateSystemDefaultDevice()
        metalView = MTKView(frame: .zero, device: device)
        queue = device?.makeCommandQueue()
        metalView.delegate = self
        metalView.clearColor = MTLClearColorMake(0.025, 0.025, 0.035, 1)
        metalView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(metalView)

        controllerLabel.text = L10n.text("Controls: touch")
        // Progress text (preparing assets, loading) shows on the disabled Play button.
        let playStyle = launchButton.configurationUpdateHandler
        launchButton.configurationUpdateHandler = { [weak self] button in
            playStyle?(button)
            // Loading progress replaces Play only after the engine starts.
            let readyTitle = GameSettings.shared.gameModeChoice.map { $0 == .story ? L10n.text("Play Story mode") : L10n.text("Play Free roam") } ?? L10n.text("Choose a mode")
            let title = button.isEnabled || !(self?.engineStarted ?? false) ? readyTitle : button.title(for: .disabled) ?? L10n.text("Loading…")
            var text = AttributedString(title)
            text.font = Theme.display(20, .heavy)
            text.foregroundColor = button.isEnabled ? Theme.onAccent : Theme.secondaryText
            button.configuration?.attributedTitle = text
            button.configuration?.image = button.isEnabled ? UIImage(systemName: "play.fill", withConfiguration: UIImage.SymbolConfiguration(weight: .heavy)) : nil
        }
        launchButton.addTarget(self, action: #selector(startEngine), for: .touchUpInside)
        output.isEditable = false
        output.isHidden = !ProcessInfo.processInfo.arguments.contains("--show-log")
        output.backgroundColor = UIColor.black.withAlphaComponent(0.65)
        output.textColor = .white
        output.font = .monospacedSystemFont(ofSize: 12, weight: .regular)
        output.layer.cornerRadius = 12
        home.modButton.addAction(UIAction { [weak self] _ in self?.showModManager() }, for: .touchUpInside)
        home.settingsButton.addAction(UIAction { [weak self] _ in self?.showSettings() }, for: .touchUpInside)
        home.layoutButton.addAction(UIAction { [weak self] _ in self?.showLayoutEditor() }, for: .touchUpInside)
        home.saveButton.addAction(UIAction { [weak self] _ in self?.showSaves() }, for: .touchUpInside)
        home.onFiles = { [weak self] in self?.showGameFiles() }
        home.onMap = { [weak self] index in
            guard let self, !self.engineStarted else { return }
            GameSettings.shared.sandboxMap = index
            self.refreshModeChoice()
        }
        home.onMode = { [weak self] index in
            guard let self, !self.engineStarted else { return }
            GameSettings.shared.gameMode = GameMode.allCases[index]
            self.refreshModeChoice()
        }
        updateServerStatus()
        // Debug/automation: --local-game-folder /path (a folder the app can already read) skips the picker.
        if let index = ProcessInfo.processInfo.arguments.firstIndex(of: "--local-game-folder"), index + 1 < ProcessInfo.processInfo.arguments.count {
            let folder = URL(fileURLWithPath: ProcessInfo.processInfo.arguments[index + 1])
            if case let .refused(problem) = GameFolder.choose(folder) { appendLog("Game folder refused: " + problem) }
        }
        if GameFolder.isChosen { updateServerStatus() }
        else if !GameSettings.shared.assetServer.isEmpty { testAssetServer() }
        // Debug/automation: --game-mode story|sandbox picks the mode before Play.
        let arguments = ProcessInfo.processInfo.arguments
        if let index = arguments.firstIndex(of: "--game-mode"), index + 1 < arguments.count {
            GameSettings.shared.gameMode = arguments[index + 1] == "story" ? .story : .sandbox
        }
        refreshModeChoice()
        home.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(home)
        fpsLabel.text = "— FPS"
        fpsLabel.isHidden = true
        fpsLabel.font = .monospacedDigitSystemFont(ofSize: 12, weight: .semibold)
        fpsLabel.textColor = .white
        fpsLabel.textAlignment = .center
        fpsLabel.backgroundColor = UIColor.black.withAlphaComponent(0.5)
        fpsLabel.layer.cornerRadius = 6
        fpsLabel.clipsToBounds = true
        fpsLabel.isUserInteractionEnabled = false
        fpsLabel.accessibilityLabel = "Game frame rate"
        fpsLabel.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(fpsLabel)
        touchControls.translatesAutoresizingMaskIntoConstraints = false
        touchControls.isHidden = true
        touchControls.inputChanged = { [weak self] in self?.pollController() }
        touchControls.openSettings = { [weak self] in self?.showSettings() }
        touchControls.openCheat = { [weak self] in self?.showModManager() }
        touchControls.hintsChanged = { [weak self] line in self?.appendLog(line) }
        touchControls.onVoiceMicChanged = { [weak self] enabled in self?.handleVoiceMicChanged(enabled) }
        let tap3 = UITapGestureRecognizer(target: self, action: #selector(handleThreeFingerTap(_:)))
        tap3.numberOfTouchesRequired = 3
        tap3.cancelsTouchesInView = false
        view.addGestureRecognizer(tap3)
        KeyboardMouse.shared.start()
        KeyboardMouse.shared.onControllerKey = { [weak self] usage, pressed in
            DispatchQueue.main.async {
                guard let self else { return }
                if pressed {
                    self.hardwareKeys.insert(usage)
                } else {
                    self.hardwareKeys.remove(usage)
                }
            }
        }
        KeyboardMouse.shared.changed = { [weak self] in
            guard let self else { return }
            self.appendLog("Keyboard: \(KeyboardMouse.shared.hasKeyboard ? "connected" : "none"), mouse: \(KeyboardMouse.shared.hasMouse ? "connected" : "none")")
            self.setNeedsUpdateOfPrefersPointerLocked()
        }
        view.addSubview(touchControls)
        NSLayoutConstraint.activate([
            touchControls.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            touchControls.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            touchControls.topAnchor.constraint(equalTo: view.topAnchor),
            touchControls.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])
        NSLayoutConstraint.activate([
            fpsLabel.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 12),
            fpsLabel.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 8),
            fpsLabel.widthAnchor.constraint(equalToConstant: 68),
            fpsLabel.heightAnchor.constraint(equalToConstant: 24)
        ])
        NSLayoutConstraint.activate([
            metalView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            metalView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            metalView.topAnchor.constraint(equalTo: view.topAnchor),
            metalView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            home.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            home.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            home.topAnchor.constraint(equalTo: view.topAnchor),
            home.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])
        let directory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        logFile = directory.appendingPathComponent("native-port.log")
        // Keep the previous run's log: after a crash it is the one worth sharing (Settings, Share log).
        // Only a run that started the game replaces it, so opening the app a few times after a crash
        // (without playing) doesn't push the crash out.
        let previous = directory.appendingPathComponent("native-port-previous.log")
        let lastRunPlayed = ((try? FileManager.default.attributesOfItem(atPath: logFile!.path)[.size] as? NSNumber)?.intValue ?? 0) > 16_384
        if lastRunPlayed || !FileManager.default.fileExists(atPath: previous.path) {
            try? FileManager.default.removeItem(at: previous)
            try? FileManager.default.moveItem(at: logFile!, to: previous)
        }
        try? Data().write(to: logFile!)
        LogWriter.shared.open(logFile!)
        appendLog("ZGTA V \(Theme.appVersion) on iOS \(UIDevice.current.systemVersion)")
        appendLog("Native UIKit + Metal host. Engine compiled into the app; no WebView or JIT.")
        appendLog("Metal device: \(device?.name ?? "unavailable")")
        GameFolder.log = { [weak self] line in self?.appendLog(line) }
        // A game folder moved into Files › On My iPhone › ZGTA V is found without any picking.
        lookForGameFiles()
        NotificationCenter.default.addObserver(self, selector: #selector(lookForGameFiles), name: UIApplication.didBecomeActiveNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(installChanged), name: .gameInstallChanged, object: nil)
        displayLink = CADisplayLink(target: self, selector: #selector(pollController))
        // ProMotion screens only run above 60 Hz when the app asks: L10n.text("Unlocked") asks for up to 120.
        if GameSettings.shared.frameRateCap == 0 {
            let top = Float(UIScreen.main.maximumFramesPerSecond)
            displayLink?.preferredFrameRateRange = CAFrameRateRange(minimum: min(60, top), maximum: top, preferred: top)
        }
        displayLink?.add(to: .main, forMode: .common)
        NotificationCenter.default.addObserver(self, selector: #selector(handleAudioEngineConfigurationChange), name: .AVAudioEngineConfigurationChange, object: audioEngine)
        NotificationCenter.default.addObserver(self, selector: #selector(handleAudioRouteChange), name: AVAudioSession.routeChangeNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(controllerChanged), name: .GCControllerDidDisconnect, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(controllerChanged), name: .GCControllerDidConnect, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(releaseTouchControls), name: UIApplication.willResignActiveNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(leftApp), name: UIApplication.didEnterBackgroundNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(leftApp), name: UIApplication.willTerminateNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(thermalStateChanged), name: ProcessInfo.thermalStateDidChangeNotification, object: nil)
        if let recovery = GameSettings.shared.recoverFromFailedBoot() {
            appendLog("Previous launch on \(recovery.failed.title) did not finish; lowered to \(recovery.fallback.title)\(recovery.resetHeight.map { ", resolution \($0)p back to Auto" } ?? "").")
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { self.explainRecovery(recovery) }
        }
        if ProcessInfo.processInfo.arguments.contains("--touch-controls-preview") {
            diagnosticsOverlay?.isHidden = true
            touchControlsAvailable = true
            fpsLabel.isHidden = false
            touchControls.isHidden = false
        }
        NotificationCenter.default.addObserver(self, selector: #selector(preloadChanged), name: .assetPreloadChanged, object: nil)
        // Continue an unfinished L10n.text("Download all game files") after a relaunch.
        AssetPreloader.shared.resumeIfNeeded()
        if ProcessInfo.processInfo.arguments.contains("--preload-autostart") {
            // Debug: start the download without tapping (simulator checks).
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                if let message = AssetPreloader.shared.start() { self.appendLog("Preload refused: " + message) }
            }
        }
        if ProcessInfo.processInfo.arguments.contains("--open-layout-editor") {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { self.showLayoutEditor() }
        }
        if ProcessInfo.processInfo.arguments.contains("--open-game-files") || ProcessInfo.processInfo.arguments.contains("--install-link") {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { self.showGameFiles() }
        }
        if ProcessInfo.processInfo.arguments.contains("--open-settings") {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { self.showSettings() }
        }
        if ProcessInfo.processInfo.arguments.contains("--boot-engine") {
            DispatchQueue.main.async { self.startEngine() }
        }
    }

    @objc private func preloadChanged() {
        let summary = AssetPreloader.shared.launchSummary
        preloadLabel.text = summary
        preloadLabel.isHidden = summary == nil
    }

    /// A batch of engine lines (LogWriter has written them to the file already).
    func engineLines(_ batch: [String]) {
        // Only the last 500 lines can show; older ones in a big batch only need their checks.
        for line in batch { handleLine(line, written: true, show: false) }
        lines.append(contentsOf: batch.suffix(500))
        if lines.count > 500 { lines.removeFirst(lines.count - 500) }
        refreshLogView()
    }

    func appendLog(_ line: String) {
        // Lines also come from background work (checking the game files); the log view is UI.
        guard Thread.isMainThread else { DispatchQueue.main.async { self.appendLog(line) }; return }
        NSLog("[native-port] %@", line)
        handleLine(line, written: false, show: true)
    }

    private func handleLine(_ line: String, written: Bool, show: Bool) {
        if !engineFailed && line.hasPrefix("ASSET_WARM_PROGRESS ") {
            let parts = line.split(separator: " ")
            if parts.count >= 3 {
                let size = Double(parts[2]).map { String(format: "%.1f GB", $0 * 1048576 / 1_000_000_000) } ?? ""
                launchButton.setTitle("Preparing assets… \(parts[1])% · \(size)", for: .disabled); launchButton.setNeedsUpdateConfiguration()
            }
        }
        if !engineFailed && line == "ASSET_WARM_COMPLETE" { launchButton.setTitle(L10n.text("Loading…"), for: .disabled); launchButton.setNeedsUpdateConfiguration() }
        // Engine readiness is terminally rejected after a trap; other workers may still log frames.
        if !engineFailed {
            if line == "WORLD_READY", ProcessInfo.processInfo.arguments.contains("--capture-world") {
                DispatchQueue.main.asyncAfter(deadline: .now() + 35) {
                    guard !self.engineFailed else { return }
                    PGCaptureNativeFrame("optimized-world")
                }
            }
            if line == "WORLD_READY", let i = ProcessInfo.processInfo.arguments.firstIndex(of: "--pad-script"), i + 1 < ProcessInfo.processInfo.arguments.count, !movementProofStarted {
                movementProofStarted = true
                runPadScript(ProcessInfo.processInfo.arguments[i + 1])
            }
            if line == "WORLD_READY", ProcessInfo.processInfo.arguments.contains("--verify-pad"), !movementProofStarted {
                movementProofStarted = true
                DispatchQueue.main.asyncAfter(deadline: .now() + 30) {
                    guard !self.engineFailed else { return }
                    self.verifyVirtualPad()
                }
            }
            if line == "WORLD_READY", ProcessInfo.processInfo.arguments.contains("--verify-movement"), !movementProofStarted {
                movementProofStarted = true
                DispatchQueue.main.asyncAfter(deadline: .now() + 30) {
                    guard !self.engineFailed else { return }
                    self.verifyMovement()
                }
            }
            if line == "WORLD_READY" {
                PGSetTargetingMode(Int32(GameSettings.shared.targetingMode))
                if worldReadyAt == nil { worldReadyAt = CACurrentMediaTime() }
                GameSettings.shared.markBootStable()
            }
            if line == "WORLD_READY", healthTimer == nil {
                // Every 10 s: physical RAM, process usage, OS headroom and game-file reads.
                healthTimer = Timer.scheduledTimer(withTimeInterval: 10, repeats: true) { [weak self] _ in self?.logHealth() }
            }
            if line == "WORLD_READY" || line.contains("\"label\":\"First frame\"") || line.contains("\"world\":true") {
                diagnosticsOverlay?.isHidden = true
                UIView.animate(withDuration: 0.35) {
                    self.home.alpha = 0
                } completion: { _ in
                    guard !self.engineFailed else { return }
                    self.home.isHidden = true
                }
                touchControlsAvailable = true
                fpsLabel.isHidden = false
            }
        }
        // Renderer setup failure keeps its drain thread alive; later engine
        // progress must not hide the failure or re-enable game controls.
        if !engineFailed && (
            line.hasPrefix("Native boot stopped:") || line == "iOS could not reserve the engine memory." || line.hasPrefix("Native trap") ||
            line == "Metal renderer could not start." ||
            line == "The Metal shader library is missing from the app: rebuild with the game's shaders."
        ) {
            engineFailed = true
            home.layer.removeAllAnimations()
            touchControlsAvailable = false
            releaseTouchControls()
            touchControls.isHidden = true
            padProof = nil
            proofInputActive = false
            proofController = nil
            worldReadyAt = nil
            healthTimer?.invalidate()
            healthTimer = nil
            fpsLabel.isHidden = true
            audioEngine.stop()
            try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
            metalView.isPaused = true
            launchButton.isEnabled = false
            launchButton.setTitle(L10n.text("Close and Reopen the App"), for: .disabled); launchButton.setNeedsUpdateConfiguration()
            home.isHidden = false
            home.alpha = 1.0
            home.settingsButton.isHidden = false
            home.layoutButton.isHidden = false
            showWhenFree(title: L10n.text("Unable to start game"), message: line + "\n\n" + L10n.text("Fully close the app from the app switcher, then reopen it. If the problem repeats, share native-port-previous.log from the ZGTA V folder."))
        }
        if !written { LogWriter.shared.write(line) }
        for key in ["[wgpu] fps:", "[wgpu] draw costs", "Native frame costs:", "Phone memory:", "WORLD_READY"] where line.hasPrefix(key) {
            metrics[key] = line
            if let data = try? JSONSerialization.data(withJSONObject: metrics, options: [.prettyPrinted, .sortedKeys]), let logFile {
                try? data.write(to: logFile.deletingLastPathComponent().appendingPathComponent("native-metrics.json"), options: .atomic)
            }
        }
        guard show else { return }
        lines.append(line)
        if lines.count > 500 { lines.removeFirst(lines.count - 500) }
        refreshLogView()
    }

    private func refreshLogView() {
        guard diagnosticsOverlay?.isHidden != true else { return }
        output.text = lines.joined(separator: "\n")
        if !output.text.isEmpty { output.scrollRangeToVisible(NSRange(location: output.text.utf16.count - 1, length: 1)) }
    }

    /// The launch screen asks for a mode once; after that it remembers it.
    private func refreshModeChoice() {
        let choice = GameSettings.shared.gameModeChoice
        home.setMode(choice.flatMap { GameMode.allCases.firstIndex(of: $0) }, detail: choice?.detail ?? L10n.text("Choose Story mode or Sandbox to play."), enabled: !engineStarted)
        home.setMap(GameSettings.shared.sandboxMap, visible: choice == .sandbox, enabled: !engineStarted)
        updatePlayEnabled()
        launchButton.setNeedsUpdateConfiguration()
    }

    @objc private func startEngine() {
        guard !engineStarted, presentedViewController == nil else { return }
        // Keep Play responsive: missing requirements lead to their setup screen.
        if GameInstallManager.shared.isRunning { showGameFiles(); return }
        if lookingForGameFiles {
            if ProcessInfo.processInfo.arguments.contains("--boot-engine") { launchAfterFileScan = true; return }
            showWhenFree(title: L10n.text("Game data"), message: L10n.text("Checking game files. Wait for the check to finish, then tap Play."))
            return
        }
        if !GameFolder.isChosen && !Self.isServerAddress(GameSettings.shared.assetServer) { showGameFiles(); return }
        if OnlineSettings.enabled && OnlineSettings.server.isEmpty { showOnline(); return }
        if GameSettings.shared.gameModeChoice == nil && !ProcessInfo.processInfo.arguments.contains("--boot-engine") {
            let alert = UIAlertController(title: L10n.text("Choose game mode"), message: L10n.text("Choose Story mode or Sandbox to play."), preferredStyle: .alert)
            for mode in GameMode.allCases {
                alert.addAction(UIAlertAction(title: mode.title, style: .default) { [weak self] _ in
                    GameSettings.shared.gameMode = mode
                    self?.refreshModeChoice()
                    self?.dismiss(animated: true)
                })
            }
            alert.addAction(UIAlertAction(title: L10n.text("Cancel"), style: .cancel))
            present(alert, animated: true)
            return
        }
        guard let path = EnginePaths.manifest else {
            appendLog("Asset manifest is missing from the app bundle.")
            showWhenFree(title: L10n.text("Unable to start game"), message: L10n.text("The app is missing its game file manifest. Please reinstall the complete IPA."))
            return
        }
        let localData: URL?
        if GameFolder.isChosen {
            guard let data = GameFolder.open() else {
                appendLog("The game folder on this iPhone can't be opened any more. Choose it again.")
                GameFolder.clear()
                updateServerStatus()
                showGameFiles()
                return
            }
            localData = data
        } else {
            localData = nil
        }
        if localData != nil && AssetPreloader.shared.localLaunchNeedsRestart {
            showWhenFree(title: "Restart required", message: "The game-file cache was opened before you selected this local folder. Restart ZGTA V once to load its files and enabled add-on packs. Your game data and saves are preserved.")
            return
        }
        do { try ModChangeQueue(directory: ModManagerViewController.modsDirectory).applyBeforeLaunch() }
        catch {
            showWhenFree(title: "Mod changes", message: error.localizedDescription)
            return
        }
        let mode = GameSettings.shared.gameMode
        guard OnlineSettings.configure(mode: mode) else {
            showWhenFree(title: L10n.text("Online server"), message: L10n.text("Invalid server"))
            return
        }
        metalView.isPaused = true
        metalView.delegate = nil
        // Dawn owns the drawable size from here; MTKView must not reset it on layout.
        metalView.autoResizeDrawable = false
        PGAttachMetalLayer(Unmanaged.passUnretained(metalView.layer).toOpaque())
        launchButton.isEnabled = false
        home.settingsButton.isHidden = true
        home.layoutButton.isHidden = true
        engineStarted = true
        refreshModeChoice()
        bootedMode = mode
        let testMap = mode == .sandbox && GameSettings.shared.sandboxMap == 1
        PGSetStartMode(testMap ? 3 : Int32(mode.rawValue))
        appendLog("Game mode: \(mode.title)\(mode == .sandbox ? " on " + GameSettings.sandboxMapTitles[GameSettings.shared.sandboxMap] : "")")
        bootedPreset = GameSettings.shared.graphicsPreset
        bootedFrameRateCap = GameSettings.shared.frameRateCap
        bootedBackend = MugoatOnlineEnabled() ? "legacy-bridge" : "offline"
        requestedFrameInterval = bootedFrameRateCap == 0 ? 0 : bootedFrameRateCap == 30 ? 2 : 1
        let initialSize = GraphicsConfiguration.size(for: bootedPreset, renderHeight: GameSettings.shared.renderHeight, screen: view.bounds.size, matchScreenShape: GameSettings.shared.matchScreenShape)
        requestedRenderSize = (initialSize.0, initialSize.1)
        appendLog("Graphics: " + GraphicsConfiguration.apply(GameSettings.shared, screen: view.bounds.size))
        appendLog("Device: " + GameSettings.shared.tier.summary)
        GameSettings.shared.markBootStarted()
        launchButton.setTitle(L10n.text("Loading…"), for: .disabled); launchButton.setNeedsUpdateConfiguration()
        appendLog("Native touch controls support held buttons, sprint and weapon selection.")
        startAudio()
        let (root, rootNote) = EnginePaths.filesRoot()
        if let rootNote { appendLog(rootNote) }
        // The game's own settings.xml only holds graphics and display options. Some choices in the
        // game's pause menu or auto-detection (MSAA, TXAA, tessellation, shader quality 2) crash Metal
        // or trigger out-of-memory. Overwrite with a sanitized safe baseline before each launch.
        let safeSettingsXml = """
        <?xml version="1.0" encoding="UTF-8"?>
        <Settings>
          <version value="27" />
          <configSource>SMC_AUTO</configSource>
          <graphics>
            <TextureQuality value="0" />
            <ShaderQuality value="1" />
            <ShadowQuality value="1" />
            <ReflectionQuality value="1" />
            <ReflectionMSAA value="0" />
            <SSAO value="0" />
            <AnisotropicFiltering value="0" />
            <MSAA value="0" />
            <MSAAFragments value="0" />
            <MSAAPostProcess value="0" />
            <WaterQuality value="0" />
            <ParticleQuality value="0" />
            <GrassQuality value="0" />
            <DeepSurfaceQuality value="0" />
            <PedLodBias value="0.200000" />
            <VehicleLodBias value="0.000000" />
            <Shadow_Distance value="1.000000" />
            <Shadow_SoftShadows value="0" />
            <Shadow_ParticleShadows value="false" />
            <Shadow_SplitZStart value="0.930000" />
            <Shadow_SplitZEnd value="0.890000" />
            <Shadow_aircraftExpBloom value="0.300000" />
            <Shadow_DisableScreenSizeCheck value="false" />
            <Reflection_MipBlur value="true" />
            <FXAA value="true" />
            <TXAA value="false" />
            <Lighting_FogVolumes value="false" />
            <Shader_SSA value="false" />
            <DX_Version value="2" />
            <CityDensity value="0.000000" />
            <PedVarietyMultiplier value="0.000000" />
            <VehicleVarietyMultiplier value="0.000000" />
            <PostFX value="0" />
            <DoF value="false" />
            <HdStreamingInFlight value="false" />
            <MaxLodScale value="0.000000" />
            <MotionBlurStrength value="0.000000" />
          </graphics>
          <system>
            <Windowed value="2" />
          </system>
          <video>
            <Windowed value="2" />
            <VSync value="1" />
          </video>
        </Settings>
        """
        for mode in ["userdata", "sandbox"] {
            let dir = "\(root)/\(mode)/Documents/Rockstar Games/GTA V"
            let settingsPath = "\(dir)/settings.xml"
            try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
            if let data = safeSettingsXml.data(using: .utf8) {
                try? data.write(to: URL(fileURLWithPath: settingsPath))
                appendLog("Sanitized GTA V graphics settings to safe baseline (\(mode)).")
            }
        }
        var effectiveManifest = path
        if let data = localData {
            PGSetLocalGameFolder(data.path)
            let modsDir = ModManagerViewController.modsDirectory
            let runtimeDir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0].appendingPathComponent("mod_runtime")
            do {
                let updated = try ModernMapIcons.prepare(manifest: URL(fileURLWithPath: effectiveManifest), localData: data, runtime: runtimeDir)
                let changed = updated.path != effectiveManifest
                effectiveManifest = updated.path
                appendLog(changed ? "Map symbols: official icon compatibility archive ready." : "Map symbols: retaining your custom archive.")
            } catch {
                appendLog("Map symbols: retaining the installed archive and built-in alternatives.")
            }
            var dlcData: Data? = nil
            let looseCandidates = [
                data.appendingPathComponent("common/data/dlcList.xml"),
                data.appendingPathComponent("common/data/dlclist.xml")
            ]
            for candidate in looseCandidates {
                if FileManager.default.fileExists(atPath: candidate.path),
                   let d = try? Data(contentsOf: candidate) {
                    dlcData = d
                    break
                }
            }
            if dlcData == nil {
                // Read dlclist.xml directly from update/update.rpf archive if present
                let updateRpfURL = data.appendingPathComponent("update/update.rpf")
                if FileManager.default.fileExists(atPath: updateRpfURL.path),
                   let updateArchive = try? RPFArchive(url: updateRpfURL) {
                    if let entry = updateArchive.entries.first(where: {
                        let p = $0.path.lowercased()
                        return p.hasSuffix("common/data/dlclist.xml") || p == "dlclist.xml"
                    }) {
                        dlcData = try? updateArchive.metadata(entry)
                    }
                }
            }
            if dlcData == nil {
                // Baseline dlclist.xml template so Add-on mods can always be registered into paths
                let baseline = """
                <?xml version="1.0" encoding="utf-8"?>
                <Paths>
                  <Item>platform:\\dlcPacks\\mppatchesng\\</Item>
                  <Item>platform:\\dlcPacks\\mpchristmas2\\</Item>
                  <Item>platform:\\dlcPacks\\mpheist\\</Item>
                  <Item>platform:\\dlcPacks\\patchday1ng\\</Item>
                  <Item>platform:\\dlcPacks\\patchday2ng\\</Item>
                  <Item>platform:\\dlcPacks\\patchday3ng\\</Item>
                </Paths>
                """
                dlcData = baseline.data(using: .utf8)
            }

            if let dlcData {
                do {
                    let baseManifestURL = URL(fileURLWithPath: effectiveManifest)
                    let (overlayManifestURL, catalog) = try ModRuntime.prepare(
                        baseManifest: baseManifestURL,
                        mods: modsDir,
                        runtime: runtimeDir,
                        dlcList: dlcData
                    )
                    effectiveManifest = overlayManifestURL.path
                    loadedModVehicleModels = Set(catalog.vehicleModels)
                    if !catalog.packs.isEmpty {
                        appendLog("ModRuntime: Loaded \(catalog.packs.count) DLC mod packs (\(catalog.vehicleModels.count) vehicles: \(catalog.vehicleModels.joined(separator: ", "))).")
                    }
                    if !catalog.problems.isEmpty {
                        appendLog("ModRuntime warning: " + catalog.problems.joined(separator: " | "))
                    }
                } catch {
                    appendLog("ModRuntime error: \(error.localizedDescription)")
                }
            }
        } else {
            PGSetAssetServer(GameSettings.shared.assetServer)
        }
        AssetPreloader.shared.engineRunning = true
        effectiveManifest.withCString { manifest in
            root.withCString { PGStartEngine(manifest, $0, engineLog, Unmanaged.passUnretained(self).toOpaque()) }
        }
    }

    private func verifyMovement() {
        let testController = GCController.withExtendedGamepad()
        guard let pad = testController.extendedGamepad else {
            appendLog("Movement proof needs the native touch controller.")
            return
        }
        appendLog("Movement proof: capturing the world before native controller input.")
        PGCaptureNativeFrame("movement-before")
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
            guard !self.engineFailed else { return }
            self.proofController = testController
            self.proofInputActive = true
            self.proofInputSamples = 0
            pad.leftThumbstick.setValueForXAxis(0, yAxis: 0.8)
            pad.rightThumbstick.setValueForXAxis(0.25, yAxis: 0)
            self.appendLog("Movement proof: native controller sticks active.")
            DispatchQueue.main.asyncAfter(deadline: .now() + 6) {
                guard !self.engineFailed else { return }
                self.proofInputActive = false
                self.appendLog("Movement proof: \(self.proofInputSamples) controller samples delivered to the engine.")
                pad.leftThumbstick.setValueForXAxis(0, yAxis: 0)
                pad.rightThumbstick.setValueForXAxis(0, yAxis: 0)
                self.proofController = nil
                PGCaptureNativeFrame("movement-after")
                self.appendLog("Movement proof: native controller sticks released.")
            }
        }
    }

    /// Debug: scripted controller input, "step;step;..." with steps "wait:<s>", "hold:<buttons>:<s>"
    /// (buttons: a b x y l1 r1 lt rt down up left right start rx+ rx- ry+ ry-, joined with +), "frame:<name>".
    /// Debug: --watch-memory <address> <length> logs which bytes change between pad-script frames.
    private var watchSnapshot: [UInt8]?
    private func watchMemory(_ label: String) {
        let args = ProcessInfo.processInfo.arguments
        guard let i = args.firstIndex(of: "--watch-memory"), i + 2 < args.count,
              let start = UInt64(args[i + 1]), let length = Int(args[i + 2]) else { return }
        var now = [UInt8](repeating: 0, count: length)
        guard now.withUnsafeMutableBytes({ PGDebugReadMemory(start, $0.baseAddress, UInt64(length)) }) else { return }
        if let before = watchSnapshot {
            var changes: [String] = []
            for k in 0..<length where before[k] != now[k] { changes.append("\(start + UInt64(k)):\(before[k])>\(now[k])") }
            appendLog("Memory watch \(label): \(changes.count) changed " + changes.prefix(400).joined(separator: " "))
        }
        watchSnapshot = now
    }
    private func runPadScript(_ script: String) {
        var at = 0.0
        for step in script.split(separator: ";") {
            let parts = step.split(separator: ":").map(String.init)
            switch parts.first {
            case "wait": at += Double(parts.count > 1 ? parts[1] : "1") ?? 1
            case "frame":
                let name = parts.count > 1 ? parts[1] : "script"
                DispatchQueue.main.asyncAfter(deadline: .now() + at) { guard !self.engineFailed else { return }; PGCaptureNativeFrame(name); self.appendLog("Pad script: frame \(name)"); self.watchMemory(name) }
            case "hold":
                var state = PGPadState(); var held = PadButtons()
                for name in (parts.count > 1 ? parts[1] : "").split(separator: "+") {
                    switch name {
                    case "a": held.insert(.a); case "b": held.insert(.b); case "x": held.insert(.x); case "y": held.insert(.y)
                    case "l1": held.insert(.l1); case "r1": held.insert(.r1); case "down": held.insert(.down); case "up": held.insert(.up)
                    case "left": held.insert(.left); case "right": held.insert(.right); case "start": held.insert(.start)
                    case "lt": state.leftTrigger = 1; case "rt": state.rightTrigger = 1
                    case "rx+": state.rightX = 1; case "rx-": state.rightX = -1; case "ry+": state.rightY = 1; case "ry-": state.rightY = -1
                    default: break
                    }
                }
                state.padButtons = held
                let duration = Double(parts.count > 2 ? parts[2] : "0.3") ?? 0.3
                let label = String(step)
                DispatchQueue.main.asyncAfter(deadline: .now() + at) { guard !self.engineFailed else { return }; self.padProof = state; self.appendLog("Pad script: \(label)") }
                at += duration
                DispatchQueue.main.asyncAfter(deadline: .now() + at) { guard !self.engineFailed else { return }; self.padProof = PGPadState() }
            default: break
            }
        }
        // Hand input back to the touch controls (and controller) when the script ends.
        DispatchQueue.main.asyncAfter(deadline: .now() + at + 0.5) { guard !self.engineFailed else { return }; self.padProof = nil; self.appendLog("Pad script: done") }
    }

    /// Simulator proof that the engine accepts the virtual controller and
    /// that controller aiming locks on: walk, pick a gun from the wheel, aim.
    private func verifyVirtualPad() {
        func log(_ step: String) { appendLog("Pad proof: \(step); input device \(PGLastInputDevice()), targeting mode \(PGTargetingMode())") }
        func pad(_ build: (inout PGPadState) -> Void) -> PGPadState { var s = PGPadState(); build(&s); return s }
        let steps: [(Double, PGPadState?, String?, String?)] = [
            (0, PGPadState(), "before input", "pad-before"),
            (0.5, pad { $0.leftY = 0.8 }, nil, nil),
            (3.5, PGPadState(), "walked forward", "pad-moved"),
            // Weapon wheel: hold L1 and point the right stick at a slot.
            (4.5, pad { $0.padButtons = .l1 }, nil, nil),
            (5.3, pad { $0.padButtons = .l1; $0.rightX = 1 }, "wheel open, pointing right", "pad-wheel"),
            (6.3, PGPadState(), "wheel released", nil),
            (8.0, pad { $0.leftTrigger = 1 }, nil, nil),
            (9.2, pad { $0.leftTrigger = 1 }, "aim held", "pad-aim"),
            (9.4, pad { $0.leftTrigger = 1; $0.rightX = 0.35 }, nil, nil),
            (10.0, pad { $0.leftTrigger = 1; $0.rightTrigger = 1 }, nil, nil),
            (10.6, pad { $0.leftTrigger = 1; $0.rightTrigger = 1 }, "aim and fire", "pad-fire"),
            (11.5, PGPadState(), "released", nil)]
        for (time, state, message, frame) in steps {
            DispatchQueue.main.asyncAfter(deadline: .now() + time) {
                guard !self.engineFailed else { return }
                if let state { self.padProof = state }
                if let message { log(message) }
                if let frame { PGCaptureNativeFrame(frame) }
            }
        }
    }

    private func startAudio() {
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playback, mode: .default, options: [])
            try session.setPreferredSampleRate(48000)
            try session.setActive(true)

            let format = AVAudioFormat(standardFormatWithSampleRate: 48000, channels: 2)!
            let source = AVAudioSourceNode(format: format) { _, _, count, audioBufferList in
                let buffers = UnsafeMutableAudioBufferListPointer(audioBufferList)
                if buffers.count >= 2, let left = buffers[0].mData, let right = buffers[1].mData {
                    PGFillAudio(left.assumingMemoryBound(to: Float.self), right.assumingMemoryBound(to: Float.self), count)
                } else if buffers.count == 1, let mono = buffers[0].mData {
                    var tempRight = [Float](repeating: 0, count: Int(count))
                    PGFillAudio(mono.assumingMemoryBound(to: Float.self), &tempRight, count)
                }
                return noErr
            }
            audioSource = source
            audioEngine.attach(source)
            audioEngine.connect(source, to: audioEngine.mainMixerNode, format: format)
            #if targetEnvironment(simulator)
            // Simulator runs are silent unless --sound is passed (test runs play through the Mac's speakers).
            if !ProcessInfo.processInfo.arguments.contains("--sound") { audioEngine.mainMixerNode.outputVolume = 0 }
            #endif
            // Silent test runs on a phone.
            if ProcessInfo.processInfo.arguments.contains("--mute") { audioEngine.mainMixerNode.outputVolume = 0 }
            audioEngine.prepare()
            try audioEngine.start()
        } catch { appendLog("Native audio setup failed: \(error.localizedDescription)") }
    }

    private func handleVoiceMicChanged(_ enabled: Bool) {
        if enabled {
            let session = AVAudioSession.sharedInstance()
            switch session.recordPermission {
            case .granted:
                self.audioQueue.async { [weak self] in
                    self?.configureMicRecording(enabled: true)
                }
            case .denied:
                appendLog("[Voice] Microphone permission is denied in iOS Settings")
                MugoatVoiceSetMicEnabled(false)
                touchControls.updateVisibility()
            case .undetermined:
                session.requestRecordPermission { [weak self] granted in
                    DispatchQueue.main.async {
                        guard let self = self else { return }
                        if granted {
                            self.audioQueue.async { [weak self] in
                                self?.configureMicRecording(enabled: true)
                            }
                        } else {
                            self.appendLog("[Voice] Microphone permission denied")
                            MugoatVoiceSetMicEnabled(false)
                            self.touchControls.updateVisibility()
                        }
                    }
                }
            @unknown default:
                break
            }
        } else {
            audioQueue.async { [weak self] in
                self?.configureMicRecording(enabled: false)
            }
        }
    }

    private func configureMicRecording(enabled: Bool) {
        let session = AVAudioSession.sharedInstance()
        if enabled {
            do {
                // .defaultToSpeaker already uses the loudspeaker instead of the earpiece; forcing
                // .speaker would also bypass connected headphones and feed the voice back into the mic.
                try session.setCategory(.playAndRecord, mode: .voiceChat, options: [.defaultToSpeaker, .allowBluetooth, .allowBluetoothA2DP])
                try session.setActive(true)
            } catch {
                appendLog("[Voice] AVAudioSession setup failed: \(error.localizedDescription)")
            }

            let inputNode = audioEngine.inputNode
            let bus = 0
            if isMicTapInstalled {
                inputNode.removeTap(onBus: bus)
                isMicTapInstalled = false
            }

            let inputFormat = inputNode.inputFormat(forBus: bus)
            let outputFormat = inputNode.outputFormat(forBus: bus)
            let tapFormat = inputFormat.sampleRate > 0 && inputFormat.channelCount > 0 ? inputFormat
                : (outputFormat.sampleRate > 0 && outputFormat.channelCount > 0 ? outputFormat : nil)
            // No microphone route yet (0 channels): installing a tap would raise an Objective-C exception.
            guard let tapFormat else {
                appendLog("[Voice] No microphone is available; microphone disabled")
                MugoatVoiceSetMicEnabled(false)
                DispatchQueue.main.async { self.touchControls.updateVisibility() }
                restoreGameAudio(micActive: false)
                return
            }

            inputNode.installTap(onBus: bus, bufferSize: 1024, format: tapFormat) { buffer, _ in
                guard let channelData = buffer.floatChannelData?[0] else { return }
                let frameCount = Int(buffer.frameLength)
                let sampleRate = buffer.format.sampleRate
                guard frameCount > 0, sampleRate > 0 else { return }
                if abs(sampleRate - 48000.0) < 1.0 {
                    MugoatVoiceSubmitMicAudio(channelData, UInt32(frameCount))
                } else {
                    let ratio = 48000.0 / sampleRate
                    let targetCount = Int(Double(frameCount) * ratio)
                    if targetCount > 0 {
                        var resampled = [Float](repeating: 0, count: targetCount)
                        for i in 0..<targetCount {
                            let srcIndex = Double(i) / ratio
                            let idx0 = Int(srcIndex)
                            let idx1 = min(idx0 + 1, frameCount - 1)
                            let frac = Float(srcIndex - Double(idx0))
                            resampled[i] = channelData[idx0] * (1.0 - frac) + channelData[idx1] * frac
                        }
                        resampled.withUnsafeBufferPointer { ptr in
                            if let base = ptr.baseAddress {
                                MugoatVoiceSubmitMicAudio(base, UInt32(targetCount))
                            }
                        }
                    }
                }
            }
            isMicTapInstalled = true
            startAudioEngine()
            appendLog("[Voice] Microphone enabled; switching to voice audio")
        } else {
            if isMicTapInstalled {
                audioEngine.inputNode.removeTap(onBus: 0)
                isMicTapInstalled = false
            }
            restoreGameAudio(micActive: false)
            appendLog("[Voice] Microphone disabled; restoring game audio")
        }
    }

    @objc private func handleAudioEngineConfigurationChange(_ notification: Notification) {
        appendLog("[Audio] Audio configuration changed; restarting audio...")
        audioQueue.async { [weak self] in self?.restoreGameAudio(micActive: MugoatVoiceIsMicEnabled()) }
    }

    /// Puts the session back for game sound (or voice chat) and makes sure the engine runs.
    private func restoreGameAudio(micActive: Bool) {
        let session = AVAudioSession.sharedInstance()
        do {
            if micActive {
                // .defaultToSpeaker already uses the loudspeaker instead of the earpiece; forcing
                // .speaker would also bypass connected headphones and feed the voice back into the mic.
                try session.setCategory(.playAndRecord, mode: .voiceChat, options: [.defaultToSpeaker, .allowBluetooth, .allowBluetoothA2DP])
            } else {
                try session.setCategory(.playback, mode: .default, options: [])
            }
            try session.setActive(true)
        } catch {
            appendLog("[Audio] AVAudioSession setup failed: \(error.localizedDescription)")
        }
        startAudioEngine()
    }

    /// Once the mic was used the engine owns an input node; with the .playback category some
    /// devices then refuse to start it, leaving the game silent. Fall back to play-and-record
    /// without voice processing (normal loudspeaker volume) so game sound always comes back.
    private func startAudioEngine() {
        guard !audioEngine.isRunning else { return }
        do {
            audioEngine.prepare()
            try audioEngine.start()
        } catch {
            appendLog("[Audio] Could not start audio (\(error.localizedDescription)); trying fallback mode")
            let session = AVAudioSession.sharedInstance()
            do {
                try session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker, .allowBluetooth, .allowBluetoothA2DP])
                try session.setActive(true)
                audioEngine.prepare()
                try audioEngine.start()
            } catch {
                appendLog("[Audio] Could not restart audio engine: \(error.localizedDescription)")
            }
        }
    }

    @objc private func handleAudioRouteChange(_ notification: Notification) {
        // Headphones plugged in or out: iOS picks the route itself (.defaultToSpeaker covers the
        // earpiece case). Forcing the speaker here sent sound past headphones and caused echo.
        let reason = (notification.userInfo?[AVAudioSessionRouteChangeReasonKey] as? UInt).flatMap(AVAudioSession.RouteChangeReason.init) ?? .unknown
        appendLog("[Audio] Route changed (reason \(reason.rawValue))")
    }

    @objc private func controllerChanged() { pollController() }

    // MARK: Game file server

    /// Back in the app (for example after moving the game folder in Files): look again. Checking every
    /// file takes about a second, so it runs off the main thread.
    @objc private func lookForGameFiles() {
        guard !engineStarted, !GameFolder.isChosen || GameFolder.inAppFolder, !lookingForGameFiles, !GameInstallManager.shared.isRunning else { return }
        lookingForGameFiles = true
        if !GameFolder.isChosen { home.setFiles(.busy, title: L10n.text("Looking for your game files…"), detail: "") }
        DispatchQueue.global(qos: .userInitiated).async {
            GameFolder.findInAppFolder()
            DispatchQueue.main.async {
                self.lookingForGameFiles = false
                self.updateServerStatus()
                if self.launchAfterFileScan {
                    self.launchAfterFileScan = false
                    self.startEngine()
                }
            }
        }
    }
    private var lookingForGameFiles = false
    private var launchAfterFileScan = false
    @objc private func installChanged() {
        guard !engineStarted else { return }
        updateServerStatus()
        // Finished while the game files screen was closed: say how it went here.
        guard presentedViewController == nil, case let .finished(result) = GameInstallManager.shared.state else { return }
        GameInstallManager.shared.acknowledge()
        switch result {
        case .success: appendLog("Game files installed and checked.")
        case let .failure(message): showWhenFree(title: "Couldn't get the game files", message: message)
        case .webPage: showGameFiles()
        }
    }
    /// Shows where the game files come from, and whether Play can start.
    private func updateServerStatus(_ status: String? = nil) {
        // A download running in the background shows on the card (tap it for the full progress).
        if case let .running(update) = GameInstallManager.shared.state {
            home.setFiles(.busy, title: update.title, detail: update.detail.split(separator: "\n").first.map(String.init) ?? L10n.text("Tap to see the progress."))
            updatePlayEnabled()
            return
        }
        // A server address that isn't a web address would boot the game with no files at all.
        let raw = GameSettings.shared.assetServer
        let server = Self.isServerAddress(raw) ? raw : ""
        if GameFolder.isChosen {
            let place = GameFolder.inAppFolder ? "In the ZGTA V folder" : L10n.text("On this iPhone")
            let problems = GameFolder.acceptedProblemCount
            home.setFiles(problems > 0 ? .attention : .ready, title: "\"\(GameFolder.name)\"",
                          detail: problems > 0 ? "\(place) · \(problems) problem \(problems == 1 ? "file" : "files"), playing anyway" : "\(place) · every file checked")
        } else if server.isEmpty, let report = GameFolder.appFolderReport {
            home.setFiles(.problem, title: report.explanation.title, detail: L10n.text("Found your game folder, but it can't be used yet. Tap to see why and how to fix it."))
        } else if server.isEmpty, !raw.isEmpty {
            home.setFiles(.problem, title: L10n.text("Server address isn't a web address"), detail: L10n.text("Tap to change it."))
        } else if server.isEmpty {
            home.setFiles(.attention, title: L10n.text("Add your game files"), detail: GameFolder.archivesFound.isEmpty ? L10n.text("Tap to find them on this iPhone, or get them from a link or an archive.") : L10n.text("Found a game archive. Tap to unpack it."))
        } else if status == "checking…" {
            home.setFiles(.busy, title: L10n.text("Streaming from your server"), detail: server)
        } else {
            let ok = status == nil || status == "connected ✓"
            home.setFiles(ok ? .ready : .problem, title: L10n.text("Streaming from your server"), detail: server + (status.map { " · " + $0 } ?? ""))
        }
        updatePlayEnabled()
    }
    /// Missing files or a mode choice are handled by tapping Play; only a running engine locks it.
    private func updatePlayEnabled() {
        launchButton.isEnabled = !engineStarted && !engineFailed
    }
    static func isServerAddress(_ text: String) -> Bool {
        guard let url = URL(string: text), let scheme = url.scheme?.lowercased(), let host = url.host else { return false }
        return (scheme == "http" || scheme == "https") && !host.isEmpty
    }
    /// The game files screen: checking, finding, downloading and unpacking.
    private func showGameFiles() {
        guard !engineStarted, presentedViewController == nil else { return }
        let controller = GameFilesViewController()
        controller.onChange = { [weak self] in self?.updateServerStatus() }
        controller.onServer = { [weak self] server in
            GameFolder.clear()
            GameSettings.shared.assetServer = server
            self?.appendLog("Game files: streaming from \(server)")
            self?.testAssetServer()
        }
        let navigation = UINavigationController(rootViewController: controller)
        Theme.styleNavigation(navigation)
        navigation.modalPresentationStyle = .fullScreen
        present(navigation, animated: true)
    }
    /// Shows a message once nothing else (like the closing folder picker) is on screen; iOS drops
    /// alerts presented during another presentation.
    private func showWhenFree(title: String, message: String, attempt: Int = 0) {
        if (presentedViewController != nil || transitionCoordinator != nil) && attempt < 20 {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) { self.showWhenFree(title: title, message: message, attempt: attempt + 1) }
            return
        }
        let alert = UIAlertController(title: title, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }
    /// Checks that the server answers with the game's file list.
    private func testAssetServer() {
        var server = GameSettings.shared.assetServer
        while server.hasSuffix("/") { server.removeLast() }
        guard let url = URL(string: server + "/data/manifest.json"), url.scheme?.hasPrefix("http") == true else {
            updateServerStatus("not a valid address"); return
        }
        updateServerStatus("checking…")
        var request = URLRequest(url: url, timeoutInterval: 10)
        request.httpMethod = "HEAD"
        URLSession.shared.dataTask(with: request) { [weak self] _, response, error in
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            DispatchQueue.main.async {
                if code == 200 { self?.updateServerStatus("connected ✓") }
                else if let error { self?.updateServerStatus("can't connect (\(error.localizedDescription))") }
                else { self?.updateServerStatus("answered \(code); is the address the folder with data/ and b/?") }
            }
        }.resume()
    }
    /// The popup after a launch that ran out of memory: what happened, what changed, and the way back.
    private func explainRecovery(_ recovery: GameSettings.BootRecovery) {
        let lowered = recovery.fallback != recovery.failed
        let title = lowered ? L10n.text("Graphics Lowered for Compatibility") : L10n.text("Resolution Reset to Automatic")
        let resolution = recovery.resetHeight.map { String(format: L10n.text(" at %dp"), $0) } ?? ""
        var message = String(format: L10n.text("The previous launch with %@%@ did not finish. Graphics were temporarily adjusted to %@."), recovery.failed.title, resolution, recovery.fallback.title)
        if recovery.resetHeight != nil && lowered { message += " " + L10n.text("Resolution is set to Automatic.") }
        message += " " + L10n.text("You can change these settings again at any time in Settings.")
        let alert = UIAlertController(title: title, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .cancel))
        alert.addAction(UIAlertAction(title: L10n.text("Keep Previous Settings"), style: .default) { [weak self] _ in
            GameSettings.shared.undoRecovery(recovery)
            self?.appendLog("Kept \(recovery.failed.title) after the warning.")
        })
        alert.addAction(UIAlertAction(title: L10n.text("Share log"), style: .default) { _ in
            let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            let logs = ["native-port-previous.log", "native-port.log"].map { documents.appendingPathComponent($0) }
                .filter { FileManager.default.fileExists(atPath: $0.path) }
            let sheet = UIActivityViewController(activityItems: logs, applicationActivities: nil)
            sheet.popoverPresentationController?.sourceView = self.view
            self.present(sheet, animated: true)
        })
        present(alert, animated: true)
    }

    private func logHealth() {
        guard !engineFailed else { return }
        var vm = task_vm_info_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<integer_t>.size)
        let ok = withUnsafeMutablePointer(to: &vm) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) { task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &count) }
        } == KERN_SUCCESS
        let used = ok ? Int(vm.phys_footprint / 1_048_576) : -1
        let free = Int(os_proc_available_memory() / 1_048_576)
        var reads = [UInt64](repeating: 0, count: 6)
        reads.withUnsafeMutableBufferPointer { PGAssetHealth($0.baseAddress) }
        let now = [PGMemoryBudgetClamps()] + reads
        let d = zip(now, lastHealth).map { $0 &- $1 }
        lastHealth = now
        let avgMS = d[1] > 0 ? Double(d[6]) / Double(d[1]) / 1000 : 0
        let fps = PGRenderedFramesPerSecond()
        appendLog(String(format: "Health: device RAM %d MB · app %d MB used, iOS headroom %d MB · guard held back streaming %llu× · reads %llu (%.1f MB, avg %.1f ms, slow %llu, errors %llu) · %.0f FPS",
                         GameSettings.shared.tier.physicalMemoryMB, used, free, d[0], d[1], Double(d[2]) / 1_048_576, avgMS, d[5], d[3], fps))
        let released = PGResourceBytesReleased(), reused = PGResourceBytesReused(), failures = PGResourceReclaimFailures()
        if released > 0 || failures > 0 {
            appendLog(String(format: "Resource pages: returned %.1f MB total · reused %.1f MB total · OS advice failures %llu",
                             Double(released) / 1_048_576, Double(reused) / 1_048_576, failures))
        }
        // Existing ten-second health timer only; no per-frame logging or GPU wait.
        if fps == 0 { PGLogNativeGraphicsProgress() }
    }

    @objc private func leftApp() {
        performanceRun.cancel("The game was hidden. Start another measurement.")
        GameSettings.shared.markBootInterrupted()
    }

    /// The touch-controls layout editor (pre-game, or from Settings).
    private func showLayoutEditor() {
        let editor = ControlsLayoutEditorController()
        editor.modalPresentationStyle = .fullScreen
        editor.onDone = { [weak self] in
            self?.touchControls.updateVisibility()
            self?.appendLog("Controls layout saved (\(ControlsLayout.entries.count) customized controls).")
        }
        (presentedViewController ?? self).present(editor, animated: true)
    }
    private func showSettings() {
        guard presentedViewController == nil else { return }
        performanceRun.cancel("Settings opened. Start another measurement.")
        touchControls.reset()
        let controller = SettingsViewController(engineRunning: engineStarted, runningMode: bootedMode)
        controller.gameModeChanged = { [weak self] in self?.refreshModeChoice() }
        controller.resolutionChanged = { [weak self] in self?.applyLiveResolution() }
        controller.controlsChanged = { [weak self] in self?.touchControls.updateVisibility() }
        controller.editLayout = { [weak self] in self?.showLayoutEditor() }
        controller.targetingChanged = { PGSetTargetingMode(Int32(GameSettings.shared.targetingMode)) }
        controller.openPerformance = { [weak self] in self?.showPerformance() }
        controller.openMods = { [weak controller, weak self] in
            guard let self, let controller else { return }
            let mods = ModManagerViewController(engineRunning: self.engineStarted)
            mods.loadedVehicleModels = self.loadedModVehicleModels
            mods.spawnHandler = { [weak self] model in self?.spawnVehicle(model) }
            mods.teleportHandler = { [weak self] in self?.teleportToWaypoint() }
        mods.cheatsAllowed = !MugoatOnlineEnabled() && (self.bootedMode ?? GameSettings.shared.gameMode) != .sandbox
        mods.cheatHandler = { [weak self] code, mode in self?.applyCheat(code, mode: mode) }
            controller.navigationController?.pushViewController(mods, animated: true)
        }
        controller.openSaves = { [weak controller, weak self] in
            guard let self, let controller else { return }
            let saves = SaveViewController(engineRunning: self.engineStarted)
            controller.navigationController?.pushViewController(saves, animated: true)
        }
        let navigation = UINavigationController(rootViewController: controller)
        Theme.styleNavigation(navigation)
        navigation.modalPresentationStyle = .fullScreen
        present(navigation, animated: true)
    }

    private func showPerformance() {
        let presenter = presentedViewController ?? self
        let result = performanceRun.result
        let summary = result.map {
            var text = String(format: "Average %.1f FPS\nMedian sample %.1f FPS · slowest sample %.1f FPS\n", $0.averageFPS, $0.medianWindowFPS, $0.slowestWindowFPS)
            if let memory = $0.conditions["availableMemoryBytes"] { text += String(format: "Lowest iOS memory headroom: %.0f MB\n", memory.minimum / 1_048_576) }
            if !$0.comparisonWarnings.isEmpty { text += $0.comparisonWarnings.joined(separator: "\n") + "\n" }
            return text + "\n"
        } ?? (performanceRun.reason.isEmpty ? "" : performanceRun.reason + "\n\n")
        let alert = UIAlertController(title: "Performance check", message: summary + "Choose a 30-second check or a 3-minute check with an FPS/heat timeline. Stay in the same place and keep the game visible. Avoid the pause menu. Sampling windows are not a per-frame 1% low. Results stay on this device.", preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Cancel", style: .cancel))
        if worldReadyAt != nil {
            for duration in [30, 180] {
            alert.addAction(UIAlertAction(title: duration == 30 ? "Measure 30s FPS" : "Measure 3min FPS", style: .default) { [weak self] _ in
                guard let self else { return }
                self.dismiss(animated: true) {
                    let s = GameSettings.shared
                    self.performanceRun.start(now: CACurrentMediaTime() * 1000, context: ["platform": "iOS", "build": Theme.appVersion, "mode": self.bootedBackend == "engine-lan" ? "lan" : (self.bootedMode.map { String(describing: $0) } ?? "unknown"), "preset": self.bootedPreset.title, "height": String(s.renderHeight), "fpsCap": String(self.bootedFrameRateCap), "savedFPSCap": String(s.frameRateCap), "runtimeBackend": self.bootedBackend, "frameLimitSource": "Requested engine interval at 60 Hz; application and presentation timing not read back", "startedAt": ISO8601DateFormatter().string(from: Date()), "thermalState": String(ProcessInfo.processInfo.thermalState.rawValue), "renderDimensionsSource": "Requested engine back-buffer dimensions; GPU application not observed", "memorySource": "TASK_VM_INFO phys_footprint and os_proc_available_memory; headroom is an OS estimate", "physicalMemoryBytes": String(ProcessInfo.processInfo.physicalMemory), "osVersion": ProcessInfo.processInfo.operatingSystemVersionString], durationSeconds: duration)
                    self.fpsLabel.isHidden = false
                }
            })
            }
        }
        if let result, let data = try? JSONEncoder().encode(result), let text = String(data: data, encoding: .utf8) {
            alert.addAction(UIAlertAction(title: "Save performance report", style: .default) { [weak presenter] _ in
                guard let presenter else { return }
                let sheet = UIActivityViewController(activityItems: [text], applicationActivities: nil)
                sheet.popoverPresentationController?.sourceView = presenter.view
                presenter.present(sheet, animated: true)
            })
        }
        presenter.present(alert, animated: true)
    }

    private func showModManager() {
        guard presentedViewController == nil else { return }
        touchControls.reset()
        let vc = ModManagerViewController(engineRunning: engineStarted)
        vc.loadedVehicleModels = loadedModVehicleModels
        vc.spawnHandler = { [weak self] model in self?.spawnVehicle(model) }
        vc.teleportHandler = { [weak self] in self?.teleportToWaypoint() }
        vc.cheatsAllowed = !MugoatOnlineEnabled() && (self.bootedMode ?? GameSettings.shared.gameMode) != .sandbox
        vc.cheatHandler = { [weak self] code, mode in self?.applyCheat(code, mode: mode) }
        let navigation = UINavigationController(rootViewController: vc)
        Theme.styleNavigation(navigation)
        present(navigation, animated: true)
    }

    private func showSaves() {
        guard presentedViewController == nil else { return }
        touchControls.reset()
        let navigation = UINavigationController(rootViewController: SaveViewController(engineRunning: engineStarted))
        Theme.styleNavigation(navigation)
        present(navigation, animated: true)
    }

    @objc private func handleThreeFingerTap(_ gesture: UITapGestureRecognizer) {
        showCheatMenu()
    }

    func showCheatMenu() { showModManager() }

    private let actionToast = GameActionToast()

    private func showCheatToast(_ message: String) {
        actionToast.show(message, in: view)
    }

    private var worldToolFeedbackGeneration: UInt64 = 0

    private func spawnVehicle(_ model: String) {
        // Allow only offline play or this app's private Engine LAN world tools.
        guard PGWorldToolsMode() != 0 else {
            showCheatToast("Vehicle spawning is available in offline play and Engine LAN.")
            return
        }
        var clean = model.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if clean == "mbs1k" { clean = "mbslk" }
        guard !clean.isEmpty else { return }
        guard engineStarted && !engineFailed else {
            showCheatToast(L10n.text("Enter the game before spawning a vehicle"))
            return
        }
        // The latest user action owns visible feedback, even when admission fails.
        // An older spawn must not replace a rejected teleport's explanation.
        worldToolFeedbackGeneration &+= 1
        let result = clean.withCString { PGQueueSpawnVehicle($0) }
        if result == 1 {
            showCheatToast(String(format: L10n.text("Spawning: %@"), clean))
            appendLog("Vehicle spawn requested: \(clean)")
            watchVehicleSpawn(clean, generation: worldToolFeedbackGeneration)
        } else {
            showCheatToast(VehicleSpawnFeedback.failure(status: result, model: clean))
        }
    }

    /// Reports how a spawn ended: the engine needs a few frames to stream the model (mods take longer).
    private func watchVehicleSpawn(_ model: String, generation: UInt64, attempt: Int = 0) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
            guard let self, self.engineStarted, !self.engineFailed, self.worldToolFeedbackGeneration == generation else { return }
            switch PGSpawnVehicleStatus() {
            case 2:
                self.showCheatToast(String(format: L10n.text("Spawned: %@"), model))
            case let status where status < 0:
                self.showCheatToast(VehicleSpawnFeedback.failure(status: status, model: model))
                self.appendLog("Vehicle spawn failed: \(model), status \(status)")
            case 1 where attempt < 140:
                self.watchVehicleSpawn(model, generation: generation, attempt: attempt + 1)
            default:
                break
            }
        }
    }

    private func teleportToWaypoint() {
        guard engineStarted && !engineFailed else {
            showCheatToast("Enter the game before using Spawn to waypoint.")
            return
        }
        guard PGWorldToolsMode() != 0 else {
            showCheatToast("Waypoint teleport is available in offline play and Engine LAN.")
            return
        }
        worldToolFeedbackGeneration &+= 1
        guard PGTeleportToWaypoint() else {
            let status = PGTeleportToWaypointStatus()
            showCheatToast("Waypoint teleport not queued: " + (status == 1 ? "A waypoint teleport is already running." :
                WaypointTeleportFeedback.message(status: status) ?? "Another world action is running."))
            return
        }
        showCheatToast("Preparing waypoint destination…")
        appendLog("Waypoint teleport queued")
        watchWaypointTeleport(generation: worldToolFeedbackGeneration)
    }

    private func watchWaypointTeleport(generation: UInt64, attempt: Int = 0) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
            guard let self, self.engineStarted, !self.engineFailed, self.worldToolFeedbackGeneration == generation else { return }
            let status = PGTeleportToWaypointStatus()
            if status == 1 && attempt < 140 {
                self.watchWaypointTeleport(generation: generation, attempt: attempt + 1)
            } else if status != 1, let message = WaypointTeleportFeedback.message(status: status) {
                self.showCheatToast(message)
                self.appendLog("Waypoint teleport ended: \(status)")
            } else if status == 1 {
                self.showCheatToast("Waypoint preparation is still pending. Wait before trying another world action.")
                self.appendLog("Waypoint teleport completion not received")
            }
        }
    }

    private func applyCheat(_ code: String, mode: CheatInputMode = .auto) {
        guard !MugoatOnlineEnabled() && (bootedMode ?? GameSettings.shared.gameMode) != .sandbox else {
            showCheatToast(L10n.text("Cheat codes are unavailable in Sandbox & Online (offline vehicle spawning remains available)"))
            return
        }
        let trimmed = code.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        guard !trimmed.isEmpty else { return }
        if trimmed == "UNFREEZE" || trimmed == "SKIPSCENE" {
            PGForceSkipScene()
            showCheatToast(L10n.text("Sent unstick scene / exit cutscene command"))
            appendLog("Cheat: PGForceSkipScene triggered")
            return
        }
        let modeDesc = mode == .console ? "Console (~)" : mode == .gamepad ? "Gamepad" : L10n.text("Auto")
        showCheatToast(String(format: L10n.text("Activating cheat: %@ (%@)"), trimmed, modeDesc))
        appendLog("Cheat: applying '\(trimmed)' (\(modeDesc))")
        CheatManager.apply(code: trimmed, mode: mode) { [weak self] ok in
            if ok {
                self?.appendLog("Cheat: sent '\(trimmed)' to game engine")
            }
        }
    }
    /// The engine follows back-buffer size changes while running.
    /// A hot phone lowers its clocks and the frame rate drops for minutes. Rendering fewer pixels while
    /// iOS reports serious/critical heat keeps it smoother and lets it cool; the resolution returns after.
    @objc private func thermalStateChanged() {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            let state = ProcessInfo.processInfo.thermalState
            let scale = state == .critical ? 0.65 : state == .serious ? 0.8 : 1.0
            guard scale != self.thermalScale else { return }
            self.thermalScale = scale
            self.appendLog("Thermal state \(state.rawValue): render resolution ×\(scale)")
            self.applyLiveResolution()
        }
    }
    private func applyLiveResolution() {
        guard engineStarted else { return }
        let settings = GameSettings.shared
        let chosenHeight = settings.renderHeight > 0 ? settings.renderHeight : bootedPreset.height
        let renderHeight = thermalScale < 1 ? Int(Double(chosenHeight) * thermalScale) : settings.renderHeight
        let (width, height) = GraphicsConfiguration.size(for: bootedPreset, renderHeight: renderHeight, screen: view.bounds.size, matchScreenShape: settings.matchScreenShape)
        PGSetBackBufferSize(Int32(width), Int32(height))
        requestedRenderSize = (width, height)
        appendLog("Graphics: live resize to \(width)×\(height)")
    }
    private func samplePerformanceConditions(now: Double) {
        guard performanceRun.wantsConditions(now: now) else { return }
        var values: [String: Double] = [
            "availableMemoryBytes": Double(os_proc_available_memory()),
            "thermalState": Double(ProcessInfo.processInfo.thermalState.rawValue),
            "thermalScale": thermalScale,
            "requestedFrameInterval": Double(requestedFrameInterval),
            "secondsSinceWorldReady": max(0, now / 1000 - (worldReadyAt ?? now / 1000)),
            "resourceBytesReleased": Double(PGResourceBytesReleased()),
            "resourceBytesReused": Double(PGResourceBytesReused()),
            "resourceReclaimFailures": Double(PGResourceReclaimFailures()),
            "memoryBudgetClamps": Double(PGMemoryBudgetClamps())
        ]
        if let size = requestedRenderSize {
            values["requestedRenderWidth"] = Double(size.width)
            values["requestedRenderHeight"] = Double(size.height)
        }
        var vm = task_vm_info_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<integer_t>.size)
        let ok = withUnsafeMutablePointer(to: &vm) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) { task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &count) }
        } == KERN_SUCCESS
        if ok { values["appFootprintBytes"] = Double(vm.phys_footprint) }
        performanceRun.observeConditions(values, now: now)
    }
    @objc private func releaseTouchControls() {
        touchControls.reset(publish: false)
        gyro.setRunning(false, orientation: .landscapeRight)
        lastControllerPoll = nil
        hardwareKeys.removeAll()
        KeyboardMouse.shared.releaseAll()
        PGUpdateVirtualPad(PGPadState())
    }

    private func showOnline() {
        guard presentedViewController == nil else { return }
        touchControls.reset()
        let controller = OnlineSettingsViewController(running: engineStarted)
        let navigation = UINavigationController(rootViewController: controller)
        Theme.styleNavigation(navigation); present(navigation, animated: true)
    }
    private var injectedKey = false, releasedKey = false, injectedMouse = false
    private func injectTestInput(sinceWorld: Double) {
        let arguments = ProcessInfo.processInfo.arguments
        if let i = arguments.firstIndex(of: "--inject-key"), i + 3 < arguments.count,
           let key = UInt8(arguments[i + 1], radix: 16), let after = Double(arguments[i + 2]), let hold = Double(arguments[i + 3]) {
            if !injectedKey && sinceWorld > after { injectedKey = true; KeyboardMouse.shared.inject(key: key, down: true); appendLog("Test: key 0x\(arguments[i + 1]) down") }
            if injectedKey && !releasedKey && sinceWorld > after + hold { releasedKey = true; KeyboardMouse.shared.inject(key: key, down: false); appendLog("Test: key 0x\(arguments[i + 1]) up") }
        }
        if let i = arguments.firstIndex(of: "--inject-mouse"), i + 3 < arguments.count,
           let dx = Double(arguments[i + 1]), let dy = Double(arguments[i + 2]), let after = Double(arguments[i + 3]),
           !injectedMouse, sinceWorld > after {
            injectedMouse = true
            KeyboardMouse.shared.inject(dx: dx, dy: dy)
            appendLog("Test: mouse moved \(dx), \(dy)")
        }
    }
    @objc private func pollController() {
        guard !engineFailed else { return }
        guard UIApplication.shared.applicationState == .active else {
            performanceRun.cancel("The game was hidden. Start another measurement.")
            touchControls.reset(publish: false)
            lastControllerPoll = nil
            PGUpdateVirtualPad(PGPadState())
            return
        }
        let now = CACurrentMediaTime()
        if now - lastFPSLabelUpdate >= 0.25 {
            let fps = PGRenderedFramesPerSecond()
            if performanceRun.state == .running {
                samplePerformanceConditions(now: now * 1000)
                performanceRun.sample(fps: fps, now: now * 1000)
                if performanceRun.state == .complete, let result = performanceRun.result {
                    appendLog(String(format: "Performance check: %.1f average FPS, %.1f slowest sampling window, %.0f ms. Not a per-frame 1%% low.", result.averageFPS, result.slowestWindowFPS, result.durationMS))
                }
            }
            let frames = fps > 0 ? String(format: "%.0f FPS", fps) : "— FPS"
            fpsLabel.text = performanceRun.state == .running ? "\(max(0, Int(ceil((performanceRun.endsAt - now * 1000) / 1000))))s test" : frames
            lastFPSLabelUpdate = now
        }
        let elapsed = lastControllerPoll.map { now - $0 } ?? (1.0 / 60.0)
        lastControllerPoll = now
        let gameStatus = PGGameStatus()
        if gameStatus != lastGameStatus {
            lastGameStatus = gameStatus
            appendLog("Game state: control \(gameStatus & 1 != 0 ? "off" : "on")\(gameStatus & 2 != 0 ? ", phone out" : "")\(gameStatus & 4 != 0 ? ", cutscene" : "")\(gameStatus & 8 != 0 ? ", warning screen" : "")\(gameStatus & 16 != 0 ? ", no player" : "")")
            if ProcessInfo.processInfo.arguments.contains("--capture-state") { PGCaptureNativeFrame("state-\(gameStatus)-\(Int(now))") }
        }
        if let padProof { PGUpdateVirtualPad(padProof); return }
        // Everything reaches the engine as its own controller, so controller
        // features (assisted aim, analog steering and throttle) apply.
        var state = PGPadState()
        var hasController = false
        if let controller = GCController.controllers().first(where: { $0.extendedGamepad != nil }), let pad = controller.extendedGamepad {
            state = PGPadState(gamepad: pad)
            hasController = true
            if diagnosticsOverlay?.isHidden != true { controllerLabel.text = "Controller: \(controller.vendorName ?? "Gamepad")" }
        } else if diagnosticsOverlay?.isHidden != true {
            controllerLabel.text = L10n.text("Touch controls ready")
        }
        // With a controller connected the touch controls step aside (Settings › Touch controls).
        // Keyboard and mouse: every frame while the game runs (keys go straight to the game as they change).
        let keyboardMouse = GameSettings.shared.keyboardMouse
        if engineStarted && keyboardMouse { KeyboardMouse.shared.send(focused: true) }
        // Automation: --inject-key <vk> <seconds after WORLD_READY> <hold seconds>, --inject-mouse <dx> <dy> <seconds after>.
        if let ready = worldReadyAt { injectTestInput(sinceWorld: now - ready) }
        let pcControls = keyboardMouse && KeyboardMouse.shared.hasKeyboard && KeyboardMouse.shared.hasMouse
        let previewing = ProcessInfo.processInfo.arguments.contains("--touch-controls-preview")
        let touchActive = touchControlsAvailable && (previewing || !((hasController || pcControls) && GameSettings.shared.hideTouchWithController))
        touchControls.isHidden = !touchActive
        var vehicle = touchActive ? PGCurrentTouchContext() : 0
        var pauseMenu = PGPauseMenuActive()
        // Debug: --preview-context <vehicle type + 1 | menu> to review a layout.
        let arguments = ProcessInfo.processInfo.arguments
        if let i = arguments.firstIndex(of: "--preview-context"), i + 1 < arguments.count {
            if arguments[i + 1] == "menu" { pauseMenu = true } else { vehicle = UInt32(arguments[i + 1]) ?? 0 }
        }
        // Debug: --context-after <seconds after WORLD_READY> <vehicle type + 1> simulates entering a vehicle.
        if let i = arguments.firstIndex(of: "--context-after"), i + 2 < arguments.count, let ready = worldReadyAt,
           let after = Double(arguments[i + 1]), now - ready > after { vehicle = UInt32(arguments[i + 2]) ?? vehicle }
        if touchActive {
            // Debug: --preview-prompt shows the Accept/Back prompt layout, --preview-phone the phone dock.
            var status = gameStatus
            if arguments.contains("--preview-prompt") { status |= 1 }
            if arguments.contains("--preview-phone") { status |= 2 }
            // The same D-pad-down control opens the Story character selector
            // or, on a multiplayer tap, the engine's lobby player list.
            touchControls.characterSwitchEnabled = PGWorldToolsMode() == 2 || bootedMode == .story || arguments.contains("--preview-switch")
            touchControls.updateGameState(status)
            touchControls.updateContext(vehicle: vehicle, pauseMenu: pauseMenu)
            var hints = PGReadControlHints(vehicle)
            // Debug: --preview-hints special,detonate,help shows the situational buttons.
            if let i = arguments.firstIndex(of: "--preview-hints"), i + 1 < arguments.count {
                let wanted = arguments[i + 1]
                if wanted.contains("special") { hints.specialShown = true; hints.specialReady = true; hints.specialFill = 0.7 }
                if wanted.contains("detonate") { hints.canDetonate = true }
                if wanted.contains("help") { hints.helpShown = true; hints.helpContext = true }
            }
            touchControls.updateHints(hints)
            let touch = touchControls.padState(elapsed: elapsed)
            touchControls.sendCameraMotion()
            if ProcessInfo.processInfo.arguments.contains("--trace-touch-controls") {
                let sample = String(format: "Touch pad: buttons=%u move=%.2f,%.2f look=%.2f,%.2f triggers=%.2f,%.2f device=%d", touch.buttons, touch.leftX, touch.leftY, touch.rightX, touch.rightY, touch.leftTrigger, touch.rightTrigger, PGLastInputDevice())
                if sample != lastTouchInputTrace { lastTouchInputTrace = sample; appendLog(sample) }
            }
            state.merge(touch)
        } else {
            PGTouchCameraEnabled(false)
        }
        if !pcControls {
            var keys = PGPadState()
            func held(_ key: UIKeyboardHIDUsage) -> Float { hardwareKeys.contains(key) ? 1 : 0 }
            let isPlane = (vehicle == 2 || vehicle == 17 || vehicle == 9 || vehicle == 10 || vehicle == 16)
            if isPlane {
                // Aircraft flight: W throttle up, S throttle down, Q yaw left, E yaw right, A/D roll, Arrows pitch
                keys.leftX = held(.keyboardD) - held(.keyboardA)
                let pitch = held(.keyboardUpArrow) - held(.keyboardDownArrow)
                keys.leftY = pitch != 0 ? pitch : (held(.keyboardW) - held(.keyboardS))
                keys.rightTrigger = max(held(.keyboardX), held(.keyboardW))
                keys.leftTrigger = max(held(.keyboardZ), held(.keyboardS))
            } else if vehicle != 0 {
                // Ground / water vehicles: W gas, S brake/reverse, A/D steer
                keys.leftX = held(.keyboardD) - held(.keyboardA)
                keys.leftY = 0
                keys.rightTrigger = max(held(.keyboardX), held(.keyboardW))
                keys.leftTrigger = max(held(.keyboardZ), held(.keyboardS))
            } else {
                // On foot: WASD move
                keys.leftX = held(.keyboardD) - held(.keyboardA)
                keys.leftY = held(.keyboardW) - held(.keyboardS)
                keys.leftTrigger = held(.keyboardZ); keys.rightTrigger = held(.keyboardX)
            }
            keys.rightX = held(.keyboardRightArrow) - held(.keyboardLeftArrow)
            keys.rightY = isPlane ? 0 : (held(.keyboardUpArrow) - held(.keyboardDownArrow))
            let map: [(UIKeyboardHIDUsage, PadButtons)] = [
                (.keyboardSpacebar, .x), (.keyboardLeftShift, .a), (.keyboardF, .y), (.keyboardR, .b),
                (.keyboardQ, .l1), (.keyboardE, .r1), (.keyboardTab, isPlane ? .x : .l1), (.keyboardV, .select), (.keyboardM, .select),
                (.keyboardEscape, .start), (.keyboardP, .start), (.keyboardLeftControl, .l3),
                (.keyboardC, .r3), (.keyboardReturnOrEnter, .a), (.keyboardDeleteOrBackspace, .b),
                (.keyboardI, .up), (.keyboardK, .down), (.keyboardJ, .left), (.keyboardL, .right)
            ]
            var keyButtons = PadButtons()
            for (key, bit) in map where hardwareKeys.contains(key) { keyButtons.insert(bit) }
            keys.padButtons = keyButtons
            state.merge(keys)
            if diagnosticsOverlay?.isHidden != true && !hardwareKeys.isEmpty && !hasController {
                controllerLabel.text = "Keyboard (Gamepad)"
            }
        }
        // Optional gyro: phone rotation adds to the right stick.
        let settings = GameSettings.shared
        let onFoot = vehicle == 0
        let driving = touchControls.context.driving
        let tiltWanted = touchActive && driving && settings.tiltSteer != .off
        let gyroWanted = touchActive && ((settings.gyroAim != .off && !touchControls.flyingWithRightStick && touchControls.context != .menu) || tiltWanted)
        let orientation = view.window?.windowScene?.interfaceOrientation ?? .landscapeRight
        gyro.setRunning(gyroWanted, orientation: orientation)
        if tiltWanted, let angle = gyro.steeringAngle() {
            // The neutral angle is however the phone is held on entering.
            if tiltSince == nil { tiltSince = now }
            if tiltNeutral == nil, now - (tiltSince ?? now) > 0.15 { tiltNeutral = angle }
            if let neutral = tiltNeutral {
                var degrees = (angle - neutral) * 180 / .pi
                degrees = abs(degrees) < 1.5 ? 0 : degrees - copysign(1.5, degrees)
                let raw = max(-1, min(1, degrees / settings.tiltFullLock))
                let curved = copysign(pow(abs(raw), 1.4), raw)
                tiltSmoothed += (curved - tiltSmoothed) * min(1, elapsed / 0.06)
                let fadeIn = min(1, (now - (tiltSince ?? now) - 0.15) / 0.3)
                let tilt = Float(tiltSmoothed * max(0, fadeIn))
                if settings.tiltSteer == .full && abs(state.leftX) < 0.05 { state.leftX = tilt }
                else if settings.tiltSteer == .assist { state.leftX = max(-1, min(1, state.leftX + tilt * 0.6)) }
            }
        } else if !driving {
            tiltNeutral = nil; tiltSince = nil; tiltSmoothed = 0
        }
        if gyroWanted && settings.gyroAim != .off {
            let aiming = touchControls.aiming || state.leftTrigger > 0.1
            let active = aiming || (settings.gyroAim == .always && onFoot)
            let rate = gyro.rate(active: active, elapsed: elapsed)
            // About 2 rad/s of phone rotation is a full stick at sensitivity 1.
            let gain = 350 * settings.gyroSensitivity
            let invert: CGFloat = settings.gyroInvertY ? -1 : 1
            state.rightX = max(-1, min(1, state.rightX + TouchControlsView.lookAxis(rate.dx * gain)))
            state.rightY = max(-1, min(1, state.rightY - TouchControlsView.lookAxis(rate.dy * gain * invert)))
        }
        // A controller's right stick picks on the radio wheel (its own inputs have no controller
        // binding in this build; see PGSetRadioWheelDirection). The camera ignores the stick meanwhile.
        if hasController, engineStarted, let pad = GCController.controllers().first(where: { $0.extendedGamepad != nil })?.extendedGamepad,
           PGReadControlHints(PGCurrentTouchContext()).radioWheelOpen {
            let x = pad.rightThumbstick.xAxis.value, y = pad.rightThumbstick.yAxis.value, length = hypotf(x, y)
            PGSetRadioWheelDirection(length > 0.3 ? x / length : 0, length > 0.3 ? y / length : 0, true)
            state.rightX = 0; state.rightY = 0
            controllerRadioWheel = true
        } else if controllerRadioWheel {
            controllerRadioWheel = false
            PGSetRadioWheelDirection(0, 0, false)
        }
        if !PGIsCheatInProgress() {
            PGUpdateVirtualPad(state)
        }
    }
    private var controllerRadioWheel = false

    func mtkView(_ view: MTKView, drawableSizeWillChange size: CGSize) {}
    func draw(in view: MTKView) {
        guard let descriptor = view.currentRenderPassDescriptor, let drawable = view.currentDrawable,
              let command = queue?.makeCommandBuffer(), let encoder = command.makeRenderCommandEncoder(descriptor: descriptor) else { return }
        encoder.endEncoding()
        command.present(drawable)
        command.commit()
    }
}
