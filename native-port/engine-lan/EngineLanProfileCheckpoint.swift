import Foundation

/// One commit lane for cloud uploads, dirty fallback stats and lifecycle saves.
/// Periodic/lifecycle disk work stays off UIKit. A revision captured before export
/// is the only revision acknowledged, so a concurrent mutation remains dirty.
final class EngineLanProfileCheckpoint: @unchecked Sendable {
    private let queue = DispatchQueue(label: "zema.engine-lan.profile-checkpoint", qos: .utility)
    private let queueKey = DispatchSpecificKey<UInt8>()
    private let revision: () -> UInt64
    private let write: () throws -> Void
    private let report: (Error?) -> Void
    private var savedRevision: UInt64
    private var lastFailure: String?
    private var timer: DispatchSourceTimer?

    init(revision: @escaping () -> UInt64, commit: @escaping () throws -> Void,
         report: @escaping (Error?) -> Void = { _ in }) {
        self.revision = revision; self.write = commit; self.report = report
        savedRevision = revision()
        queue.setSpecific(key: queueKey, value: 1)
    }

    func start() {
        queue.async { [self] in
            guard timer == nil else { return }
            let next = DispatchSource.makeTimerSource(queue: queue)
            next.schedule(deadline: .now() + 1, repeating: 1, leeway: .milliseconds(100))
            next.setEventHandler { [weak self] in self?.checkpoint() }
            timer = next; next.resume()
        }
    }

    func stop() {
        queue.async { [self] in timer?.cancel(); timer = nil }
    }

    /// Explicit engine cloud commits retain their synchronous success/failure
    /// acknowledgement, including the existing directory-fsync retry contract.
    func commitNow() throws {
        try withCommitLane { try commit() }
    }

    /// Pre-admission rename includes its own durable transaction and rollback.
    /// Keep it on this same lane once periodic checkpoints have been enabled.
    func withCommitLane(_ action: () throws -> Void) rethrows {
        if DispatchQueue.getSpecific(key: queueKey) != nil { try action(); return }
        try queue.sync(execute: action)
    }

    func requestCheckpoint(completion: @escaping () -> Void = {}) {
        queue.async { [self] in checkpoint(); completion() }
    }

    private func commit() throws {
        let before = revision()
        do { try write() }
        catch {
            let key = String(reflecting: type(of: error)) + ":" + error.localizedDescription
            if lastFailure != key { lastFailure = key; report(error) }
            throw error
        }
        savedRevision = before
        if lastFailure != nil { lastFailure = nil; report(nil) }
    }

    private func checkpoint() {
        guard revision() != savedRevision else { return }
        do { try commit() } catch { /* Keep dirty; retry on the next bounded tick. */ }
    }

    deinit { timer?.cancel() }
}
