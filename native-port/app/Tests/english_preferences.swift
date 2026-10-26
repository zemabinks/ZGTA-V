import Foundation

// No application, native engine, real preferences, sockets or game files.
final class MemoryDefaults: UserDefaults {
    private var values: [String: Any] = [:]
    override func object(forKey key: String) -> Any? { values[key] }
    override func string(forKey key: String) -> String? { values[key] as? String }
    override func bool(forKey key: String) -> Bool { values[key] as? Bool ?? false }
    override func set(_ value: Any?, forKey key: String) { values[key] = value }
}

@main struct EnglishPreferencesTests {
    static var checks = 0
    static func check(_ condition: Bool, _ description: String) {
        precondition(condition, description); checks += 1
    }
    static func main() throws {
        let catalogURL = URL(fileURLWithPath: CommandLine.arguments[1])
        let catalog = try JSONDecoder().decode([String: [String: String]].self, from: Data(contentsOf: catalogURL))
        let defaults = MemoryDefaults()
        check(L10n.preferredLanguage(in: defaults) == "en", "fresh install is English")
        defaults.set("vi", forKey: "MugoatLanguage")
        check(L10n.preferredLanguage(in: defaults) == "en", "upgrade ignores obsolete language selection")
        defaults.set("unsupported", forKey: "MugoatLanguage")
        check(L10n.preferredLanguage(in: defaults) == "en", "unknown preference falls back to English")
        func text(_ value: String, _ language: String) -> String { L10n.text(value, language: language, catalog: catalog) }
        check(text("Play", "en") == "Play", "English label")
        check(text("Play", "vi") == "Play", "removed language cannot be enabled")
        let filename = "File: Looking for your game files….zip"
        check(text(filename, "vi") == filename, "do not translate substrings in filenames")
        let model = "my-Đang triệu hồi-model"
        let rendered = String(format: text("Spawning: %@", "en"), model)
        check(rendered == "Spawning: " + model, "template leaves model data untouched")
        check(text(rendered, "vi") == rendered, "no substring mutations in rendered values")
        check(text("unknown-user-payload", "en") == "unknown-user-payload", "unknown payload preserved")

        let preferences = OnlinePreferences(defaults: defaults)
        check(!preferences.enabled && preferences.server.isEmpty && !preferences.pvp, "offline, blank server and PvP off by default")
        preferences.server = "192.168.1.10:47520"; preferences.enabled = true
        preferences.name = "Alex"; preferences.room = "lan-peace"; preferences.role = "Cảnh sát"; preferences.pvp = true
        let resumed = OnlinePreferences(defaults: defaults)
        check(resumed.enabled && resumed.server == "192.168.1.10:47520", "preserve explicit online configuration")
        check(resumed.name == "Alex" && resumed.room == "lan-peace" && resumed.pvp, "preserve saved identity and PvP preference")
        check(resumed.role == "Cảnh sát", "preserve canonical stored role")
        let expectedRoles = ["Civilian", "Police", "Medic", "Gang", "Driver"]
        check(OnlinePreferences.roles.map { text($0, "en") } == expectedRoles, "English role presentation")
        check(OnlinePreferences.wireName(name: "Alex", role: resumed.role) == "[Cảnh sát] Alex", "retain native role mechanics on the wire")
        check(OnlinePreferences.wireName(name: "[Bác sĩ] Alex", role: resumed.role) == "[Bác sĩ] Alex", "preserve explicitly prefixed existing identity")
        preferences.role = "unknown"
        check(preferences.role == OnlinePreferences.roles[0], "unknown role safely defaults without rewriting storage")
        check(defaults.string(forKey: "MugoatOnlineRole") == "unknown", "reads do not rewrite old preferences")
        for host in ["192.168.1.10", "127.0.0.1:47520", "localhost", "macbook.local:65535", "gta-lab.local:1"] {
            check(OnlineInput.validHost(host), "accept explicit endpoint: " + host)
        }
        for host in ["", "256.1.1.1", "192.168.1", "host:", "host:0", "host:65536", "host:-1", "host:abc", "ws://host:47533/ws", "https://host", "host/path", "user@host", "host\n", "host name", "-host", "host-", "a..b", "[::1]", "a:1:2", String(repeating: "a", count: 64)] {
            check(!OnlineInput.validHost(host), "reject malformed/different protocol endpoint: " + host)
        }
        check(OnlineInput.validName("Alex", role: "Cảnh sát"), "valid role name")
        for name in ["", "  ", "A\0B", "A\nB", String(repeating: "a", count: 25), String(repeating: "😀", count: 13)] {
            check(!OnlineInput.validName(name, role: "Dân thường"), "reject empty, control or truncated name")
        }
        check(!OnlineInput.validName(String(repeating: "a", count: 20), role: "Cảnh sát"), "count role prefix against server name limit")
        check(OnlineInput.validRoom("LOS-SANTOS-peace"), "explicit room")
        for room in ["", " \n", "a\0b", String(repeating: "x", count: 65), String(repeating: "😀", count: 17)] {
            check(!OnlineInput.validRoom(room), "reject invalid room")
        }
        check(OnlineInput.valid(server: "localhost:47520", name: "Alex", room: "lan-peace", role: "Cảnh sát"), "valid combined configuration")
        print("PASS: \(checks) English/defaults/identity/endpoint checks; in-memory preferences only.")
    }
}
