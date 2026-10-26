import Foundation

final class RecoveryProbe: @unchecked Sendable {
    private let lock = NSLock()
    private var count = 0
    private var sent = false
    private var retry = false
    private var vip: UInt32?
    var session: EngineLanSession!
    let mode: String
    let endpoint: String
    init(_ endpoint: String, _ mode: String) { self.endpoint = endpoint; self.mode = mode }
    func configure(_ address: UInt32, _ epoch: UInt64) -> Bool {
        lock.lock(); defer { lock.unlock() }
        precondition(vip == nil || vip == address, "A running game must retain its address")
        vip = address; count += 1
        precondition(count <= 2 && epoch != 0)
        return true
    }
    func outgoing() -> Data? {
        lock.lock(); defer { lock.unlock() }
        guard count == 2, !sent else { return nil }; sent = true
        return Data([71,53,1,3,10,77,0,1,1,2,10,77,0,2,1,2,99])
    }
    func deliver(_ frame: Data) {
        precondition(frame == Data([71,53,1,3,10,77,0,2,1,2,10,77,0,1,1,2,99]))
        print("NATIVE_REJOIN_SAME_ADDRESS_DATA_PASS"); fflush(stdout); exit(0)
    }
    func status(_ text: String) {
        lock.lock(); let shouldRetry = !retry && text.contains("disconnected"); if shouldRetry { retry = true }; lock.unlock()
        if shouldRetry { session.connect(endpoint:endpoint,room:"RECOVERY",name:"SameCharacter") }
        if mode == "occupied" && text.contains("another player") {
            lock.lock(); precondition(count == 1); lock.unlock()
            print("NATIVE_OCCUPIED_ADDRESS_PRESERVED_PASS"); fflush(stdout); exit(0)
        }
        if mode == "unsolicited" && text.contains("lobby changed") {
            lock.lock(); precondition(count == 1); lock.unlock()
            print("NATIVE_UNNEGOTIATED_EPOCH_REFUSED_PASS"); fflush(stdout); exit(0)
        }
    }
}
@main struct RecoveryFixture {
    static func main() {
        let probe = RecoveryProbe(CommandLine.arguments[1],CommandLine.arguments[2])
        #if REAL_BACKEND
        let native = EngineLanSession.Backend.native
        let session = EngineLanSession(backend:.init(configure:{native.configure($0,$1) && probe.configure($0,$1)},connected:{native.connected($0)},deliver:{probe.deliver($0)},outgoing:{probe.outgoing()}))
        #else
        let session = EngineLanSession(backend:.init(configure:{probe.configure($0,$1)},connected:{_ in},deliver:{probe.deliver($0)},outgoing:{probe.outgoing()}))
        #endif
        probe.session = session; session.status = { probe.status($0) }
        session.connect(endpoint:probe.endpoint,room:"RECOVERY",name:"SameCharacter")
        DispatchQueue.main.asyncAfter(deadline:.now()+12) { fputs("RECOVERY_TIMEOUT\n",stderr);exit(3) }
        dispatchMain()
    }
}
