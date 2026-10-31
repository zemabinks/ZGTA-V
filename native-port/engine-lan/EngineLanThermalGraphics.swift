// Keep the startup back buffer: a live LAN reset can invalidate minimap bindings.
// Escalate immediately; restore a faster cap only after 30 seconds continuously
// below the threshold. Saved user preferences are never changed.
struct EngineLanThermalGraphics {
    // Configure the engine before loading, rather than waiting for WORLD_READY.
    // LAN back buffers cannot safely resize in play; this smaller startup size
    // stays for the session. The saved resolution and cap remain unchanged.
    static func startupLimit(frameRateCap: Int, thermalState: Int) -> Int32 {
        let chosen: Int32 = frameRateCap == 0 ? 0 : frameRateCap == 30 ? 2 : 1
        return thermalState >= 3 ? max(chosen, 3) : thermalState == 2 ? max(chosen, 2) : chosen
    }
    static func startupScale(thermalState: Int) -> Double {
        thermalState >= 3 ? 0.65 : thermalState == 2 ? 0.8 : 1
    }
    private var bootLimit: Int32 = 1
    private var lastLimit: Int32?
    private var coolingSince: Double?
    private var coolingTarget: Int32?
    private var lastTime: Double?

    mutating func begin(frameRateCap: Int, initialLimit: Int32? = nil) {
        bootLimit = frameRateCap == 0 ? 0 : frameRateCap == 30 ? 2 : 1
        lastLimit = initialLimit; coolingSince = nil; coolingTarget = nil; lastTime = nil
    }

    mutating func nextLimit(thermalState: Int, ready: Bool, now: Double) -> Int32? {
        guard ready, now.isFinite else { coolingSince = nil; coolingTarget = nil; lastTime = nil; return nil }
        // Background gaps and a backwards clock cannot count as observed cooling.
        if let lastTime, now < lastTime || now - lastTime > 2 { coolingSince = nil; coolingTarget = nil }
        lastTime = now
        let target = thermalState >= 3 ? max(bootLimit, 3) : thermalState == 2 ? max(bootLimit, 2) : bootLimit
        if let current = lastLimit, target < current {
            if coolingTarget != target { coolingTarget = target; coolingSince = now }
            guard let coolingSince, now - coolingSince >= 30 else { return nil }
        } else { coolingSince = nil; coolingTarget = nil }
        guard target != lastLimit else { return nil }
        lastLimit = target; coolingSince = nil; coolingTarget = nil
        return target
    }
}
