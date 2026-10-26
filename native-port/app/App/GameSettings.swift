import Foundation

/// How the engine starts: the same two choices as the web build's loading
/// screen (Story Mode / Sandbox Mode). Raw values are the engine's start mode.
enum GameMode: Int, CaseIterable {
    case story = 1
    case sandbox = 2

    var title: String { self == .story ? L10n.text("Story mode") : L10n.text("Free roam") }
    var detail: String {
        switch self {
        case .story: return L10n.text("Continue your latest save or start a new story.")
        case .sandbox: return L10n.text("Explore the map and try every weapon in free roam.")
        }
    }
}

/// Player preferences, kept in UserDefaults across launches.
final class GameSettings {
    static let shared = GameSettings()
    private let defaults = UserDefaults.standard

    var gyroAim: GyroAimMode {
        get { GyroAimMode(rawValue: defaults.integer(forKey: "gyroAim")) ?? .off }
        set { defaults.set(newValue.rawValue, forKey: "gyroAim") }
    }
    var gyroSensitivity: Double {
        get { defaults.object(forKey: "gyroSensitivity") as? Double ?? 1.0 }
        set { defaults.set(newValue, forKey: "gyroSensitivity") }
    }
    var gyroInvertY: Bool {
        get { defaults.bool(forKey: "gyroInvertY") }
        set { defaults.set(newValue, forKey: "gyroInvertY") }
    }
    var invertLookY: Bool {
        get { defaults.bool(forKey: "invertLookY") }
        set { defaults.set(newValue, forKey: "invertLookY") }
    }

    var tiltSteer: TiltSteerMode {
        get { TiltSteerMode(rawValue: defaults.integer(forKey: "tiltSteer")) ?? .off }
        set { defaults.set(newValue.rawValue, forKey: "tiltSteer") }
    }
    /// Phone rotation, in degrees, for full steering lock.
    var tiltFullLock: Double {
        get { defaults.object(forKey: "tiltFullLock") as? Double ?? 22 }
        set { defaults.set(min(max(newValue, 10), 45), forKey: "tiltFullLock") }
    }

    /// Your own server with the game files, e.g. https://my-pc.tailnet.ts.net.
    /// A cloud build can bake in a default (Info.plist PGDefaultAssetServer).
    var assetServer: String {
        get {
            if let saved = defaults.string(forKey: "assetServer"), !saved.isEmpty { return saved }
            return Bundle.main.object(forInfoDictionaryKey: "PGDefaultAssetServer") as? String ?? ""
        }
        set { defaults.set(newValue.trimmingCharacters(in: .whitespacesAndNewlines), forKey: "assetServer") }
    }

    // Touch controls.
    var controlOpacity: Double {
        get { defaults.object(forKey: "controlOpacity") as? Double ?? 0.8 }
        set { defaults.set(min(max(newValue, 0.2), 1), forKey: "controlOpacity") }
    }
    var controlScale: Double {
        get { defaults.object(forKey: "controlScale") as? Double ?? 1.0 }
        set { defaults.set(min(max(newValue, 0.7), 1.5), forKey: "controlScale") }
    }
    var lookSensitivity: Double {
        get { defaults.object(forKey: "lookSensitivity") as? Double ?? 2.5 }
        set { defaults.set(min(max(newValue, 0.5), 10.0), forKey: "lookSensitivity") }
    }
    /// Camera speed while aiming (the game slows the camera when aiming).
    var aimSensitivity: Double {
        get { defaults.object(forKey: "aimSensitivity") as? Double ?? 2.5 }
        set { defaults.set(min(max(newValue, 0.5), 10.0), forKey: "aimSensitivity") }
    }
    /// Fire also locks on, like the classic mobile GTA ports.
    var fireAlsoAims: Bool {
        get { defaults.object(forKey: "fireAlsoAims") as? Bool ?? true }
        set { defaults.set(newValue, forKey: "fireAlsoAims") }
    }

    /// GTA's targeting preference: 0 traditional lock, 1 assisted aim,
    /// 2 assisted free aim, 3 free aim. Touch play defaults to assisted.
    var targetingMode: Int {
        get { defaults.object(forKey: "targetingMode") as? Int ?? 1 }
        set { defaults.set(newValue, forKey: "targetingMode") }
    }
    static let targetingTitles = [L10n.text("Traditional lock-on"), L10n.text("Assisted aim"), L10n.text("Assisted free aim"), L10n.text("Free aim")]

    /// nil until the player has chosen on the launch screen.
    /// Only the Los Santos map is exposed in ZGTA V.
    var sandboxMap: Int {
        get { 0 }
        set { defaults.set(0, forKey: "sandboxMap") }
    }
    static let sandboxMapTitles = ["Los Santos"]
    var gameModeChoice: GameMode? {
        get { (defaults.object(forKey: "gameMode") as? Int).flatMap(GameMode.init) }
        set { defaults.set(newValue?.rawValue, forKey: "gameMode") }
    }
    /// Sandbox was the only mode before the choice existed.
    var gameMode: GameMode {
        get { gameModeChoice ?? .sandbox }
        set { gameModeChoice = newValue }
    }

    // Graphics. The default comes from the measured device tier.
    lazy var tier = DeviceTier.probe()
    var graphicsPreset: GraphicsPreset {
        // integer(forKey:) also reads "-graphicsPreset 4" given as a launch argument (a string).
        get { defaults.object(forKey: "graphicsPreset") != nil ? GraphicsPreset(rawValue: defaults.integer(forKey: "graphicsPreset")) ?? tier.recommended : tier.recommended }
        set { defaults.set(newValue.rawValue, forKey: "graphicsPreset") }
    }
    var resolutionScale: Double {
        get { defaults.object(forKey: "resolutionScale") as? Double ?? 1.0 }
        set { defaults.set(min(max(newValue, 0.5), 1.0), forKey: "resolutionScale") }
    }
    /// Render at the screen's shape instead of a stretched 16:9 picture.
    /// Render height in pixels, changeable while playing; 0 follows the detail preset.
    var renderHeight: Int {
        get { defaults.integer(forKey: "renderHeight") }
        set { defaults.set(max(0, newValue), forKey: "renderHeight") }
    }
    var matchScreenShape: Bool {
        get { defaults.object(forKey: "matchScreenShape") as? Bool ?? true }
        set { defaults.set(newValue, forKey: "matchScreenShape") }
    }
    /// A hardware keyboard and mouse play through the game's own PC controls (on by default).
    var keyboardMouse: Bool {
        get { defaults.object(forKey: "keyboardMouse") as? Bool ?? true }
        set { defaults.set(newValue, forKey: "keyboardMouse") }
    }
    /// Left/right buttons instead of the steering stick in vehicles. Off by default.
    var steeringButtons: Bool {
        get { defaults.bool(forKey: "steeringButtons") }
        set { defaults.set(newValue, forKey: "steeringButtons") }
    }
    var hideTouchWithController: Bool {
        get { defaults.object(forKey: "hideTouchWithController") as? Bool ?? true }
        set { defaults.set(newValue, forKey: "hideTouchWithController") }
    }
    var engineMemoryMB: Int {
        get { defaults.integer(forKey: "engineMemoryMB") }
        set { defaults.set(newValue <= 0 ? 0 : min(max(newValue, 3072), 16384), forKey: "engineMemoryMB") }
    }
    var sixtyFPS: Bool { frameRateCap != 30 }
    /// Frame rate cap: 30, 60, or 0 for unlocked (up to the screen's refresh rate, 120 on ProMotion).
    var frameRateCap: Int {
        get {
            if let cap = defaults.object(forKey: "frameRateCap") as? Int, [0, 30, 60].contains(cap) { return cap }
            return defaults.bool(forKey: "sixtyFPS") ? 60 : 30 // older versions stored a 60 FPS switch
        }
        set { defaults.set(newValue, forKey: "frameRateCap") }
    }
    static func frameRateTitle(_ cap: Int) -> String { cap == 0 ? L10n.text("Unlocked") : "\(cap) FPS" }

    // Crash fallback: a launch that never reached a stable world is treated
    // as a memory kill, and the last preset that worked is restored.
    private var bootPending: Bool {
        get { defaults.bool(forKey: "graphicsBootPending") }
        set { defaults.set(newValue, forKey: "graphicsBootPending") }
    }
    private var lastGoodPreset: GraphicsPreset? {
        get { (defaults.object(forKey: "lastGoodPreset") as? Int).flatMap(GraphicsPreset.init) }
        set { defaults.set(newValue?.rawValue, forKey: "lastGoodPreset") }
    }
    /// What changed after a launch that did not finish (shown once, in a popup, on the next start).
    struct BootRecovery {
        let failed: GraphicsPreset
        let fallback: GraphicsPreset
        /// The custom resolution that was set back to Auto, if any.
        let resetHeight: Int?
        let processAllowanceMB: Int
    }
    /// Lowers the settings when the previous launch failed. Returns what changed, or nil.
    func recoverFromFailedBoot() -> BootRecovery? {
        #if targetEnvironment(simulator)
        // Simulator runs are often stopped from Xcode; only phones need this (unless testing it).
        if !ProcessInfo.processInfo.arguments.contains("--simulate-failed-boot") { bootPending = false; return nil }
        #endif
        guard bootPending else { return nil }
        bootPending = false
        // Devices with 6GB+ RAM (iPad M-series, high-end iPhones) have plenty of memory.
        // Never automatically downgrade graphics or reset custom resolution on these devices.
        if tier.physicalMemoryMB >= 6000 { return nil }
        let failed = graphicsPreset
        // A preset that already ran stably on this phone is not the problem (the app was more likely
        // closed by an update or by Xcode): keep it, and only undo a resolution raised above it.
        let fallback = lastGoodPreset == failed ? failed
            : lastGoodPreset.flatMap { $0.rawValue < failed.rawValue ? $0 : nil }
            ?? GraphicsPreset(rawValue: max(0, min(failed.rawValue - 1, tier.recommended.rawValue))) ?? .performance
        // A custom resolution above the fallback's own also costs memory: back to Auto (unless that
        // resolution already ran stably with this preset).
        let provenHeight = fallback == lastGoodPreset ? defaults.integer(forKey: "lastGoodRenderHeight") : 0
        let resetHeight = renderHeight > max(fallback.height, provenHeight) ? renderHeight : nil
        guard fallback != failed || resetHeight != nil else { return nil }
        graphicsPreset = fallback
        if resetHeight != nil { renderHeight = 0 }
        return BootRecovery(failed: failed, fallback: fallback, resetHeight: resetHeight, processAllowanceMB: tier.processAllowanceMB)
    }
    /// "Try again anyway" in the popup: put the settings back as they were.
    func undoRecovery(_ recovery: BootRecovery) {
        graphicsPreset = recovery.failed
        if let height = recovery.resetHeight { renderHeight = height }
    }
    func markBootStarted() { bootPending = true }
    /// Leaving the app is not a crash.
    func markBootInterrupted() { bootPending = false }
    func markBootStable() {
        bootPending = false
        lastGoodPreset = graphicsPreset
        defaults.set(renderHeight == 0 ? graphicsPreset.height : renderHeight, forKey: "lastGoodRenderHeight")
    }
}
