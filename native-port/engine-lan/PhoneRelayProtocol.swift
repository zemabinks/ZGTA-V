import Foundation
import CryptoKit
import CoreFoundation

/// The phone relay carries the same bounded DATA packets as relay.py. It never
/// runs a second game engine, translates snapshots, or reads character files.
enum PhoneRelayWire {
    static let version = "zema-engine-lan/1"
    static let build = "8b0b5899ed"
    static let maximumFrame = 2048
    enum Failure: Error { case invalid, resumeUnavailable, addressUnavailable }
    static func validText(_ text: String, maximum: Int) -> Bool {
        !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && text.utf8.count <= maximum &&
        !text.unicodeScalars.contains { $0.value < 32 || (127..<160).contains($0.value) }
    }
    static func privateIPv4(_ text: String) -> Bool {
        guard let ip = ipv4(text) else { return false }
        return ip >> 24 == 127 || ip >> 24 == 10 || ip >> 16 == 0xc0a8 ||
            (ip >> 20 == 0xac1) || ip >> 16 == 0xa9fe || ip >> 22 == 0x191
    }
    static func vpnIPv4(_ text: String) -> Bool { ipv4(text).map { $0 >> 22 == 0x191 } ?? false }
    static func ipv4(_ text: String) -> UInt32? {
        let parts = text.split(separator: ".", omittingEmptySubsequences: false)
        guard parts.count == 4 else { return nil }
        var value: UInt32 = 0
        for part in parts {
            guard !part.isEmpty, part.allSatisfy({ $0 >= "0" && $0 <= "9" }),
                  let byte = UInt8(part), String(byte) == part else { return nil }
            value = value << 8 | UInt32(byte)
        }
        return value
    }
    static func virtualIP(_ ip: UInt32) -> Bool { ip & 0xffff0000 == 0x0a4d0000 && ip & 255 != 0 && ip & 255 != 255 }
    static func header(_ data: Data) throws -> (response: Data, health: Bool) {
        guard data.count <= 8192, data.allSatisfy({ $0 < 128 }),
              let text = String(data: data, encoding: .ascii), text.hasSuffix("\r\n\r\n") else { throw Failure.invalid }
        let lines = text.components(separatedBy: "\r\n")
        guard lines[0] == "GET /engine-lan HTTP/1.1" || lines[0] == "GET /health HTTP/1.1" else { throw Failure.invalid }
        var fields: [String: String] = [:]
        for line in lines.dropFirst() where !line.isEmpty {
            guard let colon = line.firstIndex(of: ":") else { throw Failure.invalid }
            let key = String(line[..<colon]).lowercased()
            guard !key.isEmpty, fields[key] == nil else { throw Failure.invalid }
            fields[key] = String(line[line.index(after: colon)...]).trimmingCharacters(in: .whitespaces)
        }
        if let origin = fields["origin"], !["http://127.0.0.1:18886", "http://localhost:18886", "http://127.0.0.1:18887", "http://localhost:18887"].contains(origin) { throw Failure.invalid }
        if lines[0] == "GET /health HTTP/1.1" { return (Data(), true) }
        guard let key = fields["sec-websocket-key"], Data(base64Encoded: key)?.count == 16,
              fields["sec-websocket-version"] == "13", fields["upgrade"]?.lowercased() == "websocket",
              fields["connection"]?.lowercased().split(separator: ",").contains(where: { $0.trimmingCharacters(in: .whitespaces) == "upgrade" }) == true else { throw Failure.invalid }
        let digest = Insecure.SHA1.hash(data: Data((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").utf8))
        let accept = Data(digest).base64EncodedString()
        return (Data("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: \(accept)\r\n\r\n".utf8), false)
    }
    static func nextFrame(_ buffer: inout Data) throws -> (opcode: UInt8, payload: Data)? {
        guard buffer.count >= 2 else { return nil }
        let head = Array(buffer.prefix(8)), opcode = head[0] & 15
        guard head[0] & 0x70 == 0, head[0] & 0x80 != 0, head[1] & 0x80 != 0,
              [1, 2, 8, 9, 10].contains(opcode) else { throw Failure.invalid }
        var length = Int(head[1] & 127), offset = 2
        if length == 127 { throw Failure.invalid }
        if length == 126 {
            guard buffer.count >= 4 else { return nil }
            length = Int(head[2]) << 8 | Int(head[3]); offset = 4
            guard length >= 126 else { throw Failure.invalid }
        }
        guard length <= maximumFrame, (opcode < 8 || length <= 125), !(opcode == 8 && length == 1) else { throw Failure.invalid }
        guard buffer.count >= offset + 4 + length else { return nil }
        let bytes = Array(buffer.prefix(offset + 4 + length)), mask = Array(bytes[offset..<offset+4])
        let payload = Data((0..<length).map { bytes[offset+4+$0] ^ mask[$0 % 4] })
        buffer = Data(buffer.dropFirst(offset + 4 + length))
        return (opcode, payload)
    }
    static func frame(_ payload: Data, opcode: UInt8) -> Data {
        precondition(payload.count <= maximumFrame)
        var bytes: [UInt8] = [0x80 | opcode]
        if payload.count < 126 { bytes.append(UInt8(payload.count)) }
        else { bytes += [126, UInt8(payload.count >> 8), UInt8(payload.count & 255)] }
        var result = Data(bytes); result.append(payload); return result
    }
    static func json(_ value: [String: Any]) throws -> Data { try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]) }
}

/// Confined to the listener's serial queue. Eight players, including the host;
/// reservations last 20 seconds and never change the identity of a running game.
final class PhoneRelayCore {
    struct Peer {
        let vip: UInt32
        var name: String
        let token: String
        var connection: UUID?
        var expires: TimeInterval = 0
        var window: TimeInterval = 0
        var packets = 0
    }
    let room: String
    let epoch = String(format: "%016llx", UInt64.random(in: 1...UInt64.max))
    let instance = UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased()
    private let now: () -> TimeInterval
    private(set) var peers: [UInt32: Peer] = [:]
    var online: Int { peers.values.filter { $0.connection != nil }.count }
    init(room: String, now: @escaping () -> TimeInterval = { ProcessInfo.processInfo.systemUptime }) {
        self.room = room; self.now = now
    }
    func expire() { peers = peers.filter { $0.value.connection != nil || $0.value.expires > now() } }
    func admit(_ bytes: Data, connection: UUID) throws -> (joined: Data, replaced: UUID?) {
        expire()
        guard let message = try JSONSerialization.jsonObject(with: bytes) as? [String: Any],
              Set(message.keys).isSubset(of: ["type", "protocol", "build", "room", "name", "resume", "rejoin"]),
              message["type"] as? String == "join", message["protocol"] as? String == PhoneRelayWire.version,
              message["build"] as? String == PhoneRelayWire.build, message["room"] as? String == room,
              PhoneRelayWire.validText(room, maximum: 64), let name = message["name"] as? String,
              PhoneRelayWire.validText(name, maximum: 48) else { throw PhoneRelayWire.Failure.invalid }
        let rawToken = message["resume"]
        guard rawToken == nil || rawToken is NSNull || rawToken is String else { throw PhoneRelayWire.Failure.invalid }
        let recovery = message["rejoin"]
        guard recovery == nil || rawToken == nil else { throw PhoneRelayWire.Failure.invalid }
        var peer: Peer
        if let token = rawToken as? String {
            guard token.utf8.count == 32, token.utf8.allSatisfy({ (48...57).contains($0) || (65...90).contains($0) || (97...122).contains($0) || $0 == 45 || $0 == 95 }) else { throw PhoneRelayWire.Failure.invalid }
            guard let existing = peers.values.first(where: { Self.equalToken($0.token, token) }) else { throw PhoneRelayWire.Failure.resumeUnavailable }
            peer = existing
        } else {
            let vip: UInt32
            if let recovery {
                guard let request = recovery as? [String: Any], Set(request.keys) == ["vip", "epoch"],
                      request["epoch"] as? String == epoch,
                      let number = request["vip"] as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID(),
                      number.doubleValue == Double(number.uint32Value), (1...8).contains(number.uint32Value & 0xffff),
                      number.uint32Value & 0xffff0000 == 0x0a4d0000 else { throw PhoneRelayWire.Failure.invalid }
                vip = number.uint32Value
                guard peers[vip] == nil else { throw PhoneRelayWire.Failure.addressUnavailable }
            } else {
                guard let slot = (1...8).first(where: { peers[0x0a4d0000 | UInt32($0)] == nil }) else { throw PhoneRelayWire.Failure.invalid }
                vip = 0x0a4d0000 | UInt32(slot)
            }
            let alphabet = Array("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_".utf8)
            let token = String(decoding: (0..<32).map { _ in alphabet.randomElement()! }, as: UTF8.self)
            peer = Peer(vip: vip, name: name, token: token, connection: nil)
        }
        let replaced = peer.connection
        peer.name = name
        peer.connection = connection; peer.window = now(); peer.packets = 0
        peers[peer.vip] = peer
        let response = try PhoneRelayWire.json(["type": "joined", "protocol": PhoneRelayWire.version, "build": PhoneRelayWire.build, "vip": peer.vip, "epoch": epoch, "resume": peer.token])
        return (response, replaced)
    }
    func depart(_ connection: UUID) {
        guard let vip = peers.first(where: { $0.value.connection == connection })?.key else { return }
        peers[vip]?.connection = nil; peers[vip]?.expires = now() + 20
    }
    func destinations(_ data: Data, from connection: UUID) throws -> [UUID] {
        guard let vip = peers.first(where: { $0.value.connection == connection })?.key, var peer = peers[vip],
              (16...2048).contains(data.count) else { throw PhoneRelayWire.Failure.invalid }
        let b = Array(data)
        func u32(_ offset: Int) -> UInt32 { b[offset..<offset+4].reduce(0) { $0 << 8 | UInt32($1) } }
        let source = u32(4), destination = u32(10)
        let broadcast = destination == UInt32.max || (destination & 0xffff0000 == 0x0a4d0000 && destination & 255 == 255)
        guard Array(b.prefix(4)) == [71, 53, 1, 3], source == vip, PhoneRelayWire.virtualIP(source),
              broadcast || PhoneRelayWire.virtualIP(destination), (b[8] != 0 || b[9] != 0), (b[14] != 0 || b[15] != 0) else { throw PhoneRelayWire.Failure.invalid }
        if now() - peer.window >= 1 { peer.window = now(); peer.packets = 0 }
        peer.packets += 1; peers[vip] = peer
        guard peer.packets <= 4096 else { throw PhoneRelayWire.Failure.invalid }
        return peers.values.compactMap { other in
            guard other.vip != vip, broadcast || other.vip == destination else { return nil }
            return other.connection
        }
    }
    private static func equalToken(_ lhs: String, _ rhs: String) -> Bool {
        let a = Array(lhs.utf8), b = Array(rhs.utf8)
        guard a.count == b.count else { return false }
        return zip(a, b).reduce(UInt8(0)) { $0 | ($1.0 ^ $1.1) } == 0
    }
}
