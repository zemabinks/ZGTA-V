import Foundation
import Network
import Darwin

struct PhoneRelayAddresses {
    var lan: String?
    var vpn: String?
    static func current() -> PhoneRelayAddresses {
        var result = PhoneRelayAddresses(), first: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&first) == 0 else { return result }
        defer { freeifaddrs(first) }
        var cursor = first
        while let row = cursor {
            defer { cursor = row.pointee.ifa_next }
            guard let address = row.pointee.ifa_addr, address.pointee.sa_family == AF_INET,
                  row.pointee.ifa_flags & UInt32(IFF_UP) != 0 else { continue }
            let name = String(cString: row.pointee.ifa_name)
            var host = [CChar](repeating: 0, count: Int(NI_MAXHOST))
            guard getnameinfo(address, socklen_t(address.pointee.sa_len), &host, socklen_t(host.count), nil, 0, NI_NUMERICHOST) == 0 else { continue }
            let text = String(cString: host)
            if PhoneRelayWire.vpnIPv4(text) { result.vpn = text }
            else if PhoneRelayWire.privateIPv4(text), !text.hasPrefix("127."),
                    name.hasPrefix("en") || name.hasPrefix("bridge") || name.hasPrefix("ap") {
                if result.lan == nil || name == "en0" { result.lan = text }
            }
        }
        return result
    }
}

/// Explicit, foreground-only relay. Listens on selected private addresses and
/// loopback (also used by userspace VPN forwarding), never a public wildcard.
final class PhoneRelayServer {
    struct Snapshot { let online: Int; let running: Bool; let message: String }
    var changed: ((Snapshot) -> Void)?
    var diagnostic: ((String) -> Void)?
    private let queue = DispatchQueue(label: "zgta.phone-relay", qos: .userInitiated)
    private let announcement = LobbyAnnouncement()
    private var core: PhoneRelayCore?
    private var listeners: [NWListener] = []
    private var connections: [UUID: Client] = [:]
    private var timer: DispatchSourceTimer?
    private var generation: UInt64 = 0
    private var starting: ((Result<Void, Error>) -> Void)?
    private var readyAddresses: Set<String> = []
    private var waitingReason: String?
    private var requiredListeners = 0
    private var active = false
    private final class Client {
        let socket: NWConnection
        var buffer = Data()
        var upgraded = false
        var joined = false
        var recoveryOffered = false
        var since = ProcessInfo.processInfo.systemUptime
        var lastInput = ProcessInfo.processInfo.systemUptime
        var outgoing: [Data] = []
        var sendingSince: TimeInterval?
        init(_ socket: NWConnection) { self.socket = socket }
    }
    enum Failure: LocalizedError {
        case unavailable
        case listener(String)
        var errorDescription: String? {
            switch self {
            case .unavailable: return "The iPhone listener could not start with the selected private address or port."
            case .listener(let detail): return detail
            }
        }
    }
    func start(addresses: [String], room: String, port: UInt16 = 47540, completion: @escaping (Result<Void, Error>) -> Void) {
        queue.async { [self] in
            guard core == nil, port > 0, PhoneRelayWire.validText(room, maximum: 64), !addresses.isEmpty,
                  addresses.allSatisfy({ PhoneRelayWire.privateIPv4($0) }) else {
                DispatchQueue.main.async { completion(.failure(Failure.unavailable)) }; return
            }
            generation &+= 1; let attempt = generation
            core = PhoneRelayCore(room: room); starting = completion
            let unique = Array(Set(addresses)).sorted(); requiredListeners = unique.count; readyAddresses.removeAll(); waitingReason = nil
            log("Starting private listeners on \(unique.joined(separator: ", ")):\(port)")
            do {
                for address in unique {
                    let parameters = NWParameters.tcp
                    parameters.requiredLocalEndpoint = .hostPort(host: NWEndpoint.Host(address), port: NWEndpoint.Port(rawValue: port)!)
                    // Network.framework needs reuse for distinct local-address
                    // listeners sharing one port; otherwise the second listener
                    // fails with EADDRINUSE even though its address is different.
                    parameters.allowLocalEndpointReuse = true
                    let listener = try NWListener(using: parameters)
                    listeners.append(listener)
                    listener.newConnectionHandler = { [weak self] socket in
                        guard let self, self.generation == attempt, self.active else { socket.cancel(); return }
                        self.accept(socket)
                    }
                    listener.stateUpdateHandler = { [weak self, weak listener] state in
                        guard let self, self.generation == attempt, self.core != nil else { return }
                        switch state {
                        case .ready:
                            guard listener?.port?.rawValue == port else {
                                self.stopInternal("Listener reported an unexpected local port at \(address).")
                                return
                            }
                            self.readyAddresses.insert(address)
                            self.log("Listener ready on \(address):\(port)")
                            if self.readyAddresses.count == self.requiredListeners {
                                if unique.contains(where: { !$0.hasPrefix("127.") && !PhoneRelayWire.vpnIPv4($0) }) { self.announcement.start(room: room, port: Int32(port)) }
                                self.active = true; let done = self.starting; self.starting = nil
                                self.publish("Hosting on this iPhone. Keep ZGTA V open.")
                                DispatchQueue.main.async { done?(.success(())) }
                            }
                        case .waiting(let error):
                            self.readyAddresses.remove(address)
                            let reason = "Listener waiting at \(address):\(port): \(error)"
                            self.waitingReason = reason; self.log(reason)
                            if self.active { self.stopInternal(reason + ". The hosting network changed; reopen ZGTA V before hosting again.") }
                        case .failed(let error):
                            self.stopInternal("Listener failed at \(address):\(port): \(error)")
                        default: break
                        }
                    }
                    listener.start(queue: queue)
                }
                let clock = DispatchSource.makeTimerSource(queue: queue)
                clock.schedule(deadline: .now()+1, repeating: 1)
                clock.setEventHandler { [weak self] in
                    guard let self, self.generation == attempt else { return }
                    let now = ProcessInfo.processInfo.systemUptime
                    for (id, client) in self.connections {
                        if (!client.joined && now-client.since > 5) || now-client.lastInput > 30 || client.sendingSince.map({ now-$0 > 2 }) == true { self.close(id) }
                    }
                    self.core?.expire()
                }
                timer = clock; clock.resume()
                queue.asyncAfter(deadline: .now()+15) { [weak self] in
                    guard let self, self.generation == attempt, self.starting != nil else { return }
                    self.stopInternal("Hosting startup timed out. " + (self.waitingReason ?? "No listener readiness result was received."))
                }
            } catch { stopInternal("Could not create the iPhone listener: \(error.localizedDescription)") }
        }
    }
    func stop() { queue.async { [self] in stopInternal("Hosting stopped.") } }
    private func log(_ message: String) {
        DispatchQueue.main.async { [weak self] in self?.diagnostic?("Phone hosting: " + message) }
    }
    private func stopInternal(_ message: String) {
        log(message)
        announcement.stop()
        generation &+= 1; active = false
        for listener in listeners { listener.cancel() }; listeners.removeAll()
        for id in Array(connections.keys) { close(id) }
        timer?.cancel(); timer = nil; core = nil
        let done = starting; starting = nil
        publish(message)
        if let done { DispatchQueue.main.async { done(.failure(Failure.listener(message))) } }
    }
    private func publish(_ message: String) {
        let snapshot = Snapshot(online: core?.online ?? 0, running: active, message: message)
        DispatchQueue.main.async { [weak self] in self?.changed?(snapshot) }
    }
    private func accept(_ socket: NWConnection) {
        guard connections.count < 32, case let .hostPort(host, _) = socket.endpoint else { socket.cancel(); return }
        let text: String
        switch host { case .ipv4(let ip): text = ip.debugDescription; case .ipv6(let ip): text = ip.debugDescription; default: socket.cancel(); return }
        guard PhoneRelayWire.privateIPv4(text) || text == "::1" else { socket.cancel(); return }
        let id = UUID(); connections[id] = Client(socket)
        socket.stateUpdateHandler = { [weak self] state in
            guard let self else { return }
            switch state { case .ready: self.receive(id); case .failed, .cancelled: self.close(id); default: break }
        }
        socket.start(queue: queue)
    }
    private func close(_ id: UUID) {
        guard let client = connections.removeValue(forKey: id) else { return }
        core?.depart(id); client.socket.cancel()
        if client.joined { publish("Hosting on this iPhone. Keep ZGTA V open.") }
    }
    private func receive(_ id: UUID) {
        guard let client = connections[id] else { return }
        client.socket.receive(minimumIncompleteLength: 1, maximumLength: 8192) { [weak self, weak client] data, _, complete, error in
            guard let self, let client, self.connections[id] === client else { return }
            if let data, !data.isEmpty {
                client.buffer.append(data)
                guard client.buffer.count <= 16384 else { self.close(id); return }
                do { try self.process(id, client) } catch { self.close(id); return }
            }
            if complete || error != nil { self.close(id) }
            else if self.connections[id] === client { self.receive(id) }
        }
    }
    private func process(_ id: UUID, _ client: Client) throws {
        guard let core else { throw PhoneRelayWire.Failure.invalid }
        if !client.upgraded {
            guard let boundary = client.buffer.range(of: Data([13,10,13,10])) else {
                if client.buffer.count > 8192 { throw PhoneRelayWire.Failure.invalid }; return
            }
            let header = Data(client.buffer[..<boundary.upperBound])
            let parsed = try PhoneRelayWire.header(header)
            client.buffer = Data(client.buffer[boundary.upperBound...])
            if parsed.health {
                core.expire()
                let body = try PhoneRelayWire.json(["service":"zgta-engine-lan", "protocol":PhoneRelayWire.version, "build":PhoneRelayWire.build, "instance":core.instance, "peers":core.online, "rooms":1, "room_policy":"hosted", "catalog_version":1, "lobbies":[["room":core.room,"players":core.online,"slots":core.peers.count,"capacity":8,"player_names":core.peers.values.filter { $0.connection != nil }.sorted { $0.vip < $1.vip }.map { $0.name }]]])
                var response = Data("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: \(body.count)\r\n\r\n".utf8); response.append(body)
                client.socket.send(content: response, completion: .contentProcessed { [weak self] _ in self?.close(id) }); return
            }
            enqueue(parsed.response, to: id); client.upgraded = true; client.since = ProcessInfo.processInfo.systemUptime
        }
        while let frame = try PhoneRelayWire.nextFrame(&client.buffer) {
            client.lastInput = ProcessInfo.processInfo.systemUptime
            if !client.joined {
                guard frame.opcode == 1 else { throw PhoneRelayWire.Failure.invalid }
                let admitted: (joined: Data, replaced: UUID?)
                do { admitted = try core.admit(frame.payload, connection: id) }
                catch PhoneRelayWire.Failure.resumeUnavailable where !client.recoveryOffered {
                    client.recoveryOffered = true
                    let response = try PhoneRelayWire.json(["type":"resume-unavailable", "protocol":PhoneRelayWire.version, "build":PhoneRelayWire.build, "epoch":core.epoch, "recovery":"same-address-v1"])
                    enqueue(PhoneRelayWire.frame(response, opcode: 1), to: id)
                    continue
                } catch PhoneRelayWire.Failure.addressUnavailable {
                    let response = try PhoneRelayWire.json(["type":"rejoin-unavailable", "protocol":PhoneRelayWire.version, "build":PhoneRelayWire.build])
                    enqueue(PhoneRelayWire.frame(response, opcode: 1), to: id)
                    continue
                }
                if let old = admitted.replaced, old != id { close(old) }
                client.joined = true; enqueue(PhoneRelayWire.frame(admitted.joined, opcode: 1), to: id); publish("Hosting on this iPhone. Keep ZGTA V open.")
            } else {
                switch frame.opcode {
                case 2:
                    let targets = try core.destinations(frame.payload, from: id), packet = PhoneRelayWire.frame(frame.payload, opcode: 2)
                    for target in targets { enqueue(packet, to: target) }
                case 8: close(id); return
                case 9: enqueue(PhoneRelayWire.frame(frame.payload, opcode: 10), to: id)
                case 10: break
                case 1 where frame.payload == Data("{\"type\":\"ping\"}".utf8): enqueue(PhoneRelayWire.frame(Data("{\"type\":\"pong\"}".utf8), opcode: 1), to: id)
                default: throw PhoneRelayWire.Failure.invalid
                }
            }
        }
    }
    private func enqueue(_ bytes: Data, to id: UUID) {
        guard let client = connections[id] else { return }
        guard client.outgoing.count < 64 else { close(id); return }
        client.outgoing.append(bytes)
        if client.sendingSince == nil { sendNext(id) }
    }
    private func sendNext(_ id: UUID) {
        guard let client = connections[id] else { return }
        guard !client.outgoing.isEmpty else { client.sendingSince = nil; return }
        let bytes = client.outgoing.removeFirst(); client.sendingSince = ProcessInfo.processInfo.systemUptime
        client.socket.send(content: bytes, completion: .contentProcessed { [weak self, weak client] error in
            guard let self, let client, self.connections[id] === client else { return }
            if error != nil { self.close(id) } else { self.sendNext(id) }
        })
    }
}
