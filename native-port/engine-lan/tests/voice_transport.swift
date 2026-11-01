import Foundation
import ZemaLanBackend

// Explicit synthetic PCM only. No microphone, game, device or existing lobby.
@main struct VoiceTransport {
    static func main() {
        let session = EngineLanSession(backend: .native)
        let samples = [Float](repeating: 0.3, count: 960)
        var ticks = 0, heard = false
        let timer = DispatchSource.makeTimerSource(queue: .main)
        session.status = { text in print(text); fflush(stdout) }
        session.connect(endpoint: CommandLine.arguments[1], room: "VOICE108", name: "NativeVoice")
        timer.schedule(deadline: .now(), repeating: .milliseconds(20))
        timer.setEventHandler {
            ticks += 1
            if ZemaLanTransportReady() == 1 {
                ZemaVoiceSetPosition(100,100,20,true)
                if !ZemaVoiceIsMicEnabled() { ZemaVoiceSetMicEnabled(true) }
                samples.withUnsafeBufferPointer { ZemaVoiceSubmitMicAudio($0.baseAddress, 960) }
                var left = [Float](repeating: 0, count: 960), right = left
                ZemaVoiceMixAudio(&left,&right,960)
                if left.reduce(0,+)/960 > 0.2 { heard = true }
                let stats = ZemaVoiceReadStats()
                if ticks > 75, heard, stats.received >= 2, stats.sent >= 2 {
                    print("NATIVE_VOICE_WEBSOCKET_PASS sent=\(stats.sent) received=\(stats.received) mixed=\(stats.mixed)")
                    fflush(stdout);session.disconnect();exit(0)
                }
            }
            if ticks > 400 { print("VOICE_TIMEOUT");fflush(stdout);exit(1) }
        }
        timer.resume();dispatchMain()
    }
}
