import Foundation

@main struct ModChangeQueueTests {
    static func main() throws {
        let fm = FileManager.default
        let temp = fm.temporaryDirectory.appendingPathComponent("ZemaModQueue-" + UUID().uuidString)
        try fm.createDirectory(at: temp, withIntermediateDirectories: true)
        defer { try? fm.removeItem(at: temp) }
        func file(_ name: String, _ content: String = "original") throws -> URL {
            let path = temp.appendingPathComponent(name)
            try fm.createDirectory(at: path.deletingLastPathComponent(), withIntermediateDirectories: true)
            try Data(content.utf8).write(to: path)
            return path
        }
        func entry(_ root: URL, _ name: String) -> ModFiles.Entry {
            ModFiles.scan(root).first { $0.name == name }!
        }
        func check(_ value: Bool, _ message: String = "") { precondition(value, message) }
        func rejects(_ action: () throws -> Void) {
            do { try action(); preconditionFailure("Expected an error") } catch {}
        }
        let root = temp.appendingPathComponent("mods"), queue = ModChangeQueue(directory: root)
        let pack = try file("mods/car/dlc.rpf")
        try queue.queue(.disable, for: entry(root, "car/dlc.rpf"))
        precondition(fm.fileExists(atPath: pack.path), "A running engine must retain its file")
        check(try Data(contentsOf: pack) == Data("original".utf8))
        check(try queue.pending(for: entry(root, "car/dlc.rpf")) == .disable)
        try ModChangeQueue(directory: root).applyBeforeLaunch()
        precondition(!fm.fileExists(atPath: pack.path))
        precondition(fm.fileExists(atPath: pack.appendingPathExtension("disabled").path))
        try queue.queue(.enable, for: entry(root, "car/dlc.rpf.disabled"))
        try queue.applyBeforeLaunch()
        precondition(fm.fileExists(atPath: pack.path))
        try queue.queue(.remove, for: entry(root, "car/dlc.rpf"))
        try queue.cancel(for: entry(root, "car/dlc.rpf"))
        try queue.applyBeforeLaunch()
        precondition(fm.fileExists(atPath: pack.path), "Cancel must preserve the file")
        try queue.queue(.remove, for: entry(root, "car/dlc.rpf"))
        try queue.applyBeforeLaunch()
        precondition(!fm.fileExists(atPath: pack.path))

        let changed = try file("mods/change.rpf")
        try queue.queue(.remove, for: entry(root, "change.rpf"))
        try Data("replaced content".utf8).write(to: changed)
        rejects { try queue.applyBeforeLaunch() }
        check(try Data(contentsOf: changed) == Data("replaced content".utf8))
        check(try queue.pending(for: entry(root, "change.rpf")) == .remove, "A failed request must survive")
        try queue.cancel(for: entry(root, "change.rpf"))

        let conflict = try file("mods/conflict.rpf")
        let disabled = try file("mods/conflict.rpf.disabled", "other")
        try queue.queue(.disable, for: entry(root, "conflict.rpf"))
        rejects { try queue.applyBeforeLaunch() }
        check(try Data(contentsOf: conflict) == Data("original".utf8))
        check(try Data(contentsOf: disabled) == Data("other".utf8))
        try queue.cancel(for: entry(root, "conflict.rpf"))

        let outside = try file("outside.rpf")
        let linked = root.appendingPathComponent("linked")
        try fm.createSymbolicLink(at: linked, withDestinationURL: temp)
        let fake = ModFiles.Entry(name: "linked/outside.rpf", url: linked.appendingPathComponent("outside.rpf"), size: 8, modified: Date(), isEnabled: true)
        rejects { try queue.queue(.remove, for: fake) }
        let escaping = ModFiles.Entry(name: "../outside.rpf", url: outside, size: 8, modified: Date(), isEnabled: true)
        rejects { try queue.queue(.remove, for: escaping) }
        precondition(fm.fileExists(atPath: outside.path))

        let journal = root.appendingPathComponent(".pending-changes.json")
        let valid = try Data(contentsOf: journal)
        let corrupt = Data("not a journal".utf8)
        try corrupt.write(to: journal)
        rejects { try queue.applyBeforeLaunch() }
        check(try Data(contentsOf: journal) == corrupt, "Unreadable state must not be overwritten")
        try queue.cancelAll()
        try queue.applyBeforeLaunch()
        check(try fm.contentsOfDirectory(atPath: root.path).contains { $0.hasPrefix(".pending-changes-saved-") })
        try valid.write(to: journal)
        // Simulate a completed rename followed by a failed journal write.
        let resumed = try file("mods/retry.rpf")
        try queue.queue(.disable, for: entry(root, "retry.rpf"))
        try fm.moveItem(at: resumed, to: resumed.appendingPathExtension("disabled"))
        try queue.applyBeforeLaunch()
        check(try queue.pending(for: entry(root, "retry.rpf.disabled")) == nil)
        print("MOD_CHANGE_QUEUE_DEFER_CANCEL_CONFLICT_SYMLINK_CORRUPTION_AND_RETRY_PASS")
    }
}
