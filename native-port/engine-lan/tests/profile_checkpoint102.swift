import Foundation
import Darwin
import ZemaLanBackend

private func writeStat(_ value: UInt64) {
    let key = Array("hdeadbeef".utf8)
    var bits = value
    precondition(key.withUnsafeBufferPointer { key in
        withUnsafeBytes(of: &bits) { ZemaProfileWrite(key.baseAddress, key.count, $0.bindMemory(to: UInt8.self).baseAddress, 8) }
    } == 1)
}
private func storedStat(_ bytes: Data) -> UInt64 {
    let key = Array("hdeadbeef".utf8)
    precondition(bytes.withUnsafeBytes { ZemaProfileImport($0.bindMemory(to: UInt8.self).baseAddress, $0.count) } == 1)
    return key.withUnsafeBufferPointer { ZemaProfileStat($0.baseAddress, $0.count) }
}
private final class State: @unchecked Sendable {
    let lock = NSLock()
    var writes = 0, active = 0, maximum = 0, errors = 0, recoveries = 0
    var fail = false, mutateDuringSync = false
    func perform(_ action: () throws -> Void) throws {
        lock.lock(); writes += 1; active += 1; maximum = max(maximum, active)
        let refuse = fail; lock.unlock()
        defer { lock.lock(); active -= 1; lock.unlock() }
        if refuse { throw NSError(domain: "checkpoint-fixture", code: 5) }
        try action()
    }
    func sync(_ fd: Int32) -> Int32 {
        let result = Darwin.fsync(fd)
        lock.lock(); let mutate = mutateDuringSync; mutateDuringSync = false; lock.unlock()
        if mutate { writeStat(222) }
        return result
    }
    func error(_ value: Error?) { lock.lock(); if value != nil { errors += 1 } else { recoveries += 1 }; lock.unlock() }
    func counts() -> (Int, Int, Int) { lock.lock(); defer { lock.unlock() }; return (writes, maximum, errors) }
}

@main struct Fixture {
    static func main() throws {
        let mode = CommandLine.arguments[1], folder = URL(fileURLWithPath: CommandLine.arguments[2])
        let state = State()
        let file = try EngineLanProfileFile(directory: folder, directorySync: { state.sync($0) })
        if mode == "verify" {
            let bytes = try Data(contentsOf: folder.appendingPathComponent("profile.zemapf"))
            let expected = UInt64(CommandLine.arguments[3])!
            precondition(storedStat(bytes) == expected)
            print("DISK_RELOAD_STAT_\(expected)_PASS"); return
        }
        let loaded = try file.load(); precondition(!loaded)
        let name = Array("Audit102".utf8)
        precondition(name.withUnsafeBufferPointer { ZemaProfileConfigure(123456, $0.baseAddress, $0.count) } == 1)
        try file.commit()
        let original = try Data(contentsOf: folder.appendingPathComponent("profile.zemapf"))
        let helper = EngineLanProfileCheckpoint(revision: { ZemaProfileRevision() }, commit: {
            try state.perform { try file.commit() }
        }, report: { state.error($0) })
        let drain = {
            let done = DispatchSemaphore(value: 0)
            helper.requestCheckpoint { done.signal() }
            precondition(done.wait(timeout: .now() + 5) == .success)
        }
        switch mode {
        case "baseline-gap":
            writeStat(111)
            Thread.sleep(forTimeInterval: 1.1)
            let actual = try Data(contentsOf: folder.appendingPathComponent("profile.zemapf")); precondition(actual == original)
            precondition(ZemaProfileRevision() > 0)
            print("PREVIOUS_NATIVE_DIRTY_STAT_NOT_DURABLE_WITHOUT_CLOUD_UPLOAD_REPRODUCED")
        case "timer":
            helper.start(); helper.start(); writeStat(111)
            Thread.sleep(forTimeInterval: 1.3); drain()
            precondition(state.counts().0 == 1)
            print("PERIODIC_DIRTY_SAVE_AND_DUPLICATE_START_GUARD_PASS")
        case "stop":
            helper.start(); helper.stop(); writeStat(111)
            Thread.sleep(forTimeInterval: 1.3); precondition(state.counts().0 == 0)
            helper.start(); Thread.sleep(forTimeInterval: 1.3); drain()
            precondition(state.counts().0 == 1)
            print("OFFLINE_TIMER_STOP_AND_LAN_RESTART_PASS")
        case "failure":
            state.fail = true; writeStat(111); drain()
            let actual = try Data(contentsOf: folder.appendingPathComponent("profile.zemapf")); precondition(actual == original)
            precondition(state.counts().0 == 1 && state.counts().2 == 1)
            drain(); precondition(state.counts().0 == 2 && state.counts().2 == 1)
            state.fail = false; drain(); precondition(state.counts().0 == 3 && state.recoveries == 1)
            drain(); precondition(state.counts().0 == 3)
            print("FAILED_WRITE_RETAINS_DIRTY_REVISION_AND_RETRIES_PASS")
        case "revision-race":
            writeStat(111); state.mutateDuringSync = true; drain()
            precondition(state.counts().0 == 1)
            drain(); precondition(state.counts().0 == 2)
            drain(); precondition(state.counts().0 == 2)
            print("MUTATION_DURING_EXPORT_IS_NOT_FALSELY_ACKNOWLEDGED_PASS")
        case "rename":
            try helper.withCommitLane { try file.rename(to: "Renamed") }
            drain(); writeStat(111); drain()
            var bytes = [UInt8](repeating: 0, count: 17)
            let count = bytes.withUnsafeMutableBufferPointer { ZemaProfileName($0.baseAddress, $0.count) }
            precondition(String(decoding: bytes.prefix(Int(count)), as: UTF8.self) == "Renamed")
            print("INITIAL_AND_SUBSEQUENT_RENAME_SHARE_DURABLE_COMMIT_LANE_PASS")
        case "serialization":
            writeStat(111)
            let group = DispatchGroup()
            for _ in 0..<24 { group.enter(); DispatchQueue.global().async { try! helper.commitNow(); group.leave() } }
            precondition(group.wait(timeout: .now() + 10) == .success)
            drain(); precondition(state.counts().0 == 24 && state.counts().1 == 1)
            print("CLOUD_AND_PERIODIC_COMMITS_NEVER_OVERLAP_PASS")
        case "async":
            writeStat(111)
            let blocked = DispatchSemaphore(value: 0), release = DispatchSemaphore(value: 0), done = DispatchSemaphore(value: 0)
            let slow = EngineLanProfileCheckpoint(revision: { ZemaProfileRevision() }, commit: {
                blocked.signal(); precondition(release.wait(timeout: .now() + 5) == .success); try file.commit()
            })
            writeStat(222)
            slow.requestCheckpoint { done.signal() }
            precondition(blocked.wait(timeout: .now() + 5) == .success)
            // The caller still executes while disk work is held on its own queue.
            release.signal(); precondition(done.wait(timeout: .now() + 5) == .success)
            print("LIFECYCLE_CHECKPOINT_NEVER_BLOCKS_CALLER_PASS")
        default: fatalError("Unknown fixture mode")
        }
    }
}
