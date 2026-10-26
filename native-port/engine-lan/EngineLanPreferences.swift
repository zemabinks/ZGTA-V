import Foundation

protocol EngineLanPreferenceStore {
    func string(forKey key: String) -> String?
    func set(_ value: Any?, forKey key: String)
}
extension UserDefaults: EngineLanPreferenceStore {}

enum MultiplayerConnection: String, CaseIterable {
    case lan = "LAN"
    case remote = "Remote"

    func accepts(_ endpoint: String) -> Bool {
        guard let url = EngineLanSession.validEndpoint(endpoint), let host = url.host else { return false }
        let octets = host.split(separator: ".").compactMap { Int($0) }
        let vpn = octets.count == 4 && octets[0] == 100 && (64...127).contains(octets[1])
        return self == .remote ? vpn : !vpn
    }
    var instructions: String {
        self == .lan
            ? "Use the host relay’s Wi-Fi address. Both devices must be on the same local network."
            : "Connect Tailscale on this iPhone and the host, then enter the host’s 100.x Tailscale address. The host relay must be running."
    }
    var endpointHint: String {
        self == .lan ? "Wi-Fi IP or ws://192.168…:47540/engine-lan" : "Tailscale IP or ws://100.…:47540/engine-lan"
    }
    func endpoint(from text: String) -> String? {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let candidate = trimmed.contains("://") ? trimmed : "ws://\(trimmed):47540/engine-lan"
        return accepts(candidate) ? candidate : nil
    }
}

/// Only the chosen relay and room are preferences. Resume tokens and profile data stay elsewhere.
struct EngineLanPreferences {
    static let relayKey = "zema.engine-lan.relay.v1"
    static let roomKey = "zema.engine-lan.room.v1"
    static let connectionKey = "zema.multiplayer.connection.v1"
    static let remoteRelayKey = "zema.multiplayer.remote.relay.v1"
    static let remoteRoomKey = "zema.multiplayer.remote.room.v1"
    static func selected(from defaults: EngineLanPreferenceStore = UserDefaults.standard) -> MultiplayerConnection {
        if let value = defaults.string(forKey: connectionKey), let mode = MultiplayerConnection(rawValue: value) { return mode }
        return defaults.string(forKey: relayKey).map { MultiplayerConnection.remote.accepts($0) } == true ? .remote : .lan
    }
    static func load(mode: MultiplayerConnection, from defaults: EngineLanPreferenceStore = UserDefaults.standard) -> (relay: String, room: String) {
        let relay = defaults.string(forKey: mode == .lan ? relayKey : remoteRelayKey)
            ?? (mode == .remote ? defaults.string(forKey: relayKey) : nil) ?? ""
        let room = defaults.string(forKey: mode == .lan ? roomKey : remoteRoomKey)
            ?? (mode == .remote && mode.accepts(relay) ? defaults.string(forKey: roomKey) : nil) ?? defaultRoom
        return (mode.accepts(relay) ? relay : (mode == .lan ? defaultRelay : ""), validRoom(room) ? room : defaultRoom)
    }
    @discardableResult static func save(mode: MultiplayerConnection, relay: String, room: String, to defaults: EngineLanPreferenceStore = UserDefaults.standard) -> Bool {
        guard mode.accepts(relay), validRoom(room) else { return false }
        defaults.set(relay, forKey: mode == .lan ? relayKey : remoteRelayKey)
        defaults.set(room, forKey: mode == .lan ? roomKey : remoteRoomKey)
        defaults.set(mode.rawValue, forKey: connectionKey)
        return true
    }
    static let defaultRelay = ""
    static let defaultRoom = "LOS-SANTOS"
    static func validRoom(_ value: String) -> Bool {
        !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && value.utf8.count <= 64 &&
        !value.unicodeScalars.contains { CharacterSet.controlCharacters.contains($0) }
    }
    static func load(from defaults: EngineLanPreferenceStore = UserDefaults.standard) -> (relay: String, room: String) {
        let relay = defaults.string(forKey: relayKey) ?? defaultRelay
        let room = defaults.string(forKey: roomKey) ?? defaultRoom
        return (EngineLanSession.validEndpoint(relay) != nil ? relay : defaultRelay,
                validRoom(room) ? room : defaultRoom)
    }
    @discardableResult static func save(relay: String, room: String, to defaults: EngineLanPreferenceStore = UserDefaults.standard) -> Bool {
        guard EngineLanSession.validEndpoint(relay) != nil, validRoom(room) else { return false }
        defaults.set(relay, forKey: relayKey); defaults.set(room, forKey: roomKey)
        return true
    }
    static func summary(relay: String, room: String) -> String { "Room: \(room)\nHost relay: \(relay)" }
}
