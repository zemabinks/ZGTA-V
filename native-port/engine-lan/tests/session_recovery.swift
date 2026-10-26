import Foundation
import ZemaLanFixture

final class Probe: @unchecked Sendable {
    private let lock=NSLock()
    private var count=0
    private var done=false
    func joined() -> Int { lock.lock(); defer {lock.unlock()};count+=1;return count }
    func finish(){lock.lock();done=true;lock.unlock()}
    func finished()->Bool{lock.lock();defer{lock.unlock()};return done}
}
@main struct SessionRecovery {
    static func main(){
        let endpoint=CommandLine.arguments[1],mode=CommandLine.arguments[2],probe=Probe()
        let connection=EngineLanSession(backend:.native)
        connection.status={text in
            if text.hasPrefix("Engine-LAN transport connected") {
                if probe.joined()==2 { print("NATIVE_SAME_SESSION_RESUME_PASS");probe.finish() }
            }else if mode=="invalid" && text.contains("message was invalid") {
                print("NATIVE_INVALID_MESSAGE_REPORTED_PASS");probe.finish()
            }else if mode=="resume" && text.contains("disconnected") {
                connection.connect(endpoint:endpoint,room:"audit",name:"NativeAudit")
            }
        }
        connection.connect(endpoint:endpoint,room:"audit",name:"NativeAudit")
        let end=Date().addingTimeInterval(12)
        while !probe.finished() && Date()<end { RunLoop.current.run(until:Date().addingTimeInterval(0.01)) }
        connection.disconnect()
        if !probe.finished(){exit(3)}
    }
}
