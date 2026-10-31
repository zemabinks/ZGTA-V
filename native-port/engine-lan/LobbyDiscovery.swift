import Foundation
import Darwin

/// Foreground Bonjour discovery. Advertisements are only seeds for /health.
final class LobbyLANDiscovery: NSObject, NetServiceBrowserDelegate, NetServiceDelegate {
    var found: ((String) -> Void)?
    var onStatus: ((String?) -> Void)?
    private let browser = NetServiceBrowser()
    private var services: [NetService] = []
    private var attempts: [ObjectIdentifier: Int] = [:]
    private var retries: [ObjectIdentifier: DispatchWorkItem] = [:]
    private var delivered = Set<String>()
    private var generation = 0
    func start() {
        stop(); onStatus?(nil)
        browser.delegate = self
        browser.searchForServices(ofType: "_zgtav._tcp.", inDomain: "local.")
    }
    func stop() {
        generation += 1; browser.stop()
        for work in retries.values { work.cancel() }; retries.removeAll()
        for service in services { service.stop(); service.delegate = nil }
        services.removeAll(); attempts.removeAll(); delivered.removeAll()
    }
    func netServiceBrowser(_ browser: NetServiceBrowser, didFind service: NetService, moreComing: Bool) {
        guard services.count < 8, !services.contains(where: { $0.name == service.name && $0.domain == service.domain }) else { return }
        services.append(service); service.delegate = self; resolve(service)
    }
    private func resolve(_ service: NetService) {
        let key = ObjectIdentifier(service)
        attempts[key, default: 0] += 1
        service.resolve(withTimeout: 5)
    }
    func netServiceBrowser(_ browser: NetServiceBrowser, didRemove service: NetService, moreComing: Bool) {
        guard let existing = services.first(where: { $0.name == service.name && $0.domain == service.domain }) else { return }
        let key = ObjectIdentifier(existing)
        retries.removeValue(forKey: key)?.cancel(); attempts.removeValue(forKey: key)
        existing.stop(); existing.delegate = nil; services.removeAll { $0 === existing }
    }
    func netServiceBrowser(_ browser: NetServiceBrowser, didNotSearch errorDict: [String: NSNumber]) {
        NSLog("ZGTA V LAN discovery browse failed: %@", errorDict)
        onStatus?("Nearby search could not start. Allow Local Network access for ZGTA V in iOS Settings, then Refresh. You can also join with an invite.")
    }
    func netService(_ sender: NetService, didNotResolve errorDict: [String: NSNumber]) {
        guard services.contains(where: { $0 === sender }) else { return }
        NSLog("ZGTA V LAN discovery resolve failed: %@", errorDict)
        let key = ObjectIdentifier(sender)
        guard attempts[key, default: 0] < 2 else {
            if delivered.isEmpty { onStatus?("A nearby host was found but its address could not be resolved. Refresh, or use its invite.") }; return
        }
        let attempt = generation
        let work = DispatchWorkItem { [weak self, weak sender] in
            guard let self, let sender, self.generation == attempt, self.services.contains(where: { $0 === sender }) else { return }
            self.retries.removeValue(forKey: key); self.resolve(sender)
        }
        retries[key] = work; DispatchQueue.main.asyncAfter(deadline: .now() + 0.5, execute: work)
    }
    func netServiceDidResolveAddress(_ sender: NetService) {
        guard services.contains(where: { $0 === sender }), (1...65535).contains(sender.port) else { return }
        for data in sender.addresses ?? [] {
            let host: String? = data.withUnsafeBytes { raw in
                guard let pointer = raw.baseAddress, raw.count >= MemoryLayout<sockaddr_in>.size else { return nil }
                let address = pointer.assumingMemoryBound(to: sockaddr.self)
                guard address.pointee.sa_family == AF_INET else { return nil }
                var name = [CChar](repeating: 0, count: Int(NI_MAXHOST))
                guard getnameinfo(address, socklen_t(raw.count), &name, socklen_t(name.count), nil, 0, NI_NUMERICHOST) == 0 else { return nil }
                return String(cString: name)
            }
            if let host, !host.hasPrefix("127."), let record = LobbyRecord.parse("ws://\(host):\(sender.port)/engine-lan"), record.connection == .lan, delivered.insert(record.relay).inserted {
                onStatus?(nil); found?(record.relay)
            }
        }
    }
    deinit { browser.stop(); for work in retries.values { work.cancel() }; for service in services { service.stop() } }
}
