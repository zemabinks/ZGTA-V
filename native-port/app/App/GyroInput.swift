import CoreMotion
import UIKit

/// Optional gyro look. Phone rotation adds camera movement on top of touch,
/// for the fine corrections a thumb cannot make.
enum GyroAimMode: Int, CaseIterable {
    case off, whileAiming, always
    var title: String { [L10n.text("Off"), "While aiming", "Always on foot"][rawValue] }
}

/// Optional tilt steering for ground vehicles.
enum TiltSteerMode: Int, CaseIterable {
    case off, assist, full
    var title: String { [L10n.text("Off"), "Assist", "Tilt to steer"][rawValue] }
}

final class GyroInput {
    private let motion = CMMotionManager()
    private let queue = OperationQueue()
    private let lock = NSLock()
    // Rotation accumulated since the last poll, in radians (screen yaw, pitch).
    private var accumulated = CGVector.zero
    private var lastTimestamp: TimeInterval?
    private var orientation = UIInterfaceOrientation.landscapeRight
    private var smoothed = CGVector.zero
    private var gravity: CMAcceleration?

    var available: Bool { motion.isDeviceMotionAvailable }

    init() { queue.maxConcurrentOperationCount = 1 }

    func setRunning(_ running: Bool, orientation: UIInterfaceOrientation) {
        lock.lock(); self.orientation = orientation; lock.unlock()
        guard available else { return }
        if running, !motion.isDeviceMotionActive {
            motion.deviceMotionUpdateInterval = 1.0 / 120.0
            motion.startDeviceMotionUpdates(using: .xArbitraryZVertical, to: queue) { [weak self] sample, _ in
                if let sample { self?.integrate(sample) }
            }
        } else if !running, motion.isDeviceMotionActive {
            motion.stopDeviceMotionUpdates()
            lock.lock(); accumulated = .zero; lastTimestamp = nil; lock.unlock()
            smoothed = .zero
        }
    }

    /// Every sensor sample counts, so nothing aliases at 30 or 60 FPS.
    private func integrate(_ sample: CMDeviceMotion) {
        lock.lock(); defer { lock.unlock() }
        defer { lastTimestamp = sample.timestamp }
        guard let last = lastTimestamp else { self.gravity = sample.gravity; return }
        let dt = min(max(sample.timestamp - last, 0), 0.05)
        let rate = sample.rotationRate, gravity = sample.gravity
        self.gravity = gravity
        // Player-space yaw: rotation about the real vertical, so turning
        // your body turns the camera however the phone is tilted.
        let g = sqrt(gravity.x * gravity.x + gravity.y * gravity.y + gravity.z * gravity.z)
        let yaw = g > 0.1 ? (rate.x * gravity.x + rate.y * gravity.y + rate.z * gravity.z) / g : 0
        // Pitch: rotation about the screen's horizontal axis (the device's
        // long axis in landscape). Tilting the back upward looks up.
        let pitch = orientation == .landscapeRight ? rate.y : -rate.y
        accumulated.dx += yaw * dt
        accumulated.dy += pitch * dt
    }

    /// Average rotation rate since the last call, in radians/second (x =
    /// turn right, y = look down). Inactive polls discard motion so aiming
    /// never starts with a jump.
    func rate(active: Bool, elapsed: Double) -> CGVector {
        lock.lock(); let turned = accumulated; accumulated = .zero; lock.unlock()
        guard active, elapsed > 0 else { smoothed = .zero; return .zero }
        var r = CGVector(dx: turned.dx / elapsed, dy: turned.dy / elapsed)
        // Soft tiered smoothing: steady hands lose tremor, fast motion stays direct.
        func blend(_ speed: Double) -> Double { min(1, max(0, (speed - 0.035) / (0.14 - 0.035))) }
        let k = blend(hypot(r.dx, r.dy))
        smoothed.dx = smoothed.dx * 0.5 + r.dx * 0.5
        smoothed.dy = smoothed.dy * 0.5 + r.dy * 0.5
        r.dx = r.dx * k + smoothed.dx * (1 - k)
        r.dy = r.dy * k + smoothed.dy * (1 - k)
        // Tightening: scale tiny motion toward zero instead of cutting it off.
        func tighten(_ v: Double) -> Double { let t = 0.026; return abs(v) < t ? v * abs(v) / t : v }
        return CGVector(dx: tighten(r.dx), dy: tighten(r.dy))
    }

    /// Steering-wheel angle of the phone in radians, positive = turned right
    /// (clockwise). Nil when the phone lies too flat to tell.
    func steeringAngle() -> Double? {
        lock.lock(); let g = gravity, orientation = self.orientation; lock.unlock()
        guard let g else { return nil }
        // Gravity in screen coordinates (x right, y up) for each landscape side.
        let screenX = orientation == .landscapeRight ? -g.y : g.y
        let screenY = orientation == .landscapeRight ? g.x : -g.x
        guard hypot(screenX, screenY) > 0.3 else { return nil }
        return atan2(screenX, -screenY)
    }
}
