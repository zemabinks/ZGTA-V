import Foundation

/// Bonjour advertises existing private listeners; it never creates another game server.
final class LobbyAnnouncement {
    private var service: NetService?
    func start(room: String, port: Int32) {
        DispatchQueue.main.async { [self] in
            service?.stop()
            var name="ZGTA V · "+room
            while name.utf8.count>63{name.removeLast()}
            let value=NetService(domain:"local.",type:"_zgtav._tcp.",name:name,port:port)
            value.setTXTRecord(NetService.data(fromTXTRecord:["protocol":Data(PhoneRelayWire.version.utf8),"build":Data(PhoneRelayWire.build.utf8)]))
            service=value;value.publish()
        }
    }
    func stop(){DispatchQueue.main.async{[self] in service?.stop();service=nil}}
}
