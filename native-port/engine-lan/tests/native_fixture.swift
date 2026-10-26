import Foundation
import ZemaLanFixture
@main struct NativeFixture {
    static func main() {
        guard CommandLine.arguments.count == 2 else { exit(2) }
        let connection = EngineLanSession(backend: .native)
        connection.status = { text in
            if text.hasPrefix("Engine-LAN transport connected") {
                guard FixtureInstall() == 1, FixtureSend() == 1 else { exit(3) }
            }
        }
        connection.connect(endpoint: CommandLine.arguments[1], room: "fixture-cross-language", name: "NativeFixture")
        let deadline = Date().addingTimeInterval(15)
        while Date() < deadline {
            if FixtureReceived() == 1 {
                connection.disconnect()
                print("NATIVE_ENGINE_LAN_REPLY_PASS")
                return
            }
            RunLoop.current.run(until: Date().addingTimeInterval(0.01))
        }
        connection.disconnect(); exit(4)
    }
}
