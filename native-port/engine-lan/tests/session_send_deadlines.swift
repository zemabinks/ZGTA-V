// Boundary doubles for the real EngineLanSession. No sockets or app preferences.
import Foundation

final class URLSessionConfiguration {
    static var ephemeral: URLSessionConfiguration { URLSessionConfiguration() }
    var timeoutIntervalForRequest: TimeInterval = 0
}
final class URLSession {
    init(configuration: URLSessionConfiguration) {}
    func webSocketTask(with url: URL) -> URLSessionWebSocketTask { probe.newSocket() }
    func invalidateAndCancel() {}
}
final class URLSessionWebSocketTask: @unchecked Sendable {
    enum Message { case data(Data), string(String) }
    enum CloseCode { case goingAway }
    private let lock = NSLock()
    private var receiver: ((Result<Message, Error>) -> Void)?
    private var sent: [Message] = []
    private var callbacks: [(Error?) -> Void] = []
    private var closed = false
    func resume() {}
    func cancel(with: CloseCode, reason: Data?) { lock.lock(); closed = true; lock.unlock() }
    func send(_ message: Message, completionHandler: @escaping (Error?) -> Void) {
        lock.lock(); sent.append(message)
        if case .data = message { callbacks.append(completionHandler); lock.unlock() }
        else { lock.unlock(); completionHandler(nil) }
    }
    func receive(completionHandler: @escaping (Result<Message, Error>) -> Void) {
        lock.lock(); receiver = completionHandler; lock.unlock()
    }
    var receiving: Bool { lock.lock(); defer { lock.unlock() }; return receiver != nil }
    var dataCount: Int { lock.lock(); defer { lock.unlock() }; return callbacks.count }
    var isClosed: Bool { lock.lock(); defer { lock.unlock() }; return closed }
    func complete(_ index: Int, error: Error? = nil) {
        lock.lock(); let callback = callbacks[index]; lock.unlock(); callback(error)
    }
    func deliver(_ value: Result<Message, Error>) {
        lock.lock(); let callback = receiver; receiver = nil; lock.unlock()
        precondition(callback != nil); callback!(value)
    }
    func admission() {
        deliver(.success(.string("{\"type\":\"joined\",\"protocol\":\"zema-engine-lan/1\",\"build\":\"8b0b5899ed\",\"vip\":172818433,\"epoch\":\"0000000000000009\",\"resume\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}")))
    }
    func join() -> [String: Any] {
        lock.lock(); defer { lock.unlock() }
        guard case .string(let text) = sent.first else { preconditionFailure() }
        return try! JSONSerialization.jsonObject(with: Data(text.utf8)) as! [String: Any]
    }
}
final class SendProbe: @unchecked Sendable {
    private let lock = NSLock()
    private var time: TimeInterval = 0
    private var sockets: [URLSessionWebSocketTask] = []
    private var frames = 0
    private var online = false
    private var messages: [String] = []
    func clock() -> TimeInterval { lock.lock(); defer { lock.unlock() }; return time }
    func advance(_ value: TimeInterval) { lock.lock(); time = value; lock.unlock() }
    func newSocket() -> URLSessionWebSocketTask {
        lock.lock(); defer { lock.unlock() }
        let socket = URLSessionWebSocketTask(); sockets.append(socket); return socket
    }
    func latest(_ count: Int) -> URLSessionWebSocketTask? {
        lock.lock(); defer { lock.unlock() }; return sockets.count == count ? sockets.last : nil
    }
    func queue(_ count: Int) { lock.lock(); frames += count; lock.unlock() }
    func outgoing() -> Data? {
        lock.lock(); defer { lock.unlock() }; guard frames > 0 else { return nil }
        frames -= 1; return Data(repeating: 0, count: 16)
    }
    func remaining() -> Int { lock.lock(); defer { lock.unlock() }; return frames }
    func clearFrames() { lock.lock(); frames = 0; lock.unlock() }
    func connected(_ value: Bool) { lock.lock(); online = value; lock.unlock() }
    func connected() -> Bool { lock.lock(); defer { lock.unlock() }; return online }
    func status(_ text: String) { lock.lock(); messages.append(text); lock.unlock() }
    func status() -> String { lock.lock(); defer { lock.unlock() }; return messages.last ?? "" }
}
let probe = SendProbe()

@main struct SendDeadlineFixture {
    static func wait(_ label: String, _ condition: () -> Bool) {
        let end = Date().addingTimeInterval(3)
        while !condition() && Date() < end { RunLoop.current.run(until: Date().addingTimeInterval(0.005)) }
        precondition(condition(), label)
    }
    static func main() {
        let session = EngineLanSession(backend: .init(configure: { $0 == 0x0a4d0001 && $1 == 9 },
            connected: { probe.connected($0) }, deliver: { _ in }, outgoing: { probe.outgoing() }),
            uptime: { probe.clock() })
        session.status = { probe.status($0) }
        let endpoint = "ws://127.0.0.1:47540/engine-lan"
        session.connect(endpoint: endpoint, room: "test", name: "Audit")
        wait("initial receive installed") { probe.latest(1)?.receiving == true }
        let first = probe.latest(1)!
        if CommandLine.arguments[1] == "initial-error" {
            first.deliver(.failure(NSError(domain: "fixture", code: 1)))
            wait("initial failure") { first.isClosed }
            wait("initial failure message") { probe.status().contains("Could not connect to the host relay") }
            precondition(!probe.status().contains("resume"))
            print("NATIVE_INITIAL_FAILURE_EXPLAINS_RELAY_WITHOUT_RESUME_PASS"); return
        }
        first.admission(); wait("admitted") { probe.connected() }
        if CommandLine.arguments[1] == "resume-error" {
            session.disconnect(); wait("disconnected") { first.isClosed }
            session.connect(endpoint: endpoint, room: "test", name: "Audit")
            wait("resume receive installed") { probe.latest(2)?.receiving == true }
            let second = probe.latest(2)!; precondition(second.join()["resume"] as? String == String(repeating: "a", count: 32))
            second.deliver(.failure(NSError(domain: "fixture", code: 1)))
            wait("resume failure message") { probe.status().contains("Could not resume") }
            precondition(probe.status().contains("Saved characters are preserved"))
            print("NATIVE_FAILED_RESUME_RETAINS_TOKEN_AND_EXPLAINS_RECOVERY_PASS"); return
        }
        probe.queue(64); wait("bounded initial sends") { first.dataCount == 16 }
        precondition(probe.remaining() == 48, "At most 16 sends in flight")
        probe.advance(4)
        for index in (1...15).reversed() { first.complete(index) }
        wait("new traffic after out-of-order completions") { first.dataCount == 31 }
        probe.advance(4.8)
        for index in 16...30 { first.complete(index) }
        wait("newer traffic still completes") { first.dataCount == 46 }
        // The first send has never completed; new completions must not hide its age.
        probe.advance(5.1)
        wait("oldest send times out despite new traffic") { first.isClosed }
        wait("timeout reported") { probe.status().contains("send timed out") }
        precondition(!probe.connected())
        probe.clearFrames()
        session.connect(endpoint: endpoint, room: "test", name: "Audit")
        wait("reconnect receive installed") { probe.latest(2)?.receiving == true }
        let second = probe.latest(2)!; precondition(second.join()["resume"] as? String == String(repeating: "a", count: 32))
        second.admission(); wait("reconnected") { probe.connected() }
        // Late and duplicate completions from the old generation cannot close the new one.
        first.complete(0, error: NSError(domain: "late", code: 2)); first.complete(1)
        probe.queue(16); wait("new connection keeps full send capacity") { second.dataCount == 16 }
        for index in (0...15).reversed() { second.complete(index); second.complete(index) }
        probe.queue(16); wait("duplicate completions do not underflow capacity") { second.dataCount == 32 }
        precondition(probe.connected() && !second.isClosed)
        session.disconnect(); wait("explicit close") { second.isClosed }
        print("NATIVE_OLDEST_SEND_DEADLINE_CAPACITY_OUT_OF_ORDER_AND_STALE_GENERATION_PASS")
    }
}
