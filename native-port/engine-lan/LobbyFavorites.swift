import Foundation

/// Explicit user choices only. Joining a lobby never silently favorites it.
/// Separate storage preserves the existing recent-lobby and connection data.
enum LobbyFavorites {
    private static let key = "zgta.favorite-lobbies.v1"
    static func identity(_ record: LobbyRecord) -> String { record.relay + "\n" + record.room }
    static func load(store: UserDefaults = .standard) -> [LobbyRecord] {
        guard let data = store.data(forKey: key), data.count <= 32768,
              let decoded = try? JSONDecoder().decode([LobbyRecord].self, from: data) else { return [] }
        var seen = Set<String>()
        return decoded.prefix(32).compactMap { record in
            guard var checked = LobbyRecord.parse(record.relay, room: record.room),
                  seen.insert(identity(checked)).inserted else { return nil }
            checked.label = String(record.label.prefix(48)); return checked
        }
    }
    static func contains(_ record: LobbyRecord, store: UserDefaults = .standard) -> Bool {
        load(store: store).contains { identity($0) == identity(record) }
    }
    @discardableResult static func set(_ record: LobbyRecord, saved: Bool, store: UserDefaults = .standard) -> Bool {
        guard var checked = LobbyRecord.parse(record.relay, room: record.room) else { return false }
        checked.label = String(record.label.prefix(48))
        var records = load(store: store).filter { identity($0) != identity(checked) }
        if saved { guard records.count < 32 else { return false }; records.insert(checked, at: 0) }
        guard let data = try? JSONEncoder().encode(records), data.count <= 32768 else { return false }
        store.set(data, forKey: key); return true
    }
}
