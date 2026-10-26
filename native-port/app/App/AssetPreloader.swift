import UIKit

extension Notification.Name {
    static let assetPreloadChanged = Notification.Name("AssetPreloadChanged")
}

/// Where the engine keeps its files. The asset cache sits next to this folder
/// (`AssetCache-<version>`), so the preloader and the engine must agree on it.
enum EnginePaths {
    static var manifest: String? {
        if let bundlePath = Bundle.main.path(forResource: "manifest", ofType: "json"),
           FileManager.default.fileExists(atPath: bundlePath) {
            return bundlePath
        }
        if let folder = GameFolder.open() {
            let candidate1 = folder.appendingPathComponent("data/manifest.json").path
            if FileManager.default.fileExists(atPath: candidate1) { return candidate1 }
            let candidate2 = folder.appendingPathComponent("manifest.json").path
            if FileManager.default.fileExists(atPath: candidate2) { return candidate2 }
        }
        return nil
    }

    /// Returns the engine files root and, on the simulator, an optional note.
    static func filesRoot() -> (path: String, note: String?) {
        let base = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        // Upgrading the old Muguet-based build must preserve its actual saves.
        // Reuse that root when present; never overwrite or delete either folder.
        let legacy = base.appendingPathComponent("saves")
        let folder = FileManager.default.fileExists(atPath: legacy.path) ? legacy : base.appendingPathComponent("EngineFiles")
        let documents = folder.path
        #if targetEnvironment(simulator)
        // PG_SIMULATOR_ENGINE_ROOT (or PG_ENGINE_FILES_ROOT) keeps a test run's saves and cache apart.
        let environment = ProcessInfo.processInfo.environment
        guard let simulatorRoot = environment["PG_SIMULATOR_ENGINE_ROOT"] ?? environment["PG_ENGINE_FILES_ROOT"] else { return (documents, nil) }
        do {
            try FileManager.default.createDirectory(atPath: simulatorRoot, withIntermediateDirectories: true)
            return (simulatorRoot, nil)
        } catch {
            return (documents, "Simulator uses its app container for engine files.")
        }
        #else
        return (documents, nil)
        #endif
    }
}

/// L10n.text("Download all game files"): copies every archive into the same block cache
/// that streaming fills, so play no longer depends on the server. The native
/// side (Source/NativeAssetPreload.h) does the work; this class keeps the
/// player's choice, checks storage, estimates time and handles app lifecycle.
/// Progress is stored in the cache itself, so nothing is lost on relaunch.
final class AssetPreloader {
    static let shared = AssetPreloader()

    enum Phase: Equatable {
        case unavailable(String)
        case idle
        case downloading
        case paused
        case complete
    }

    /// Space left free on top of the download, for saves, shaders and iOS.
    static let reserveBytes: UInt64 = 1_000_000_000

    private let defaults = UserDefaults.standard
    private let arguments = ProcessInfo.processInfo.arguments
    /// Debug subset: comma-separated path prefixes (e.g. `common/,x64/data/`).
    let filter: String?
    private(set) var totalBytes: UInt64 = 0
    private(set) var cachedBytes: UInt64 = 0
    private(set) var fileCount: UInt32 = 0
    private(set) var measured = false
    private(set) var lastError: String?
    private var prepared = false
    private var running = false
    /// Removal in progress: no download may start until it is done.
    private(set) var removing = false
    private var timer: Timer?
    private var samples: [(time: CFTimeInterval, bytes: UInt64)] = []
    private var backgroundTask: UIBackgroundTaskIdentifier = .invalid

    /// The player asked for all files and has not cancelled.
    private(set) var wanted: Bool {
        get { defaults.bool(forKey: "assetPreloadWanted") }
        set { defaults.set(newValue, forKey: "assetPreloadWanted") }
    }
    /// Paused by the player (not by iOS or a network error).
    private(set) var userPaused: Bool {
        get { defaults.bool(forKey: "assetPreloadPaused") }
        set { defaults.set(newValue, forKey: "assetPreloadPaused") }
    }
    /// While the game runs, fewer download lanes leave bandwidth to demand reads.
    var engineRunning = false {
        didSet { PGAssetPreloadSetLanes(engineRunning ? 2 : 6) }
    }

    private init() {
        if let i = arguments.firstIndex(of: "--preload-filter"), i + 1 < arguments.count { filter = arguments[i + 1] } else { filter = nil }
        let center = NotificationCenter.default
        center.addObserver(self, selector: #selector(enteredBackground), name: UIApplication.didEnterBackgroundNotification, object: nil)
        center.addObserver(self, selector: #selector(becameActive), name: UIApplication.didBecomeActiveNotification, object: nil)
    }

    var phase: Phase {
        if GameFolder.isChosen {
            return .unavailable("The game files are already on this iPhone (folder \"\(GameFolder.name)\"), so nothing needs downloading.")
        }
        if prepared && !PGAssetPreloadSupported() {
            return .unavailable("The simulator reads the Mac's game files directly. Launch with --stream-assets to test downloads.")
        }
        if running { return .downloading }
        if measured && totalBytes > 0 && cachedBytes >= totalBytes { return .complete }
        if wanted { return .paused }
        return .idle
    }
    var fraction: Double { totalBytes > 0 ? min(1, Double(cachedBytes) / Double(totalBytes)) : 0 }
    var missingBytes: UInt64 { totalBytes > cachedBytes ? totalBytes - cachedBytes : 0 }

    /// Download speed over the last 20 seconds, once there are 3 seconds of data.
    var bytesPerSecond: Double? {
        guard let first = samples.first, let last = samples.last, last.time - first.time >= 3 else { return nil }
        return Double(last.bytes - first.bytes) / (last.time - first.time)
    }
    var secondsRemaining: Double? {
        guard let rate = bytesPerSecond, rate > 1024 else { return nil }
        return Double(missingBytes) / rate
    }

    /// Opens the cache the way the engine will. Cheap after the first call.
    func prepare() {
        // Local launches build a mod/icon manifest immediately before Play.
        // NativeAssets freezes its first manifest, so preparing the base list
        // here would discard that launch overlay (including appended DLC IDs).
        guard !GameFolder.isChosen else { return }
        guard !prepared, let manifest = EnginePaths.manifest else { return }
        let root = EnginePaths.filesRoot().path
        manifest.withCString { m in root.withCString { PGAssetCachePrepare(m, $0) } }
        prepared = true
    }

    /// Re-reads how much is on the device (presence maps only).
    func refresh(completion: (() -> Void)? = nil) {
        guard !GameFolder.isChosen else { measured = true; notify(); completion?(); return }
        prepare()
        guard PGAssetPreloadSupported() else { measured = true; notify(); completion?(); return }
        let filter = self.filter
        DispatchQueue.global(qos: .utility).async {
            var total: UInt64 = 0, cached: UInt64 = 0, files: UInt32 = 0
            if let filter { filter.withCString { PGAssetPreloadMeasure($0, &total, &cached, &files) } }
            else { PGAssetPreloadMeasure(nil, &total, &cached, &files) }
            DispatchQueue.main.async {
                if !self.running { self.cachedBytes = cached }
                self.totalBytes = total; self.fileCount = files; self.measured = true
                self.notify(); completion?()
            }
        }
    }

    /// A previously opened remote cache cannot be replaced while its jobs may
    /// still read it. Restart once after switching to a local folder in-process.
    var localLaunchNeedsRestart: Bool { GameFolder.isChosen && prepared }

    /// Free space for app data, as iOS reports it for important downloads.
    func availableBytes() -> UInt64 {
        if let i = arguments.firstIndex(of: "--preload-pretend-free-mb"), i + 1 < arguments.count, let mb = UInt64(arguments[i + 1]) {
            return mb * 1_000_000
        }
        let url = URL(fileURLWithPath: NSHomeDirectory())
        let values = try? url.resourceValues(forKeys: [.volumeAvailableCapacityForImportantUsageKey])
        return UInt64(max(0, values?.volumeAvailableCapacityForImportantUsage ?? 0))
    }

    /// Starts or resumes. Returns a message when the download cannot start.
    @discardableResult
    func start() -> String? {
        guard !GameFolder.isChosen else { return "The game files are already on this iPhone; no download is needed." }
        prepare()
        guard !GameSettings.shared.assetServer.isEmpty else { return "Set your game file server first (Play screen)." }
        PGSetAssetServer(GameSettings.shared.assetServer)
        guard PGAssetPreloadSupported() else { return "Downloads are not available here." }
        if running { return nil }
        if removing { return "Still removing files. Try again in a moment." }
        var total: UInt64 = 0, cached: UInt64 = 0, files: UInt32 = 0
        if let filter { filter.withCString { PGAssetPreloadMeasure($0, &total, &cached, &files) } }
        else { PGAssetPreloadMeasure(nil, &total, &cached, &files) }
        totalBytes = total; cachedBytes = cached; fileCount = files; measured = true
        if cached >= total { wanted = true; userPaused = false; lastError = nil; notify(); return nil }
        let needed = total - cached + Self.reserveBytes
        let free = availableBytes()
        if free < needed {
            let message = "Not enough free space. The rest of the game needs \(Self.format(total - cached)) plus \(Self.format(Self.reserveBytes)) to spare, but only \(Self.format(free)) is free. Free up \(Self.format(needed - free)) and try again."
            lastError = message
            notify()
            return message
        }
        wanted = true
        userPaused = false
        lastError = nil
        samples = []
        let lanes: UInt32 = engineRunning ? 2 : 6
        let started = filter.map { $0.withCString { PGAssetPreloadStart($0, lanes) } } ?? PGAssetPreloadStart(nil, lanes)
        guard started else { return "The download could not start." }
        running = true
        NSLog("[asset-preload] started: %llu of %llu bytes on device, %u files", cached, total, files)
        startTimer()
        notify()
        return nil
    }

    func pause() {
        userPaused = true
        PGAssetPreloadStop()
        notify()
    }

    /// Stops and forgets the request. Downloaded files stay until removed.
    func cancel() {
        wanted = false
        userPaused = false
        lastError = nil
        PGAssetPreloadStop()
        notify()
    }

    /// Deletes the whole asset cache (also the streamed startup set) on a
    /// background queue; thousands of files can take a few seconds.
    /// Returns a message when it cannot run now.
    func removeDownloads(completion: @escaping (String?) -> Void) {
        guard !running else { completion("Stop the download first."); return }
        guard !engineRunning else { completion("Restart the app to remove files; the game is using them."); return }
        guard !removing else { completion(nil); return }
        removing = true
        wanted = false
        userPaused = false
        lastError = nil
        notify()
        DispatchQueue.global(qos: .userInitiated).async {
            var freed: UInt64 = 0
            let removed = PGAssetCacheRemoveAll(&freed)
            DispatchQueue.main.async {
                self.removing = false
                if removed { self.cachedBytes = 0 }
                NSLog("[asset-preload] removed cache: %d, %llu bytes", removed ? 1 : 0, freed)
                self.refresh()
                completion(removed ? nil : "The files could not be removed.")
            }
        }
    }

    /// App launch and return to the foreground: continue an unfinished
    /// download unless the player paused it.
    func resumeIfNeeded() {
        guard !GameFolder.isChosen else { return }
        prepare()
        refresh { [weak self] in
            guard let self, !self.removing, PGAssetPreloadSupported(), self.wanted, !self.userPaused, !self.running,
                  self.cachedBytes < self.totalBytes else { return }
            if let message = self.start() { NSLog("[asset-preload] resume refused: %@", message) }
            else { NSLog("[asset-preload] resumed after relaunch or return") }
        }
    }

    private func startTimer() {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in self?.tick() }
    }

    private func tick() {
        let status = PGAssetPreloadGetStatus()
        let now = CACurrentMediaTime()
        samples.append((now, status.downloadedBytes))
        samples.removeAll { now - $0.time > 20 }
        if status.totalBytes > 0 { totalBytes = status.totalBytes; cachedBytes = status.cachedBytes }
        if status.running, availableBytes() < 300_000_000 {
            lastError = "Paused because this iPhone is almost out of storage."
            PGAssetPreloadStop()
        }
        if !status.running {
            running = false
            timer?.invalidate(); timer = nil
            switch status.error {
            case Int32(PGAssetPreloadErrorNetwork.rawValue):
                lastError = "Could not reach the game server. Check that Tailscale is connected, then resume."
            case Int32(PGAssetPreloadErrorStorage.rawValue):
                lastError = "Stopped because files could not be saved. Free up storage, then resume."
            default: break
            }
            NSLog("[asset-preload] stopped: %llu of %llu bytes on device, error %d", status.cachedBytes, status.totalBytes, status.error)
            endBackgroundTask()
            refresh()
        }
        notify()
    }

    @objc private func enteredBackground() {
        guard running, backgroundTask == .invalid else { return }
        // iOS allows a short time in the background; then the lanes stop after
        // their current 1 MB piece and continue when the app is opened again.
        backgroundTask = UIApplication.shared.beginBackgroundTask(withName: "Game file download") { [weak self] in
            PGAssetPreloadStop()
            self?.endBackgroundTask()
        }
    }
    @objc private func becameActive() {
        endBackgroundTask()
        resumeIfNeeded()
    }
    private func endBackgroundTask() {
        guard backgroundTask != .invalid else { return }
        UIApplication.shared.endBackgroundTask(backgroundTask)
        backgroundTask = .invalid
    }

    private func notify() { NotificationCenter.default.post(name: .assetPreloadChanged, object: self) }

    static func format(_ bytes: UInt64) -> String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        formatter.allowedUnits = bytes >= 1_000_000_000 ? [.useGB] : [.useMB]
        return formatter.string(fromByteCount: Int64(bytes))
    }
    static func formatDuration(_ seconds: Double) -> String {
        if seconds < 60 { return "under a minute left" }
        let formatter = DateComponentsFormatter()
        formatter.unitsStyle = .short
        formatter.allowedUnits = seconds >= 3600 ? [.hour, .minute] : [.minute]
        formatter.maximumUnitCount = 2
        return "about \(formatter.string(from: seconds) ?? "") left"
    }

    /// One-line summary for the launch screen; nil when there is nothing to say.
    var launchSummary: String? {
        let percent = Int((fraction * 100).rounded(.down))
        switch phase {
        case .downloading: return "Downloading game files: \(percent)% (\(Self.format(cachedBytes)) of \(Self.format(totalBytes)))"
        case .paused: return "Game file download paused at \(percent)%"
        case .complete: return wanted ? "All game files on device" : nil
        case .idle, .unavailable: return nil
        }
    }
}
