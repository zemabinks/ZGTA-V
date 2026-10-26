import Foundation

/// Identifies a private host/room only. Never contains resume tokens or saves.
struct LobbyRecord: Equatable, Codable {
    let relay: String
    let room: String
    var label: String = ""
    var connection: MultiplayerConnection { MultiplayerConnection.remote.accepts(relay) ? .remote : .lan }
    var invite: String {
        var url = URLComponents(); url.scheme = "zgtav"; url.host = "join"
        url.queryItems = [URLQueryItem(name:"relay",value:relay),URLQueryItem(name:"room",value:room)]
        url.percentEncodedQuery = url.percentEncodedQuery?.replacingOccurrences(of:"+",with:"%2B")
        return url.string ?? ""
    }
    static func parse(_ input: String, room fallback: String = "LOS-SANTOS") -> LobbyRecord? {
        guard input.utf8.count <= 1024 else { return nil }
        var text=input.trimmingCharacters(in:.whitespacesAndNewlines), room=fallback
        if text.hasPrefix("zgtav:") {
            guard let url=URLComponents(string:text.replacingOccurrences(of:"+",with:"%20")),url.scheme=="zgtav",url.host=="join",url.user==nil,url.password==nil,url.port==nil,url.fragment==nil,(url.path.isEmpty||url.path=="/"),let items=url.queryItems,items.count==2,Set(items.map(\.name))==["relay","room"],let address=items.first(where:{$0.name=="relay"})?.value,let value=items.first(where:{$0.name=="room"})?.value else{return nil}
            text=address;room=value
        }
        guard text.utf8.count<=128,EngineLanPreferences.validRoom(room) else{return nil}
        if !text.contains("://") {
            guard text.range(of:"^[0-9.]+(?::[1-9][0-9]{0,4})?$",options:.regularExpression) != nil else{return nil}
            text="ws://"+text+(text.contains(":") ? "" : ":47540")+"/engine-lan"
        }
        guard let url=EngineLanSession.validEndpoint(text) else{return nil}
        return LobbyRecord(relay:url.absoluteString,room:room)
    }
}

enum LobbyHistory {
    private static let key="zgta.saved-lobbies.v1"
    static func load() -> [LobbyRecord] {
        guard let data=UserDefaults.standard.data(forKey:key),data.count<=32768,let values=try? JSONDecoder().decode([LobbyRecord].self,from:data) else{return []}
        var seen=Set<String>()
        return values.prefix(12).compactMap { value in
            guard var checked=LobbyRecord.parse(value.relay,room:value.room),seen.insert(value.relay+"\n"+value.room).inserted else{return nil}
            checked.label=String(value.label.prefix(48));return checked
        }
    }
    static func remember(_ record: LobbyRecord) {
        guard let valid=LobbyRecord.parse(record.relay,room:record.room) else{return}
        var rows=load().filter{$0.relay != valid.relay || $0.room != valid.room};rows.insert(valid,at:0)
        if let data=try? JSONEncoder().encode(Array(rows.prefix(12))){UserDefaults.standard.set(data,forKey:key)}
    }
    static func forget(_ record: LobbyRecord) {
        if let data=try? JSONEncoder().encode(load().filter{$0.relay != record.relay || $0.room != record.room}){UserDefaults.standard.set(data,forKey:key)}
    }
}
