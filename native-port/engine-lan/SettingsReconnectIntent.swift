#if ZGTA_NATIVE_RECOVERY_QA
import Foundation

/// One existing Settings Reconnect action; no extra game overlay or QA step panel.
/// Transport's completion must follow its validated admission, not WebSocket open.
@MainActor
final class SettingsReconnectIntent {
    static let shared = SettingsReconnectIntent()
    typealias Completion = @MainActor (Bool) -> Void
    typealias Dismissed = @MainActor () -> Void
    private var intent: UUID?

    func begin(transportReady: Bool,
               reconnectTransport: (@escaping Completion) -> Void,
               dismissSettings: @escaping (@escaping Dismissed) -> Void,
               status: @escaping (String, Bool) -> Void) {
        guard intent == nil else { return }
        let token = UUID(); intent = token
        let admitted: Completion = { [weak self] success in
            guard let self, self.intent == token else { return }
            guard success else { self.intent = nil; status("Could not reconnect to this lobby. Try Reconnect again.", true); return }
            var state = ZemaNativeRecoveryQASnapshot()
            guard ZemaNativeRecoveryQARead(&state, UInt32(MemoryLayout.size(ofValue: state))) == 1,
                  state.admission_ticket != 0 else {
                self.intent = nil; status("The lobby has not admitted this player yet. Try Reconnect again.", true); return
            }
            let ticket = state.admission_ticket, generation = state.generation
            status("Opening GTA’s Find New Session. In GTA, select Public Session, then confirm.", false)
            // UIKit completion only: no timer is treated as game/menu readiness.
            dismissSettings { [weak self] in
                guard let self, self.intent == token else { return }
                self.intent = nil
                if ZemaNativeRecoveryReconnectStart(ticket, generation) != 1 {
                    status("GTA could not start Reconnect. Close its menu, return to the world and try again.", true)
                }
            }
        }
        if transportReady { admitted(true) }
        else { status("Reconnecting to the same lobby…", false); reconnectTransport(admitted) }
    }

    /// Invoke on background, offline launch, another connection attempt or explicit cancellation.
    func invalidate() {
        intent = nil
        ZemaNativeRecoveryReconnectCancel() // enqueues cancellation; owned release remains engine-thread only
    }

    func statusText() -> String? {
        var state = ZemaNativeReconnectSnapshot()
        guard ZemaNativeRecoveryReconnectRead(&state, UInt32(MemoryLayout.size(ofValue: state))) == 1 else { return nil }
        if (1...9).contains(state.step) { return "Opening GTA’s Find New Session…" }
        if state.step == 10 { return "In GTA, select Public Session and confirm the session change." }
        if state.step == 11 { return "GTA Reconnect stopped. Close its menu, return to the world and try again." }
        return nil
    }
}
#endif
