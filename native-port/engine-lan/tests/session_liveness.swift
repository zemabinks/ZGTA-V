import Foundation

final class LivenessProbe: @unchecked Sendable {
    private let lock = NSLock()
    private var joined = false
    private var complete = false
    func connected(_ value: Bool) { lock.lock(); defer { lock.unlock() }; if value { joined = true } }
    func failure() { lock.lock(); defer { lock.unlock() }; if joined { complete = true } }
    func finished() -> Bool { lock.lock(); defer { lock.unlock() }; return complete }
}

@main struct SessionLiveness {
    static func main() {
        let probe = LivenessProbe()
        let session = EngineLanSession(backend: .init(configure: { $0 == 0x0a4d0001 && $1 == 9 },
            connected: { probe.connected($0) }, deliver: { _ in }, outgoing: { nil }))
        session.status = { text in
            if text.contains("stopped responding") { probe.failure() }
        }
        let start = Date()
        session.connect(endpoint: CommandLine.arguments[1], room: "liveness", name: "Audit")
        while !probe.finished() && Date().timeIntervalSince(start) < 35 {
            RunLoop.current.run(until: Date().addingTimeInterval(0.01))
        }
        session.disconnect()
        guard probe.finished() else { fputs("Silent relay still appears connected after 35 seconds\n", stderr); exit(3) }
        print("NATIVE_SILENT_RELAY_DISCONNECTED_PASS \(Date().timeIntervalSince(start))")
    }
}
