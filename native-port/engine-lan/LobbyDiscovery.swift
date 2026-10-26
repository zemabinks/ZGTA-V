import Foundation
import Darwin

/// Discovery is an explicit, foreground screen action. Every result is health-checked.
final class LobbyLANDiscovery: NSObject, NetServiceBrowserDelegate, NetServiceDelegate {
    var found: ((String)->Void)?
    private let browser=NetServiceBrowser()
    private var services:[NetService]=[]
    func start(){stop();browser.delegate=self;browser.searchForServices(ofType:"_zgtav._tcp.",inDomain:"local.")}
    func stop(){browser.stop();for service in services{service.stop();service.delegate=nil};services.removeAll()}
    func netServiceBrowser(_ browser: NetServiceBrowser,didFind service: NetService,moreComing: Bool){
        guard services.count<8,!services.contains(where:{$0.name==service.name&&$0.domain==service.domain}) else{return}
        services.append(service);service.delegate=self;service.resolve(withTimeout:2)
    }
    func netServiceDidResolveAddress(_ sender: NetService){
        guard (1...65535).contains(sender.port) else{return}
        for data in sender.addresses ?? [] {
            let host:String?=data.withUnsafeBytes { raw in
                guard let pointer=raw.baseAddress,raw.count>=MemoryLayout<sockaddr_in>.size else{return nil}
                let address=pointer.assumingMemoryBound(to:sockaddr.self)
                guard address.pointee.sa_family==AF_INET else{return nil}
                var name=[CChar](repeating:0,count:Int(NI_MAXHOST))
                guard getnameinfo(address,socklen_t(raw.count),&name,socklen_t(name.count),nil,0,NI_NUMERICHOST)==0 else{return nil}
                return String(cString:name)
            }
            if let host,!host.hasPrefix("127."),let record=LobbyRecord.parse("ws://\(host):\(sender.port)/engine-lan"),record.connection == .lan {found?(record.relay)}
        }
    }
    deinit{browser.stop();for service in services{service.stop()}}
}
