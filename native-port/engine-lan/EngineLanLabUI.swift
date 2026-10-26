import UIKit
import ZemaLanBackend

private var laboratoryProfile: EngineLanProfileFile?
@_cdecl("ZemaExperimentalCommit") func zemaExperimentalCommit() -> Int32 {
    guard let profile = laboratoryProfile else { return 0 }
    do { try profile.commit(); return 1 } catch { return 0 }
}

/// Included only in the separate experimental bundle. No automatic connection.
final class ZemaEngineLANUI {
    static let shared = ZemaEngineLANUI()
    private let session = EngineLanSession(backend: .native)
    var changed: (() -> Void)?
    var log: ((String) -> Void)?
    private var phoneHost: PhoneRelayServer?
    private var hostRunning = false
    private var hostUsed = false
    private var hostLAN: String?
    private var hostVPN: String?
    private var hostPlayers = 0
    private var oldIdleTimer: Bool?
    private var lifecycleObservers: [NSObjectProtocol] = []
    private var mode = EngineLanPreferences.selected()
    private var endpoint = EngineLanPreferences.load(mode: EngineLanPreferences.selected()).relay
    private var room = EngineLanPreferences.load(mode: EngineLanPreferences.selected()).room
    private var name = "Player"
    private weak var screen: UIAlertController?
    private weak var resumeAction: UIAlertAction?
    private var connecting = false
    private var restartWhenConnected = false
    private var lastMessage: String?
    private var admitted = false
    private var showingRunningPanel = false
    private weak var pendingController: UIViewController?
    private var pendingPlay: (() -> Void)?
    private(set) var selectedRole = "join"
    private var connectionAttempt: UInt64 = 0
    private var buildLabel: String { Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown" }
    private var connectionSummary: String {
        if hostUsed {
            let local = hostLAN.map { "LAN: ws://\($0):47540/engine-lan" } ?? "LAN: unavailable"
            let remote = hostVPN.map { "Remote: ws://\($0):47540/engine-lan" } ?? "Remote: not enabled for this lobby"
            return "Hosted on this iPhone · \(hostPlayers) connected\nRoom: \(room)\n\(local)\n\(remote)"
        }
        return EngineLanPreferences.summary(relay: endpoint, room: room)
    }
    var connectionDetail: String {
        hostUsed ? (hostRunning ? "Hosting · \((mode == .remote ? hostVPN : hostLAN) ?? "this iPhone") · Keep ZGTA V open" : "Hosting stopped · Start hosting again in Multiplayer") : (connecting ? "Connecting to \(room)…" : (mode.accepts(endpoint) ? "\(room) · \(mode.rawValue) · \(ready ? "Ready to play" : "Open Connection to connect")" : "Choose Join or create, or Find lobby."))
    }
    var launchDetail: String {
        if connecting { return selectedRole == "host" ? "Preparing your lobby…" : "Connecting to \(room)…" }
        if ready { return selectedRole == "host" ? "Lobby ready · Press Host multiplayer to enter the game. Keep ZGTA V open." : "\(room) · \(mode.rawValue) · Press Play multiplayer to enter the game." }
        if let lastMessage { return lastMessage }
        return "Choose a lobby above, then press the green button to play."
    }
    var connectionTitle: String { mode.rawValue }
    var ready: Bool { ZemaLanGameReady() == 1 }
    private init() {
        lifecycleObservers = [UIApplication.didEnterBackgroundNotification, UIApplication.willTerminateNotification].map { notification in
            NotificationCenter.default.addObserver(forName: notification, object: nil, queue: .main) { [weak self] _ in
                guard let self, self.phoneHost != nil else { return }
                self.stopHosting(message: "Hosting stopped because ZGTA V left the foreground. Return to Multiplayer and start hosting again; your character is saved.")
            }
        }
        session.status = { [weak self] message in
            DispatchQueue.main.async {
                guard let self else { return }
                self.connecting = false
                if ZemaLanTransportReady() == 1 { self.admitted = true }
                ZemaLanPrepared(ZemaLanTransportReady() == 1 && laboratoryProfile != nil ? 1 : 0)
                self.lastMessage = self.ready
                    ? (self.showingRunningPanel ? "Network connected. Reconnect restarts the GTA session in this lobby." : "Connected. Tap Play to start.")
                    : (self.mode == .remote ? message + "\n" + self.mode.instructions : message)
                self.screen?.message = (self.lastMessage ?? "") + "\n\n" + self.connectionSummary
                self.resumeAction?.isEnabled = !self.connecting && (true) && (!self.hostUsed || self.hostRunning)
                if self.restartWhenConnected && self.ready { self.restartWhenConnected = false; self.queueSessionRestart() }
                self.changed?()
                let owner = self.pendingController
                self.pendingController = nil
                let play = self.pendingPlay
                self.pendingPlay = nil
                let attempt = self.connectionAttempt
                if self.ready, let play {
                    DispatchQueue.main.asyncAfter(deadline: .now()+0.4) { [weak self] in
                        guard let self, self.connectionAttempt == attempt, self.ready, !self.connecting else { return }
                        play()
                    }
                } else if !self.ready, let owner {
                    // Success never opens a second confirmation. A failed running
                    // reconnect reports its reason; initial setup retains its form.
                    self.restartWhenConnected = false
                    let wasRunning = self.showingRunningPanel
                    let failure = self.lastMessage ?? message
                    DispatchQueue.main.asyncAfter(deadline: .now()+0.4) { [weak self, weak owner] in
                        guard let self, let owner, self.connectionAttempt == attempt, !self.ready, !self.connecting else { return }
                        if wasRunning {
                            guard owner.presentedViewController == nil else { return }
                            let alert = UIAlertController(title: "Multiplayer · \(self.mode.rawValue)", message: failure, preferredStyle: .alert)
                            alert.addAction(UIAlertAction(title: "OK", style: .default))
                            owner.present(alert, animated: true)
                        } else { self.present(from: owner, running: false) }
                    }
                }
            }
        }
    }
    private func prepareProfile(renameTo requestedName: String? = nil, createIfMissing: Bool = true) throws {
        if laboratoryProfile == nil {
            let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            let file = try EngineLanProfileFile(directory: EngineLanProfileFile.profileDirectory(inAppDocuments: documents))
            if try !file.load() {
                guard createIfMissing else { return }
                if ZemaProfileReady() != 1 {
                    let bytes = Array((requestedName ?? name).utf8)
                    let id = UInt32.random(in: 65536...UInt32(Int32.max))
                    guard bytes.withUnsafeBufferPointer({ ZemaProfileConfigure(id,$0.baseAddress,$0.count) }) == 1 else { throw EngineLanProfileFile.Failure.unavailable }
                }
                try file.commit()
            }
            laboratoryProfile = file
        }
        // Apply the explicit Join/Host name before first admission, preserving
        // numeric identity and every saved character/stat record. Reconnect uses
        // the admitted name and never a later text-field edit.
        if let requestedName, let profile = laboratoryProfile {
            try profile.rename(to: requestedName)
        }
        var bytes = [UInt8](repeating: 0, count: 17)
        let count = bytes.withUnsafeMutableBufferPointer { ZemaProfileName($0.baseAddress, $0.count) }
        guard count > 0 else { throw EngineLanProfileFile.Failure.unavailable }
        name = String(decoding: bytes.prefix(Int(count)), as: UTF8.self)
    }
    func reconnectSession(from controller: UIViewController) {
        guard ZemaLabEnabled() != 0, !connecting else { return }
        if ready { queueSessionRestart() }
        else { restartWhenConnected = true; connect(from: controller, running: true) }
    }
    private func queueSessionRestart() {
        guard PGRequestSessionRestart() else { log?("A GTA session restart is already pending."); return }
        lastMessage = "Rejoining your GTA session…"
        log?(lastMessage!)
        var polls = 0
        Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] timer in
            polls += 1
            let status = PGSessionRestartStatus()
            guard status < 0 || status == 4 || polls > 500 else { return }
            timer.invalidate()
            guard let self else { return }
            self.lastMessage = status == 4 ? "Returned to the GTA session." : "Session restart did not finish. Find New Session → Public Session remains available."
            self.log?(self.lastMessage!)
            self.screen?.message = self.lastMessage! + "\n\n" + self.connectionSummary
        }
    }
    private func connect(from controller: UIViewController, running: Bool) {
        connectionAttempt &+= 1
        pendingController = controller
        showingRunningPanel = running
        screen = nil
        resumeAction = nil
        connecting = true
        lastMessage = "Connecting to \(endpoint)… Please wait for the connection result."
        session.disconnect()
        session.connect(endpoint: endpoint, room: room, name: name)
        // Reconnect is an action, not another request to open connection details.
        // The globe button still presents that panel explicitly; only an actual
        // failed admission may present feedback from the status callback.
    }
    /// Selecting a mode has no side effects. Play may reuse a previously chosen lobby.
    /// First-time setup stays on Home, where the Join / Host / Find actions are visible.
    func playConfigured(from controller: UIViewController, play: @escaping () -> Void) -> Bool {
        if waitForConnection(play) { return true }
        if ready { play(); return true }
        guard !hostUsed || hostRunning, mode.accepts(endpoint), EngineLanPreferences.validRoom(room) else { return false }
        if URL(string: endpoint)?.host == "127.0.0.1", !hostRunning { return false }
        do { try prepareProfile() }
        catch {
            showError("The saved multiplayer profile could not be opened. Your character is preserved. Use Join a lobby to check the settings.", from: controller)
            return true
        }
        pendingPlay = play
        connect(from: controller, running: false)
        changed?()
        return true
    }

    /// Only an explicit Play tap during admission requests a deferred launch.
    func waitForConnection(_ play: @escaping () -> Void) -> Bool {
        guard connecting else { return false }
        pendingPlay = play
        return true
    }
    func leaveBeforeOfflineLaunch() {
        connectionAttempt &+= 1
        pendingController = nil
        pendingPlay = nil
        session.disconnect()
        connecting = false
        lastMessage = nil
        ZemaLanPrepared(0)
        if phoneHost != nil { stopHosting(message: "Hosting stopped before offline play.") }
    }
    /// Setup never receives a launch callback. Only the final green Play action can start the engine.
    func presentSetup(from controller: UIViewController, role: String, selected: @escaping () -> Void) {
        guard controller.presentedViewController == nil, !connecting else { return }
        pendingPlay = nil
        if role == "choose" {
            let menu = UIAlertController(title: "Join or create", message: "Set up a lobby first, then use the green button to enter the game.", preferredStyle: .alert)
            for (value, title) in [("join", "Join a friend"), ("host", "Create a lobby")] {
                menu.addAction(UIAlertAction(title: title, style: .default) { [weak self, weak controller] _ in
                    DispatchQueue.main.asyncAfter(deadline: .now()+0.3) { [weak self, weak controller] in
                        guard let self, let controller else { return }
                        self.presentSetup(from: controller, role: value, selected: selected)
                    }
                })
            }
            menu.addAction(UIAlertAction(title: "Cancel", style: .cancel))
            controller.present(menu, animated: true)
        } else if role == "browse" {
            guard !admitted, !hostUsed else {
                showError("Reopen ZGTA V before browsing another lobby. Your current lobby and saved character are preserved.", from: controller); return
            }
            selectedRole = role; selected(); changed?()
            presentBrowser(from: controller, selected: selected)
        } else {
            // An admitted host cannot become a guest without reopening the app.
            guard !hostUsed || role == "host" else {
                showError("Reopen ZGTA V before joining another lobby. Your hosted lobby and saved character are preserved.", from: controller); return
            }
            guard role != "host" || !admitted || hostUsed else {
                showError("Reopen ZGTA V before hosting another lobby. Your current lobby and saved character are preserved.", from: controller); return
            }
            selectedRole = role; selected(); changed?()
            presentChoices(from: controller, role: role, selected: selected)
        }
    }
    private func presentBrowser(from controller: UIViewController, selected: @escaping () -> Void) {
        guard !admitted, !hostUsed else { showError("Your game already has a lobby. Use Multiplayer to reconnect, or reopen ZGTA V to choose another host. Your character is preserved.", from: controller); return }
        LobbyBrowserPresenter.present(from: controller) { [weak self, weak controller] record in
            guard let self, let controller else { return }
            self.mode = record.connection; self.endpoint = record.relay; self.room = record.room
            EngineLanPreferences.save(mode: self.mode, relay: self.endpoint, room: self.room)
            selected()
            DispatchQueue.main.asyncAfter(deadline: .now()+0.3) { [weak self, weak controller] in
                guard let self, let controller else { return }; self.present(from: controller, running: false)
            }
        }
    }
    func presentChoices(from controller: UIViewController, role: String? = nil, selected: @escaping () -> Void) {
        guard controller.presentedViewController == nil, !connecting else { return }
        let menu = UIAlertController(title: "Multiplayer", message: "LAN uses your local network. Remote uses Tailscale to reach the host. Both use your saved multiplayer character.", preferredStyle: .alert)
        for choice in MultiplayerConnection.allCases {
            menu.addAction(UIAlertAction(title: choice.rawValue, style: .default) { [weak self, weak controller] _ in
                guard let self, let controller else { return }
                if choice != self.mode && (self.admitted || self.ready) {
                    self.showError("Close and reopen ZGTA V before switching between LAN and Remote. Your saved character is preserved.", from: controller)
                    return
                }
                self.mode = choice
                let saved = EngineLanPreferences.load(mode: choice)
                self.endpoint = saved.relay
                self.room = saved.room
                self.lastMessage = nil
                selected()
                DispatchQueue.main.asyncAfter(deadline: .now()+0.3) { [weak self, weak controller] in
                    guard let self, let controller else { return }
                    if role == "host" { self.presentHostSetup(from: controller) }
                    else if role == "join" { self.present(from: controller, running: false) }
                    else { self.presentRoleChoice(from: controller) }
                }
            })
        }
        menu.addAction(UIAlertAction(title: "Cancel", style: .cancel))
        controller.present(menu, animated: true)
    }
    func present(from controller: UIViewController, running: Bool) {
        guard controller.presentedViewController == nil, running || !connecting else { return }
        if hostUsed { presentHostStatus(from: controller, running: running); return }
        if !running {
            do { try prepareProfile(createIfMissing: false) }
            catch { showError("The saved multiplayer profile could not be opened. Existing data was preserved.", from: controller); return }
        }
        let alert = UIAlertController(title: "Multiplayer · \(mode.rawValue)",message: (lastMessage ?? (ready ? "Connected to the chosen relay." : mode.instructions)) + "\n\n" + connectionSummary + (running ? "" : "\nPaste an invite to fill its host, connection type and room. Your chosen name updates the saved multiplayer name; appearance and progress stay intact."),preferredStyle:.alert)
        screen = alert
        resumeAction = nil
        showingRunningPanel = running
        if running {
            alert.message = (ready ? "Reconnect restarts the GTA session directly in this lobby." : lastMessage ?? "Reconnect restores the host connection, then restarts your GTA session in the same lobby. Your saved character is preserved.") + "\n\n" + connectionSummary
            let reconnect = UIAlertAction(title: "Reconnect", style: .default) { [weak self,weak controller] _ in
                guard let self,let controller,!self.connecting else { return }
                self.reconnectSession(from:controller)
            }
            resumeAction = reconnect
            reconnect.isEnabled = !connecting
            alert.addAction(reconnect)
        } else {
            alert.addTextField { $0.text=self.endpoint;$0.placeholder=self.mode.endpointHint;$0.autocapitalizationType = .none;$0.autocorrectionType = .no }
            alert.addTextField { $0.text=self.room;$0.placeholder="Room";$0.autocapitalizationType = .allCharacters }
            alert.addTextField { $0.text=self.name;$0.placeholder="Name (1–16 English characters)";$0.autocorrectionType = .no }
            let connectAction = UIAlertAction(title:ready ? "Reconnect" : "Connect",style:.default) { [weak self,weak controller,weak alert] _ in
                guard let self,let alert,let controller,!self.connecting else { return }
                let values=alert.textFields?.map { $0.text ?? "" } ?? []
                guard values.count==3,let target=LobbyRecord.parse(values[0],room:values[1]),(self.mode.accepts(target.relay) || values[0].trimmingCharacters(in:.whitespacesAndNewlines).hasPrefix("zgtav:")),!values[2].trimmingCharacters(in:.whitespaces).isEmpty,values[2].utf8.count<=16,values[2].utf8.allSatisfy({ $0>=32 && $0<127 }) else {
                    self.showError("Enter a \(self.mode == .remote ? "Tailscale 100.x" : "local Wi-Fi") relay address, a room of 1–64 bytes without control characters, and a name of 1–16 English characters.",from:controller);return
                }
                let chosenEndpoint = target.relay
                if self.admitted && (chosenEndpoint != self.endpoint || target.room != self.room) {
                    self.showError("Reopen ZGTA V before changing the host or room. Your saved character stays intact.",from:controller);return
                }
                self.mode=target.connection;self.endpoint=chosenEndpoint;self.room=target.room
                do { try self.prepareProfile(renameTo: values[2]) }
                catch let error as EngineLanProfileFile.Failure {
                    self.showError(error.message + " Existing data was preserved.",from:controller);return
                } catch {
                    self.showError("The multiplayer profile could not be prepared. Existing data was preserved.",from:controller);return
                }
                EngineLanPreferences.save(mode: self.mode, relay: self.endpoint, room: self.room)
                LobbyHistory.remember(target)
                self.connect(from:controller,running:false); self.changed?()
            }
            connectAction.isEnabled = !connecting
            resumeAction = connectAction
            alert.addAction(connectAction)
        }
        alert.addAction(UIAlertAction(title:"Close",style:.cancel))
        controller.present(alert,animated:true)
    }
    private func presentRoleChoice(from controller: UIViewController) {
        guard controller.presentedViewController == nil else { return }
        if hostUsed { presentHostStatus(from: controller, running: false); return }
        let menu = UIAlertController(title: "Multiplayer · \(mode.rawValue)", message: mode == .lan ? "Join an existing lobby, or host one on this iPhone. No Mac is needed for iPhone hosting." : "Connect Tailscale first. Join a host, or host on this iPhone and share its Tailscale IPv4.", preferredStyle: .alert)
        menu.addAction(UIAlertAction(title: "Join a game", style: .default) { [weak self, weak controller] _ in
            DispatchQueue.main.asyncAfter(deadline: .now()+0.3) { [weak self, weak controller] in
                guard let self, let controller else { return }; self.selectedRole = "join"; self.changed?(); self.present(from: controller, running: false)
            }
        })
        menu.addAction(UIAlertAction(title: "Create lobby", style: .default) { [weak self, weak controller] _ in
            DispatchQueue.main.asyncAfter(deadline: .now()+0.3) { [weak self, weak controller] in
                guard let self, let controller else { return }; self.selectedRole = "host"; self.changed?(); self.presentHostSetup(from: controller)
            }
        })
        menu.addAction(UIAlertAction(title: "Cancel", style: .cancel))
        controller.present(menu, animated: true)
    }
    private func presentHostSetup(from controller: UIViewController, running: Bool = false) {
        guard controller.presentedViewController == nil, !connecting else { return }
        guard (!admitted || hostUsed) && !hostRunning else {
            showError("Leave the current lobby before starting a hosted lobby. Your saved character is preserved.", from: controller); return
        }
        do { try prepareProfile(createIfMissing: false) }
        catch { showError("The saved multiplayer profile could not be opened. Existing data was preserved.", from: controller); return }
        let addresses = PhoneRelayAddresses.current()
        if mode == .lan && addresses.lan == nil {
            showError("Connect this iPhone to Wi-Fi before hosting LAN. You can use Remote with Tailscale instead.", from: controller); return
        }
        let local = mode == .lan ? (addresses.lan.map { "Other players join LAN at \($0)." } ?? "Wi-Fi is unavailable.") : "Remote hosting uses Tailscale over Wi-Fi or cellular. Share this iPhone’s Tailscale address."
        let alert = UIAlertController(title: "Create lobby · \(mode.rawValue)", message: local + "\nKeep ZGTA V open and the host phone awake. Leaving the app stops this lobby. No Mac is needed.", preferredStyle: .alert)
        if mode == .remote {
            alert.addTextField { field in
                field.text = addresses.vpn ?? UserDefaults.standard.string(forKey: "zgta.phone-host.vpn.v1") ?? ""
                field.placeholder = "This iPhone’s Tailscale IPv4 (100.x)"; field.autocorrectionType = .no; field.autocapitalizationType = .none
            }
        }
        alert.addTextField { $0.text = UserDefaults.standard.string(forKey: "zgta.phone-host.room.v1") ?? self.room; $0.placeholder = "Room"; $0.autocapitalizationType = .allCharacters }
        alert.addTextField { $0.text = self.name; $0.placeholder = "Name (progress is preserved)"; $0.autocorrectionType = .no }
        alert.addAction(UIAlertAction(title: "Create lobby", style: .default) { [weak self, weak controller, weak alert] _ in
            guard let self, let controller, let alert, !self.connecting else { return }
            let values = alert.textFields?.map { $0.text ?? "" } ?? []
            let offset = self.mode == .remote ? 1 : 0
            guard values.count == offset+2, EngineLanPreferences.validRoom(values[offset]),
                  !values[offset+1].trimmingCharacters(in: .whitespaces).isEmpty, values[offset+1].utf8.count <= 16,
                  values[offset+1].utf8.allSatisfy({ $0 >= 32 && $0 < 127 }) else {
                self.showError("Enter a room of 1–64 bytes and a name of 1–16 English characters.", from: controller); return
            }
            var remote: String? = addresses.vpn
            if self.mode == .remote {
                guard let url = MultiplayerConnection.remote.endpoint(from: values[0]), let host = URL(string: url)?.host else {
                    self.showError("Enter this iPhone’s Tailscale 100.x address from the Tailscale app.", from: controller); return
                }
                remote = host
            }
            if self.hostUsed && values[offset] != self.room {
                self.showError("Keep the same room when restarting this game’s hosted lobby. Reopen ZGTA V to choose another room; your character is preserved.", from: controller); return
            }
            self.room = values[offset]
            do { try self.prepareProfile(renameTo: values[offset+1]) } catch {
                self.showError("Your saved character could not be opened. Existing data was preserved.", from: controller); return
            }
            self.connectionAttempt &+= 1; let attempt = self.connectionAttempt
            self.connecting = true; self.pendingController = controller
            let server = PhoneRelayServer(); self.phoneHost = server
            self.hostLAN = self.mode == .lan ? addresses.lan : nil; self.hostVPN = self.mode == .remote ? remote : nil
            server.diagnostic = { [weak self] line in self?.log?(line) }
            self.lastMessage = "Starting hosting on this iPhone…"
            self.changed?()
            server.changed = { [weak self, weak server] snapshot in
                guard let self, let server, self.phoneHost === server else { return }
                self.hostRunning = snapshot.running; self.hostPlayers = snapshot.online
                if self.hostUsed && !snapshot.running { self.stopHosting(message: snapshot.message) }
                self.screen?.message = (self.lastMessage ?? snapshot.message) + "\n\n" + self.connectionSummary
                self.changed?()
            }
            // Keep the host's local game and its guest-facing private listener.
            // A loopback-only listener was locally ready but unreachable through
            // this phone's VPN path. The server enables private port reuse.
            var binds = ["127.0.0.1"]
            if self.mode == .lan, let ip = addresses.lan { binds.append(ip) }
            if self.mode == .remote, let ip = remote { binds.append(ip) }
            self.log?("Phone host interfaces: LAN=\(addresses.lan ?? "none"), VPN=\(addresses.vpn ?? "none"); selected=\(binds.joined(separator: ", "))")
            server.start(addresses: binds, room: self.room) { [weak self, weak controller, weak server] result in
                guard let self, let controller, let server, self.phoneHost === server, self.connectionAttempt == attempt else { return }
                switch result {
                case .failure(let error):
                    self.phoneHost = nil; self.connecting = false; self.pendingController = nil; self.pendingPlay = nil
                    let help = self.mode == .remote
                        ? "Remote hosting over 5G does not require Wi-Fi. Keep Tailscale connected on both devices."
                        : "Allow Local Network access in iOS Settings and connect to the same Wi-Fi as the other player."
                    self.lastMessage = "Hosting could not start. " + error.localizedDescription
                    self.changed?()
                    self.showError((self.lastMessage ?? "Hosting could not start.") + "\n\n" + help + " Your character and join settings are preserved.", from: controller)
                case .success:
                    self.hostUsed = true; self.hostRunning = true
                    self.oldIdleTimer = UIApplication.shared.isIdleTimerDisabled; UIApplication.shared.isIdleTimerDisabled = true
                    self.endpoint = "ws://127.0.0.1:47540/engine-lan"
                    UserDefaults.standard.set(self.room, forKey: "zgta.phone-host.room.v1")
                    if let remote { UserDefaults.standard.set(remote, forKey: "zgta.phone-host.vpn.v1") }
                    self.connect(from: controller, running: running); self.changed?()
                }
            }
        })
        alert.addAction(UIAlertAction(title: "Cancel", style: .cancel))
        controller.present(alert, animated: true)
    }
    private func stopHosting(message: String) {
        connectionAttempt &+= 1; pendingController = nil; pendingPlay = nil
        let server = phoneHost; phoneHost = nil; server?.stop()
        session.disconnect(); connecting = false; hostRunning = false; hostPlayers = 0
        if let oldIdleTimer { UIApplication.shared.isIdleTimerDisabled = oldIdleTimer }; oldIdleTimer = nil
        ZemaLanPrepared(0); lastMessage = message
        screen?.message = message + "\n\n" + connectionSummary; resumeAction?.isEnabled = false
        changed?()
    }
    private func presentHostStatus(from controller: UIViewController, running: Bool) {
        let alert = UIAlertController(title: hostRunning ? "Hosting on this iPhone" : "Hosting stopped", message: (lastMessage ?? "Keep ZGTA V open. Share this address and room with the other player.") + "\n\n" + connectionSummary, preferredStyle: .alert)
        screen = alert; resumeAction = nil; showingRunningPanel = running
        if hostRunning {
            alert.addAction(UIAlertAction(title: "Copy invite", style: .default) { [weak self] _ in
                guard let self, let address = self.mode == .remote ? self.hostVPN : self.hostLAN else { return }
                let record = LobbyRecord(relay: "ws://\(address):47540/engine-lan", room: self.room)
                LobbyHistory.remember(record); UIPasteboard.general.string = record.invite
            })
            alert.addAction(UIAlertAction(title: "Copy join address", style: .default) { [weak self] _ in
                guard let self, let address = self.mode == .remote ? self.hostVPN : self.hostLAN else { return }
                UIPasteboard.general.string = "ws://\(address):47540/engine-lan"
            })
            let reconnect = UIAlertAction(title: "Reconnect", style: .default) { [weak self, weak controller] _ in
                guard let self, let controller, self.hostRunning, !self.connecting else { return }; self.reconnectSession(from: controller)
            }
            reconnect.isEnabled = !connecting; resumeAction = reconnect; alert.addAction(reconnect)
            alert.addAction(UIAlertAction(title: "Stop hosting", style: .destructive) { [weak self] _ in
                self?.stopHosting(message: "Hosting stopped. Other players were disconnected. Start hosting again here, then let players reconnect.")
            })
        } else {
            alert.addAction(UIAlertAction(title: "Start hosting again", style: .default) { [weak self, weak controller] _ in
                DispatchQueue.main.asyncAfter(deadline: .now()+0.3) { [weak self, weak controller] in
                    guard let self, let controller else { return }; self.presentHostSetup(from: controller, running: running)
                }
            })
        }
        alert.addAction(UIAlertAction(title: "Close", style: .cancel))
        controller.present(alert, animated: true)
    }
    private func showError(_ text:String,from controller:UIViewController) {
        let alert=UIAlertController(title:"Multiplayer · \(mode.rawValue)",message:text,preferredStyle:.alert);alert.addAction(UIAlertAction(title:"OK",style:.default))
        DispatchQueue.main.asyncAfter(deadline:.now()+0.3) { controller.present(alert,animated:true) }
    }
}
