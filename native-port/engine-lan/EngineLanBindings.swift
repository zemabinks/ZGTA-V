import Foundation
import ZemaLanBackend

extension EngineLanSession.Backend {
    /// The same C ABI is used by the iPhone target and the disposable Mac
    /// transport harness. Configuring transport never starts/patches a game.
    static var native: Self {
        Self(configure: { vip, epoch in
                 guard ZemaLanConfigure(vip, epoch) == 1 else { return false }
                 ZemaVoiceConfigure(vip); return true
             },
             connected: { value in
                 ZemaLanConnected(value ? 1 : 0); ZemaVoiceConnected(value)
                 DispatchQueue.main.async { NotificationCenter.default.post(name: Notification.Name("ZGTAEngineVoiceTransportChanged"), object: nil) }
             },
             deliver: { data in
                 data.withUnsafeBytes { bytes in
                     let pointer = bytes.bindMemory(to: UInt8.self).baseAddress
                     if !ZemaVoiceDeliver(pointer, bytes.count) { _ = ZemaLanDeliver(pointer, bytes.count) }
                 }
             },
             outgoing: {
                 var bytes = [UInt8](repeating: 0, count: 2048)
                 let count = bytes.withUnsafeMutableBufferPointer { ZemaLanTakeOutgoing($0.baseAddress, $0.count) }
                 let length = Int(count)
                 guard length > 0, length <= bytes.count else { return nil }
                 return Data(bytes.prefix(length))
             }, voiceOutgoing: {
                 var bytes = [UInt8](repeating: 0, count: Int(ZEMA_VOICE_FRAME_BYTES))
                 let count = bytes.withUnsafeMutableBufferPointer { ZemaVoiceTakeOutgoing($0.baseAddress, $0.count) }
                 return count > 0 ? Data(bytes.prefix(Int(count))) : nil
             })
    }
}
