import Foundation

/// Explicit app preferences only. Never enable networking or inherit a public
/// endpoint merely because an older config.json happens to be present.
final class OnlinePreferences {
    private let defaults: UserDefaults
    init(defaults: UserDefaults = .standard) { self.defaults = defaults }
    var enabled: Bool {
        get { defaults.bool(forKey: "MugoatOnlineEnabled") }
        set { defaults.set(newValue, forKey: "MugoatOnlineEnabled") }
    }
    var server: String {
        get { defaults.string(forKey: "MugoatOnlineServer") ?? "" }
        set { defaults.set(newValue, forKey: "MugoatOnlineServer") }
    }
    var name: String {
        get { defaults.string(forKey: "MugoatOnlineName") ?? "Player" }
        set { defaults.set(newValue, forKey: "MugoatOnlineName") }
    }
    var room: String {
        get { defaults.string(forKey: "MugoatOnlineRoom") ?? "story" }
        set { defaults.set(newValue, forKey: "MugoatOnlineRoom") }
    }
    // These identifiers are parsed by src/mp.rs::role_of. Translate the picker,
    // never these saved values or the on-wire name prefixes.
    static let roles = ["Dân thường", "Cảnh sát", "Bác sĩ", "Băng đảng", "Tài xế"]
    var role: String {
        get {
            let stored = defaults.string(forKey: "MugoatOnlineRole") ?? Self.roles[0]
            return Self.roles.contains(stored) ? stored : Self.roles[0]
        }
        set { defaults.set(newValue, forKey: "MugoatOnlineRole") }
    }
    var pvp: Bool {
        get { defaults.bool(forKey: "MugoatOnlinePVP") }
        set { defaults.set(newValue, forKey: "MugoatOnlinePVP") }
    }
    static func wireName(name: String, role: String) -> String {
        role != roles[0] && !name.hasPrefix("[") ? "[\(role)] \(name)" : name
    }
}

enum OnlineInput {
    // Match the native bridge's documented IPv4/hostname[:port] form. URLs,
    // credentials, paths and raw WebSocket addresses are different protocols.
    static func validHost(_ host: String) -> Bool {
        guard !host.isEmpty, host.utf8.count <= 253, host.unicodeScalars.allSatisfy({ $0.isASCII }) else { return false }
        let parts = host.split(separator: ":", omittingEmptySubsequences: false)
        guard parts.count <= 2 else { return false }
        if parts.count == 2 {
            guard !parts[1].isEmpty, parts[1].allSatisfy({ $0 >= "0" && $0 <= "9" }),
                  let port = Int(parts[1]), (1...65535).contains(port) else { return false }
        }
        let address = String(parts[0])
        if address.allSatisfy({ $0.isNumber || $0 == "." }) {
            let octets = address.split(separator: ".", omittingEmptySubsequences: false)
            return octets.count == 4 && octets.allSatisfy { !$0.isEmpty && $0.count <= 3 && (Int($0).map { (0...255).contains($0) } ?? false) }
        }
        let labels = address.split(separator: ".", omittingEmptySubsequences: false)
        return labels.allSatisfy { label in
            !label.isEmpty && label.count <= 63 && label.first != "-" && label.last != "-" &&
            label.allSatisfy { $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "-") }
        }
    }
    static func validName(_ name: String, role: String) -> Bool {
        let wire = OnlinePreferences.wireName(name: name, role: role)
        return !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
            !name.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }) &&
            wire.utf8.count <= 48 && wire.unicodeScalars.count <= 24
    }
    static func validRoom(_ room: String) -> Bool {
        !room.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && room.utf8.count <= 64 &&
            !room.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) })
    }
    static func valid(server: String, name: String, room: String, role: String) -> Bool {
        validHost(server) && validName(name, role: role) && validRoom(room)
    }
}
