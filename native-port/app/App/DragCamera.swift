import Foundation
import CoreGraphics

/// Muguet-style relative dragging. Each finger has its own dead zone; the
/// camera receives movement once, without a second floating joystick.
struct DragCamera {
    private struct Finger { var start: CGPoint; var last: CGPoint; var active = false }
    private var fingers: [ObjectIdentifier: Finger] = [:]
    private var pending = CGPoint.zero

    mutating func begin(_ id: ObjectIdentifier, at point: CGPoint) {
        fingers[id] = Finger(start: point, last: point)
    }
    mutating func move(_ id: ObjectIdentifier, to point: CGPoint) {
        guard var finger = fingers[id], point.x.isFinite, point.y.isFinite else { return }
        let delta = CGPoint(x: point.x - finger.last.x, y: point.y - finger.last.y)
        finger.last = point
        if !finger.active && hypot(point.x - finger.start.x, point.y - finger.start.y) < 2.5 {
            fingers[id] = finger
            return
        }
        finger.active = true
        fingers[id] = finger
        pending.x += delta.x; pending.y += delta.y
    }
    mutating func end(_ id: ObjectIdentifier) { fingers[id] = nil }
    mutating func reset() { fingers.removeAll(); pending = .zero }

    mutating func motion(sensitivity: Double, invertedY: Bool = false) -> CGPoint {
        let delta = pending; pending = .zero
        let gain = min(max(sensitivity, 0.1), 10.0)
        return CGPoint(x: delta.x * gain, y: delta.y * gain * 0.85 * (invertedY ? -1 : 1))
    }

    /// Keep assisted aiming on pad 0. Relative finger motion becomes a pad
    /// velocity for this poll only; a resting finger always returns zero.
    mutating func velocity(elapsed: Double, sensitivity: Double, aimed: Bool) -> CGPoint {
        guard elapsed.isFinite, elapsed > 0, elapsed <= 0.05 else { pending = .zero; return .zero }
        let seconds = max(elapsed, 1.0 / 240)
        let delta = motion(sensitivity: sensitivity)
        return CGPoint(x: delta.x / seconds, y: delta.y / seconds)
    }
}
