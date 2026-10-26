import Foundation
import Darwin
import ZemaLanBackend

@main struct ProfileRenameFixture {
    static func snapshot() -> Data {
        let required = -Int(ZemaProfileExport(nil, 0)); precondition(required > 0)
        var data = Data(count: required)
        let n = data.withUnsafeMutableBytes { ZemaProfileExport($0.bindMemory(to: UInt8.self).baseAddress, $0.count) }
        precondition(n == required); return data
    }
    static func name() -> String {
        var bytes = [UInt8](repeating: 0, count: 17)
        let count = bytes.withUnsafeMutableBufferPointer { ZemaProfileName($0.baseAddress, $0.count) }
        precondition(count > 0); return String(decoding: bytes.prefix(Int(count)), as: UTF8.self)
    }
    static func main() throws {
        let folder = URL(fileURLWithPath: CommandLine.arguments[1]), mode = CommandLine.arguments[2]
        let current = folder.appendingPathComponent("profile.zemapf"), previous = folder.appendingPathComponent("profile.previous.zemapf")
        var syncs = 0
        let file = try EngineLanProfileFile(directory: folder, directorySync: { fd in
            syncs += 1
            if mode == "sync-failure" && syncs == 2 { return -1 }
            if mode == "external-during-sync" && syncs == 2 {
                try! Data("external-writer".utf8).write(to: current)
                return -1
            }
            return Darwin.fsync(fd)
        })
        let loaded = try file.load()
        if mode == "reload" {
            precondition(loaded && name() == "New Name" && ZemaProfileId() == 123456)
            let old = try! Data(contentsOf: previous)
            let now = snapshot(); precondition(now == (try! Data(contentsOf: current)) && now != old)
            print("RENAMED_PROFILE_DURABLE_RELOAD_PASS"); return
        }
        precondition(!loaded)
        let oldName = Array("OldName".utf8)
        precondition(oldName.withUnsafeBufferPointer { ZemaProfileConfigure(123456, $0.baseAddress, $0.count) } == 1)
        for (key, value) in [("f:GTA5/char0001.save", [UInt8]([0,255,128,0,42])), ("p2:7", [UInt8]([77,0,0,0,0,0,0,0]))] {
            let key = Array(key.utf8)
            precondition(key.withUnsafeBufferPointer { k in value.withUnsafeBufferPointer { v in ZemaProfileWrite(k.baseAddress,k.count,v.baseAddress,v.count) } } == 1)
        }
        try file.commit(); let before = snapshot()
        if mode.hasPrefix("external-before") { try Data("external-writer".utf8).write(to: current) }
        if mode == "unsafe-backup" {
            let sentinel = folder.appendingPathComponent("sentinel"); try Data("keep".utf8).write(to: sentinel)
            try FileManager.default.createSymbolicLink(at: previous, withDestinationURL: sentinel)
        }
        if mode == "post-admission" {
            precondition(ZemaLanConfigure(0x0a4d0001, 9) == 1); ZemaLanConnected(1)
            for connected in [true, false] {
                if !connected { ZemaLanConnected(0) }
                do { try file.rename(to: "New Name"); preconditionFailure("Admitted identity renamed") }
                catch EngineLanProfileFile.Failure.renameLocked {}
                precondition(snapshot() == before && name() == "OldName")
            }
            precondition(try! Data(contentsOf: current) == before)
            print("ADMITTED_AND_DISCONNECTED_RENAME_REFUSED_PASS"); return
        }
        if ["sync-failure","unsafe-backup","external-before","external-before-same","external-during-sync"].contains(mode) {
            do { try file.rename(to: mode == "external-before-same" ? "OldName" : "New Name"); preconditionFailure("Persistence failure acknowledged") }
            catch {}
            precondition(snapshot() == before && name() == "OldName" && ZemaProfileId() == 123456)
            let bytes = try! Data(contentsOf: current)
            if mode.hasPrefix("external") { precondition(bytes == Data("external-writer".utf8)) }
            else { precondition(bytes == before) }
            if mode == "sync-failure" { precondition(try! Data(contentsOf: previous) == before && syncs == 3) }
            if mode == "unsafe-backup" { precondition(try! Data(contentsOf: folder.appendingPathComponent("sentinel")) == Data("keep".utf8)) }
            print("RENAME_FAILURE_MEMORY_DISK_ROLLBACK_OR_EXTERNAL_GUARD_PASS"); return
        }
        for invalid in ["", "  ", "name\n", "12345678901234567", "é"] {
            do { try file.rename(to: invalid); preconditionFailure("Invalid name accepted") }
            catch EngineLanProfileFile.Failure.renameLocked {}
            precondition(snapshot() == before && (try! Data(contentsOf: current)) == before)
        }
        try file.rename(to: "New Name")
        precondition(name() == "New Name" && ZemaProfileId() == 123456)
        precondition(try! Data(contentsOf: previous) == before)
        let renamed = snapshot(); precondition(try! Data(contentsOf: current) == renamed)
        precondition(renamed != before)
        try file.rename(to: "New Name"); precondition(snapshot() == renamed)
        // A reversible name-only edit must reproduce every original encoded byte.
        try file.rename(to: "OldName"); precondition(snapshot() == before)
        try file.rename(to: "New Name")
        print("RENAME_IDENTITY_PROGRESS_BYTES_BACKUP_ROUNDTRIP_PASS")
    }
}
