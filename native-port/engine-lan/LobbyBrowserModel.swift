import Foundation

struct LobbyBrowserEntry {
    let record: LobbyRecord
    var health: LobbyHealth?
    var checkedAt: Date?
    var room: LobbyHealth.Room?
    var checking = true
    func fresh(at now: Date) -> Bool { checkedAt.map { now.timeIntervalSince($0) <= 30 } ?? false }
    func hostOnline(at now: Date) -> Bool { fresh(at: now) && health?.online == true && health?.incompatible != true }
    /// A guessed/saved room is never a live-directory result without advertisement.
    func listedOnline(at now: Date) -> Bool { hostOnline(at: now) && health?.catalog == true && room != nil }
    func canJoin(at now: Date) -> Bool { hostOnline(at: now) && (room != nil || health?.restricted == false) }
    func state(at now: Date) -> String {
        if checking && checkedAt == nil { return "Checking…" }
        if !fresh(at: now) { return checking ? "Checking…" : "Not checked recently" }
        if health?.incompatible == true { return "Different game version" }
        guard hostOnline(at: now) else { return "Offline" }
        if room != nil { return "Online" }
        return health?.restricted == true ? "Room unavailable" : "Host online · room not advertised"
    }
}

/// Pure live-list policy; all health responses still come from the bounded probe.
struct LobbyBrowserModel {
    private(set) var entries: [LobbyBrowserEntry] = []
    mutating func begin(records: [LobbyRecord]) -> [LobbyRecord] {
        let previous = Dictionary(entries.map { (LobbyFavorites.identity($0.record), $0) }, uniquingKeysWith: { first, _ in first })
        var hosts = Set<String>(), seen = Set<String>(), seeds = [LobbyRecord]()
        for record in records {
            guard hosts.contains(record.relay) || hosts.count < 32,
                  seen.insert(LobbyFavorites.identity(record)).inserted else { continue }
            if hosts.insert(record.relay).inserted { seeds.append(record) }
        }
        var next = [LobbyBrowserEntry]()
        for record in records where hosts.contains(record.relay) {
            let key = LobbyFavorites.identity(record)
            guard !next.contains(where: { LobbyFavorites.identity($0.record) == key }) else { continue }
            var entry = previous[key] ?? LobbyBrowserEntry(record: record)
            entry.checking = true; next.append(entry)
        }
        // Retain recent advertisements while their refresh is in flight; timeout
        // removes them immediately and the 30-second freshness cap fails closed.
        for old in entries where hosts.contains(old.record.relay) && !next.contains(where: { LobbyFavorites.identity($0.record) == LobbyFavorites.identity(old.record) }) {
            var entry = old; entry.checking = true; next.append(entry)
        }
        entries = next; return seeds
    }
    mutating func addCandidate(_ record: LobbyRecord) -> Bool {
        guard !entries.contains(where: { $0.record.relay == record.relay }), Set(entries.map { $0.record.relay }).count < 32 else { return false }
        entries.append(LobbyBrowserEntry(record: record)); return true
    }
    mutating func receive(relay: String, health: LobbyHealth?, at now: Date = Date()) {
        let originals = entries.filter { $0.record.relay == relay }
        entries.removeAll { $0.record.relay == relay }
        if let health, health.online, health.catalog {
            for room in health.rooms {
                let record = LobbyRecord(relay: relay, room: room.name)
                entries.append(LobbyBrowserEntry(record: record, health: health, checkedAt: now, room: room, checking: false))
            }
        }
        for old in originals where !entries.contains(where: { LobbyFavorites.identity($0.record) == LobbyFavorites.identity(old.record) }) {
            entries.append(LobbyBrowserEntry(record: old.record, health: health, checkedAt: now, room: health?.rooms.first { $0.name == old.record.room }, checking: false))
        }
    }
    func visible(favorites: [LobbyRecord], onlyFavorites: Bool, mode: MultiplayerConnection, at now: Date = Date()) -> [LobbyBrowserEntry] {
        let saved = Set(favorites.map(LobbyFavorites.identity))
        return entries.filter { $0.record.connection == mode && (onlyFavorites ? saved.contains(LobbyFavorites.identity($0.record)) : $0.listedOnline(at: now)) }.sorted {
            let a = $0.record.room.localizedCaseInsensitiveCompare($1.record.room)
            return a == .orderedSame ? $0.record.relay < $1.record.relay : a == .orderedAscending
        }
    }
}
