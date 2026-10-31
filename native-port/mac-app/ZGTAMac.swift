import AppKit
import Foundation

let resources = Bundle.main.resourceURL!
#if arch(arm64)
let pythonArchitecture = "aarch64"
#else
let pythonArchitecture = "x86_64"
#endif
let python = resources.appendingPathComponent("Python/\(pythonArchitecture)/bin/python3")
let hostScript = resources.appendingPathComponent("mac_host.py")
let dataFolder = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".local/share/ZGTA-V")
let homeURL = URL(string: "http://127.0.0.1:18887/")!

func hostProcess(_ extra: [String]) -> Process {
    let process = Process()
    process.executableURL = python
    process.arguments = ["-I", "-B", hostScript.path, "--data", dataFolder.path] + extra
    process.currentDirectoryURL = resources
    process.standardInput = FileHandle.nullDevice
    return process
}

if CommandLine.arguments.contains("--verify-payload") {
    let check = hostProcess(["--verify"])
    do { try check.run(); check.waitUntilExit(); exit(check.terminationStatus) }
    catch { fputs("Bundled runtime could not start.\n", stderr); exit(1) }
}

final class LauncherView: NSView {
    let status = NSTextField(wrappingLabelWithString: "Opening your game launcher…")
    let openButton = NSButton(title: "Open ZGTA V", target: nil, action: nil)
    let folderButton = NSButton(title: "Choose game folder…", target: nil, action: nil)
    override init(frame: NSRect) {
        super.init(frame: frame)
        wantsLayer = true
        layer?.backgroundColor = NSColor(calibratedRed: 0.045, green: 0.065, blue: 0.06, alpha: 1).cgColor
        let icon = NSImageView()
        icon.image = NSImage(contentsOf: resources.appendingPathComponent("ZGTA-V.icns"))
        icon.imageScaling = .scaleProportionallyUpOrDown
        icon.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([icon.widthAnchor.constraint(equalToConstant: 66), icon.heightAnchor.constraint(equalToConstant: 66)])
        let title = NSTextField(labelWithString: "ZGTA V")
        title.font = .systemFont(ofSize: 32, weight: .bold)
        title.textColor = .white
        let subtitle = NSTextField(labelWithString: "Play your way · by zema")
        subtitle.textColor = .secondaryLabelColor
        let titles = NSStackView(views: [title, subtitle]); titles.orientation = .vertical; titles.alignment = .leading
        let header = NSStackView(views: [icon, titles]); header.spacing = 18
        status.textColor = .white; status.font = .systemFont(ofSize: 15)
        let hint = NSTextField(wrappingLabelWithString: "Keep ZGTA V open while playing or hosting. Your game files, mods and saves stay in their existing locations.")
        hint.textColor = .secondaryLabelColor
        openButton.bezelStyle = .rounded; openButton.keyEquivalent = "\r"; openButton.isEnabled = false
        openButton.contentTintColor = NSColor(calibratedRed: 0.49, green: 0.72, blue: 0.23, alpha: 1)
        folderButton.bezelStyle = .rounded; folderButton.isEnabled = false
        let buttons = NSStackView(views: [openButton, folderButton]); buttons.spacing = 12
        let stack = NSStackView(views: [header, status, hint, buttons]); stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 22
        stack.translatesAutoresizingMaskIntoConstraints = false; addSubview(stack)
        NSLayoutConstraint.activate([stack.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 34), stack.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -34), stack.topAnchor.constraint(equalTo: topAnchor, constant: 34), hint.widthAnchor.constraint(equalTo: stack.widthAnchor), status.widthAnchor.constraint(equalTo: stack.widthAnchor)])
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
}

final class Launcher: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    var view: LauncherView!
    var ownedHost: Process?
    var timer: Timer?
    var attempts = 0
    var expected: [String: Any] = [:]
    var verifying = false
    var didOpen = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = NSMenu(); let item = NSMenuItem(); menu.addItem(item)
        let appMenu = NSMenu(); appMenu.addItem(withTitle: "Quit ZGTA V", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"); item.submenu = appMenu; NSApp.mainMenu = menu
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 590, height: 320), styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        window.title = "ZGTA V"; window.appearance = NSAppearance(named: .darkAqua)
        view = LauncherView(frame: NSRect(x: 0, y: 0, width: 590, height: 320)); window.contentView = view
        view.openButton.target = self; view.openButton.action = #selector(openGame)
        view.folderButton.target = self; view.folderButton.action = #selector(chooseFolder)
        window.center()
        if let i = CommandLine.arguments.firstIndex(of: "--render-preview"), CommandLine.arguments.count > i + 1 {
            view.status.stringValue = "Ready to play. Open ZGTA V in your browser."
            view.openButton.isEnabled = true
            view.layoutSubtreeIfNeeded()
            let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds)!
            view.cacheDisplay(in: view.bounds, to: rep)
            try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[i+1]))
            NSApp.terminate(nil); return
        }
        window.makeKeyAndOrderFront(nil)
        verifyAndStart()
    }
    func fail(_ message: String) { timer?.invalidate(); view.status.stringValue = message; window.makeKeyAndOrderFront(nil) }
    func verifyAndStart() {
        guard !verifying else { return }; verifying = true
        DispatchQueue.global().async {
            let check = hostProcess(["--verify"]); let pipe = Pipe(); check.standardOutput = pipe; check.standardError = FileHandle.nullDevice
            do {
                try check.run(); let output = pipe.fileHandleForReading.readDataToEndOfFile(); check.waitUntilExit()
                guard check.terminationStatus == 0, let result = try JSONSerialization.jsonObject(with: output) as? [String: Any], let identity = result["identity"] as? [String: Any] else { throw CocoaError(.fileReadCorruptFile) }
                DispatchQueue.main.async { self.verifying = false; self.expected = identity; self.view.folderButton.isEnabled = true; self.inspectExisting() }
            } catch { DispatchQueue.main.async { self.verifying = false; self.fail("This app copy could not be verified. Copy ZGTA V from the disk image again.") } }
        }
    }
    func requestStatus(_ reply: @escaping ([String: Any]?) -> Void) {
        var request = URLRequest(url: homeURL.appendingPathComponent("zema-lab/launcher/status")); request.httpMethod = "POST"; request.httpBody = Data("{}".utf8); request.timeoutInterval = 1
        request.setValue("application/json", forHTTPHeaderField: "Content-Type"); request.setValue("1", forHTTPHeaderField: "X-Zema-Lab")
        URLSession.shared.dataTask(with: request) { data, _, _ in
            let value = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            DispatchQueue.main.async { reply(value) }
        }.resume()
    }
    func inspectExisting() {
        requestStatus { value in
            if let value = value {
                guard value["service"] as? String == "zgta-browser-launcher", let identity = value["identity"] as? [String: Any], NSDictionary(dictionary: identity).isEqual(to: self.expected) else {
                    self.fail("A different launcher version is still running. Quit that launcher, then reopen this app to finish updating."); return
                }
                self.ready(); return
            }
            if let raw = try? Data(contentsOf: dataFolder.appendingPathComponent("launcher.json")), let config = try? JSONSerialization.jsonObject(with: raw) as? [String: Any], let path = config["mirror"] as? String, FileManager.default.fileExists(atPath: path + "/data/manifest.json") {
                self.startHost(nil)
            } else { self.view.status.stringValue = "Choose your existing GTA V game folder to get started."; self.chooseFolder() }
        }
    }
    @objc func chooseFolder() {
        guard ownedHost == nil else { fail("Quit ZGTA V before choosing a different game folder."); return }
        let panel = NSOpenPanel(); panel.canChooseDirectories = true; panel.canChooseFiles = false; panel.allowsMultipleSelection = false
        panel.message = "Choose the prepared game folder containing index.html, data and b. Your files stay where they are."
        guard panel.runModal() == .OK, let folder = panel.url else { return }
        startHost(folder)
    }
    func startHost(_ mirror: URL?) {
        do {
            let fm = FileManager.default
            if !fm.fileExists(atPath: dataFolder.path) { try fm.createDirectory(at: dataFolder, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700]) }
            let attrs = try fm.attributesOfItem(atPath: dataFolder.path)
            guard attrs[.type] as? FileAttributeType == .typeDirectory, (attrs[.ownerAccountID] as? NSNumber)?.uint32Value == getuid(), ((attrs[.posixPermissions] as? NSNumber)?.intValue ?? 0o777) & 0o077 == 0 else { throw CocoaError(.fileWriteNoPermission) }
            let logs = dataFolder.appendingPathComponent("mac-app-logs", isDirectory: true)
            try fm.createDirectory(at: logs, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            let log = logs.appendingPathComponent("launch-\(UUID().uuidString).log")
            fm.createFile(atPath: log.path, contents: nil, attributes: [.posixPermissions: 0o600])
            let handle = try FileHandle(forWritingTo: log)
            let process = hostProcess(mirror.map { ["--mirror", $0.path] } ?? [])
            process.standardOutput = handle; process.standardError = handle
            try process.run(); ownedHost = process; attempts = 0
            view.status.stringValue = "Starting your game launcher…"
            timer = Timer.scheduledTimer(withTimeInterval: 0.4, repeats: true) { _ in
                self.attempts += 1
                if !process.isRunning { self.ownedHost = nil; self.fail("The launcher could not start. Check your game folder, then try again."); return }
                self.requestStatus { value in
                    if let identity = value?["identity"] as? [String: Any], NSDictionary(dictionary: identity).isEqual(to: self.expected) { self.ready() }
                    else if self.attempts > 60 { self.fail("The launcher is taking longer than expected. Quit ZGTA V and try again.") }
                }
            }
        } catch { fail("ZGTA V could not open its private data folder. Your game files have been preserved.") }
    }
    func ready() { guard !didOpen else { return }; didOpen = true; timer?.invalidate(); view.status.stringValue = "Ready to play. Open ZGTA V in your browser."; view.openButton.isEnabled = true; view.folderButton.isEnabled = false; openGame() }
    @objc func openGame() {
        if let chrome = NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.google.Chrome") { NSWorkspace.shared.open([homeURL], withApplicationAt: chrome, configuration: NSWorkspace.OpenConfiguration()) }
        else { NSWorkspace.shared.open(homeURL) }
    }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool { window.makeKeyAndOrderFront(nil); return true }
    func applicationWillTerminate(_ notification: Notification) { timer?.invalidate(); if let process = ownedHost, process.isRunning { process.interrupt() } }
}
let app = NSApplication.shared
let delegate = Launcher()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
