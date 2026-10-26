import Foundation
import ZemaLanBackend

extension EngineLanSession.Backend {
    /// The same C ABI is used by the iPhone target and the disposable Mac
    /// transport harness. Configuring transport never starts/patches a game.
    static var native: Self {
        Self(configure: { ZemaLanConfigure($0, $1) == 1 },
             connected: { ZemaLanConnected($0 ? 1 : 0) },
             deliver: { data in
                 data.withUnsafeBytes { bytes in
                     _ = ZemaLanDeliver(bytes.bindMemory(to: UInt8.self).baseAddress, bytes.count)
                 }
             },
             outgoing: {
                 var bytes = [UInt8](repeating: 0, count: 2048)
                 let count = bytes.withUnsafeMutableBufferPointer { ZemaLanTakeOutgoing($0.baseAddress, $0.count) }
                 let length = Int(count)
                 guard length > 0, length <= bytes.count else { return nil }
                 return Data(bytes.prefix(length))
             })
    }
}
