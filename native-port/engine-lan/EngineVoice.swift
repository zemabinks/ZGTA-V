import Foundation
import ZemaLanBackend

/// The existing controls select the active backend; no second multiplayer UI.
enum EngineVoice {
    static func isMicEnabled() -> Bool { ZemaLabEnabled() != 0 ? ZemaVoiceIsMicEnabled() : MugoatVoiceIsMicEnabled() }
    static func isSpeakerEnabled() -> Bool { ZemaLabEnabled() != 0 ? ZemaVoiceIsSpeakerEnabled() : MugoatVoiceIsSpeakerEnabled() }
    static func setMicEnabled(_ value: Bool) {
        if ZemaLabEnabled() != 0 { ZemaVoiceSetMicEnabled(value) } else { MugoatVoiceSetMicEnabled(value) }
    }
    static func setSpeakerEnabled(_ value: Bool) {
        if ZemaLabEnabled() != 0 { ZemaVoiceSetSpeakerEnabled(value) } else { MugoatVoiceSetSpeakerEnabled(value) }
    }
    static func submit(_ samples: UnsafePointer<Float>, _ count: UInt32) {
        if ZemaLabEnabled() != 0 { ZemaVoiceSubmitMicAudio(samples, count) } else { MugoatVoiceSubmitMicAudio(samples, count) }
    }
    static var diagnosticSummary: String {
        let voice = ZemaVoiceReadStats()
        return "[Voice] sent=\(voice.sent) received=\(voice.received) mixed_frames=\(voice.mixed) dropped=\(voice.dropped) position_updates=\(voice.positionUpdates) mic=\(isMicEnabled()) speaker=\(isSpeakerEnabled())"
    }
}
