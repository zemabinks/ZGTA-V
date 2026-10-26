import Foundation

/// Matches the browser's bounded, time-weighted presented-FPS sampler.
final class PerformanceRun {
    enum State: String { case idle, running, cancelled, complete }
    struct Metric: Encodable {
        var first: Double
        var last: Double
        var minimum: Double
        var maximum: Double
        var observations: Int = 1
        var counterReset: Bool = false
        var delta: Double? = nil
    }
    struct Snapshot: Encodable {
        let elapsedMS: Double
        let fps: Double
        let conditions: [String: Double]
    }
    struct Result: Encodable {
        let format = "zgta-performance-v2"
        let context: [String: String]
        let durationMS: Double
        let samples: Int
        let averageFPS: Double
        let medianWindowFPS: Double
        let slowestWindowFPS: Double
        let conditions: [String: Metric]
        let comparisonWarnings: [String]
        let timeline: [Snapshot]
        let note = "Presented FPS averaged over sampling windows; not a per-frame 1% low. Match position, view, weather, settings and device temperature when comparing."
    }
    private(set) var state: State = .idle
    private(set) var reason = ""
    private(set) var started: Double = 0
    private var last: Double = 0
    private var context: [String: String] = [:]
    private var samples: [(fps: Double, ms: Double)] = []
    private var conditions: [String: Metric] = [:]
    private var lastConditionTime: Double?
    private var latestGauges: [String: Double] = [:]
    private var timeline: [Snapshot] = []
    private(set) var measurementMS: Double = 30000
    var endsAt: Double { started + 2000 + measurementMS }
    private static let counters: Set<String> = ["resourceBytesReleased", "resourceBytesReused", "resourceReclaimFailures", "memoryBudgetClamps"]
    private static let gauges: Set<String> = ["appFootprintBytes", "availableMemoryBytes", "thermalState", "thermalScale", "requestedRenderWidth", "requestedRenderHeight", "canvasWidth", "canvasHeight", "requestedFrameInterval", "secondsSinceWorldReady"]
    private(set) var result: Result?
    func start(now: Double, context: [String: String] = [:], durationSeconds: Int = 30) {
        guard now.isFinite, [30, 180].contains(durationSeconds) else { return }
        measurementMS = Double(durationSeconds) * 1000
        state = .running; started = now; last = now; self.context = context
        samples = []; conditions = [:]; latestGauges = [:]; timeline = []; lastConditionTime = nil; result = nil; reason = ""
    }
    func cancel(_ message: String = "Measurement cancelled.") {
        guard state == .running else { return }
        state = .cancelled; reason = message; result = nil
    }
    func tick(now: Double) {
        if state == .running && (!now.isFinite || now < last || now - last > 1500) {
            cancel("Frame samples stopped. Start another measurement.")
        }
    }
    /// Called only by an explicit check, at most once per second during its measured window.
    func wantsConditions(now: Double) -> Bool {
        state == .running && now.isFinite && now >= started + 2000 && now <= endsAt &&
            (lastConditionTime.map { now - $0 >= 1000 } ?? true)
    }
    func observeConditions(_ values: [String: Double], now: Double) {
        guard wantsConditions(now: now) else { return }
        lastConditionTime = now
        for (name, value) in values where Self.counters.contains(name) || Self.gauges.contains(name) {
            guard value.isFinite && value >= 0 else { continue }
            if Self.gauges.contains(name) { latestGauges[name] = value }
            if var metric = conditions[name] {
                metric.counterReset = metric.counterReset || (Self.counters.contains(name) && value < metric.last)
                metric.last = value; metric.minimum = min(metric.minimum, value); metric.maximum = max(metric.maximum, value)
                metric.observations += 1
                metric.delta = Self.counters.contains(name) && !metric.counterReset ? value - metric.first : nil
                conditions[name] = metric
            } else {
                conditions[name] = Metric(first: value, last: value, minimum: value, maximum: value)
            }
        }
    }
    private var comparisonWarnings: [String] {
        var warnings: [String] = []
        if let heat = conditions["thermalState"], heat.maximum >= 2 { warnings.append("iOS reported serious or critical heat during this check.") }
        if let heat = conditions["thermalState"], heat.minimum != heat.maximum { warnings.append("Thermal state changed during this check.") }
        if ["requestedRenderWidth", "requestedRenderHeight", "canvasWidth", "canvasHeight"].contains(where: { conditions[$0].map { $0.minimum != $0.maximum } ?? false }) { warnings.append("Render dimensions changed during this check.") }
        if let cap = conditions["requestedFrameInterval"], cap.minimum != cap.maximum { warnings.append("Requested engine frame limit changed during this check.") }
        if conditions.values.contains(where: { $0.counterReset }) { warnings.append("A cumulative counter reset; its delta is unavailable.") }
        if conditions.isEmpty { warnings.append("Run conditions were unavailable.") }
        return warnings
    }
    func sample(fps: Double, now: Double) {
        guard state == .running else { return }
        tick(now: now); guard state == .running else { return }
        guard fps.isFinite && fps >= 0 && fps <= 1000 else { cancel("Invalid frame sample."); return }
        let previous = last; last = now
        let begin = started + 2000, end = endsAt
        let weight = max(0, min(now, end) - max(previous, begin))
        if weight > 0 { samples.append((fps, weight)) }
        if weight > 0, timeline.last.map({ min(now, end) - begin - $0.elapsedMS >= 1000 }) ?? true {
            timeline.append(Snapshot(elapsedMS: min(now, end) - begin, fps: fps, conditions: latestGauges))
        }
        guard samples.count <= Int(measurementMS / 1000) * 6 else { cancel("Too many frame samples."); return }
        if now >= end {
            let duration = samples.reduce(0) { $0 + $1.ms }
            guard duration >= measurementMS - 500 && samples.count >= Int(measurementMS / 1500) else { cancel("Not enough fresh frame samples."); return }
            let sorted = samples.map(\.fps).sorted()
            result = Result(context: context, durationMS: duration, samples: samples.count,
                            averageFPS: samples.reduce(0) { $0 + $1.fps * $1.ms } / duration,
                            medianWindowFPS: sorted[sorted.count / 2], slowestWindowFPS: sorted[0],
                            conditions: conditions, comparisonWarnings: comparisonWarnings, timeline: timeline)
            state = .complete
        }
    }
}
