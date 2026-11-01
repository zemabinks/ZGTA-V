import Foundation
import CoreFoundation

/// Explicit LAN or private Tailscale transport for the native engine backend. Networking starts
/// only on connect(), after a user chooses this experimental mode and endpoint.
/// Does not install an app, patch an engine, alter saves or select Mugoat mode.
final class EngineLanSession: NSObject, @unchecked Sendable {
    struct Backend: @unchecked Sendable {
        let configure: (UInt32, UInt64) -> Bool
        let connected: (Bool) -> Void
        let deliver: (Data) -> Void
        let outgoing: () -> Data?
        var voiceOutgoing: (() -> Data?)? = nil
    }
    private let backend: Backend
    private let queue = DispatchQueue(label: "zema.engine-lan.transport")
    private var task: URLSessionWebSocketTask?
    private var session: URLSession?
    private var pump: DispatchSourceTimer?
    private var resume: String?
    private var address: UInt32?
    private var sessionEpoch: UInt64?
    private var recoveryEpoch: UInt64?
    private var generation: UInt64 = 0
    private var admitted = false
    private var pending: [UInt64: TimeInterval] = [:]
    private var nextSend: UInt64 = 0
    private var lastPing: TimeInterval = 0
    private var lastInbound: TimeInterval = 0
    private let uptime: @Sendable () -> TimeInterval
    var status: (@Sendable (String) -> Void)?
    init(backend: Backend, uptime: @escaping @Sendable () -> TimeInterval = { ProcessInfo.processInfo.systemUptime }) {
        self.backend = backend; self.uptime = uptime
    }

    private func connectionFailure(_ cause: String) {
        let message: String
        if admitted {
            message = "Engine-LAN disconnected: \(cause). Check the host relay and reconnect promptly to the same session."
        } else if resume != nil {
            message = "Could not resume this LAN session: \(cause). Check the same host relay and room; if the relay restarted or the reservation expired, fully close and reopen ZGTA V. Saved characters are preserved."
        } else {
            message = "Could not connect to the host relay: \(cause). Check that the relay is running and that both devices use the same Wi-Fi or private VPN address. Your settings are kept."
        }
        stop(); status?(message)
    }

    static func validEndpoint(_ text: String) -> URL? {
        guard let parts = URLComponents(string: text), parts.scheme == "ws", parts.user == nil,
              parts.password == nil, parts.query == nil, parts.fragment == nil,
              parts.path == "/engine-lan", let host = parts.host,
              let url = parts.url, parts.port.map({ (1...65535).contains($0) }) ?? true else { return nil }
        let raw = host.split(separator: ".", omittingEmptySubsequences: false)
        guard raw.count == 4, raw.allSatisfy({ !$0.isEmpty && $0.count <= 3 && $0.allSatisfy({ $0 >= "0" && $0 <= "9" }) }),
              raw.allSatisfy({ Int($0).map({ (0...255).contains($0) }) ?? false }) else { return nil }
        let numbers = raw.map { Int($0)! }
        // Require the literal dotted-decimal endpoint the user entered; do not
        // accept ambiguous numeric aliases, escaped hosts or URL normalization.
        guard zip(raw, numbers).allSatisfy({ String($0.1) == $0.0 }),
              text == "ws://" + host + (parts.port.map { ":\($0)" } ?? "") + "/engine-lan" else { return nil }
        guard numbers[0] == 127 || numbers[0] == 10 || (numbers[0] == 192 && numbers[1] == 168) ||
              (numbers[0] == 172 && (16...31).contains(numbers[1])) || (numbers[0] == 169 && numbers[1] == 254) ||
              (numbers[0] == 100 && (64...127).contains(numbers[1])) else { return nil }
        return url
    }
    func connect(endpoint: String, room: String, name: String) {
        self.queue.async { [self] in
            guard self.task == nil, let url = Self.validEndpoint(endpoint),
                  !room.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, room.utf8.count <= 64,
                  !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, name.utf8.count <= 48,
                  !room.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }),
                  !name.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }) else {
                self.status?("Choose a LAN or Tailscale IPv4 relay endpoint, name and room."); return
            }
            self.generation &+= 1; let token = self.generation
            let configuration = URLSessionConfiguration.ephemeral
            configuration.timeoutIntervalForRequest = 15
            let transport = URLSession(configuration: configuration)
            self.session = transport
            let socket = transport.webSocketTask(with: url); self.task = socket; socket.resume()
            self.recoveryAttempted = false
            self.recoveryEpoch = nil
            self.joinRoom = room; self.joinName = name
            var join: [String: Any] = ["type": "join", "protocol": "zema-engine-lan/1", "build": "8b0b5899ed", "room": room, "name": name]
            if let savedResume = self.resume { join["resume"] = savedResume }
            guard let data = try? JSONSerialization.data(withJSONObject: join), let text = String(data: data, encoding: .utf8) else { self.stop(); self.status?("Local engine-LAN message was invalid; reconnect the same session."); return }
            socket.send(.string(text)) { [weak self, weak socket] error in
                guard let self else { return }
                self.queue.async { [self] in
                    guard self.task === socket, self.generation == token else { return }
                    if error != nil { self.connectionFailure("join send failed") }
                }
            }
            self.receive(socket, token)
            self.queue.asyncAfter(deadline: .now() + 15) { [weak self, weak socket] in
                guard let self, self.task === socket, self.generation == token, !self.admitted else { return }
                self.connectionFailure("admission timed out")
            }
        }
    }
    private var recoveryAttempted = false
    private var joinRoom = ""
    private var joinName = ""
    private func receive(_ socket: URLSessionWebSocketTask, _ token: UInt64) {
        socket.receive { [weak self, weak socket] result in
            guard let self, let socket else { return }
            self.queue.async { [self] in
                guard self.task === socket, self.generation == token else { return }
                switch result {
                case .failure:
                    self.connectionFailure("connection interrupted")
                case .success(let message):
                    switch message {
                    case .data(let data):
                        guard self.admitted, (16...2048).contains(data.count) else { self.stop(); self.status?("Local engine-LAN message was invalid; reconnect the same session."); return }
                        self.backend.deliver(data)
                        self.lastInbound = self.uptime()
                    case .string(let text):
                        guard let data = text.data(using: .utf8), data.count <= 2048,
                              let object = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { self.stop(); self.status?("Local engine-LAN message was invalid; reconnect the same session."); return }
                        if object["type"] as? String == "pong" {
                            if self.admitted { self.lastInbound = self.uptime() }
                            break
                        }
                        if !self.admitted, object["protocol"] as? String == "zema-engine-lan/1", object["build"] as? String == "8b0b5899ed" {
                            if object["type"] as? String == "rejoin-unavailable", self.recoveryAttempted {
                                self.stop(); self.status?("Reconnect could not keep your game address because another player is using it. Retry when that slot is free, or reopen ZGTA V to join a new session. Your saved character is preserved."); return
                            }
                            if object["type"] as? String == "resume-unavailable", self.resume != nil, let address = self.address,
                               !self.recoveryAttempted, object["recovery"] as? String == "same-address-v1",
                               let epoch = object["epoch"] as? String, epoch.count == 16,
                               UInt64(epoch, radix: 16).map({ $0 != 0 }) == true {
                                self.recoveryAttempted = true
                                self.recoveryEpoch = UInt64(epoch, radix: 16)
                                let join: [String: Any] = ["type":"join", "protocol":"zema-engine-lan/1", "build":"8b0b5899ed", "room":self.joinRoom, "name":self.joinName, "rejoin":["vip":address, "epoch":epoch]]
                                guard let data = try? JSONSerialization.data(withJSONObject: join), let text = String(data:data,encoding:.utf8) else { self.connectionFailure("invalid recovery request");return }
                                socket.send(.string(text)) { [weak self, weak socket] error in
                                    guard let self else { return }
                                    self.queue.async { [self] in
                                        guard self.task === socket, self.generation == token else { return }
                                        if error != nil { self.connectionFailure("recovery send failed") }
                                    }
                                }
                                self.receive(socket, token); return
                            }
                        }
                        guard !self.admitted, object["type"] as? String == "joined",
                              object["protocol"] as? String == "zema-engine-lan/1", object["build"] as? String == "8b0b5899ed",
                              let address = object["vip"] as? NSNumber, CFGetTypeID(address) != CFBooleanGetTypeID(),
                              address.doubleValue == Double(address.uint32Value),
                              (self.address == nil || self.address == address.uint32Value),
                              let epoch = object["epoch"] as? String, epoch.count == 16,
                              let number = UInt64(epoch, radix: 16), number != 0,
                              (self.sessionEpoch == nil || (self.recoveryAttempted ? self.recoveryEpoch == number : self.sessionEpoch == number)),
                              let secret = object["resume"] as? String, secret.utf8.count == 32,
                              secret.allSatisfy({ $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "-" || $0 == "_") }),
                              self.backend.configure(address.uint32Value, number) else {
                            self.stop(); self.status?("The lobby changed. Reopen ZGTA V to join again; your saved character is preserved."); return
                        }
                        self.resume = secret; self.address = address.uint32Value; self.sessionEpoch = number; self.admitted = true; self.backend.connected(true)
                        self.lastInbound = self.uptime()
                        self.status?("Engine-LAN transport connected; game startup verification remains separate.")
                        self.startPump(socket, token)
                    @unknown default: self.stop(); self.status?("Local engine-LAN transport was interrupted."); return
                    }
                    if self.task === socket { self.receive(socket, token) }
                }
            }
        }
    }
    private func startPump(_ socket: URLSessionWebSocketTask, _ token: UInt64) {
        let timer = DispatchSource.makeTimerSource(queue: self.queue); self.pump = timer
        timer.schedule(deadline: .now(), repeating: .milliseconds(10)); self.lastPing = self.uptime()
        timer.setEventHandler { [weak self, weak socket] in
            guard let self, let socket, self.task === socket, self.generation == token else { return }
            let now = self.uptime()
            if now - self.lastInbound >= 30 {
                self.stop(); self.status?("Engine-LAN relay stopped responding. Reconnect to the same session."); return
            }
            // A newer completion must not hide an older stalled send.
            if self.pending.values.contains(where: { now - $0 > 5 }) {
                self.stop(); self.status?("Local engine-LAN send timed out."); return
            }
            // At most 16 in-flight frames, each <=2048 bytes. No unbounded self.send backlog.
            let engineLimit = self.backend.voiceOutgoing == nil ? 16 : 14
            while self.pending.count < engineLimit, let frame = self.backend.outgoing() {
                guard (16...2048).contains(frame.count) else { self.stop(); self.status?("Local engine-LAN message was invalid; reconnect the same session."); return }
                self.send(.data(frame), socket, token)
            }
            // Voice has a separate 100 ms queue and at most two send slots;
            // stale speech cannot build up behind engine traffic.
            var voiceFrames = 0
            while self.pending.count < 16, voiceFrames < 2, let frame = self.backend.voiceOutgoing?() {
                guard frame.count == 356 else { break }
                self.send(.data(frame), socket, token); voiceFrames += 1
            }
            if now - self.lastPing > 10, self.pending.count < 16 {
                self.lastPing = now; self.send(.string("{\"type\":\"ping\"}"), socket, token)
            }
        }
        timer.resume()
    }
    private func send(_ message: URLSessionWebSocketTask.Message, _ socket: URLSessionWebSocketTask, _ token: UInt64) {
        self.nextSend &+= 1
        let sendID = self.nextSend
        self.pending[sendID] = self.uptime()
        socket.send(message) { [weak self, weak socket] error in
            guard let self else { return }
            self.queue.async { [self] in
                guard self.task === socket, self.generation == token else { return }
                guard self.pending.removeValue(forKey: sendID) != nil else { return }
                if error != nil { self.connectionFailure("send failed") }
            }
        }
    }
    func disconnect() { self.queue.async { [self] in self.stop() } }
    private func stop() {
        self.generation &+= 1; self.pump?.cancel(); self.pump = nil
        let old = self.task; self.task = nil; self.admitted = false; self.pending.removeAll(keepingCapacity: true)
        self.backend.connected(false); old?.cancel(with: .goingAway, reason: nil)
        self.session?.invalidateAndCancel(); self.session = nil
    }
    deinit { self.pump?.cancel(); self.task?.cancel(with: .goingAway, reason: nil); self.session?.invalidateAndCancel() }
}
