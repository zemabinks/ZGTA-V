import Foundation
import ZemaLanBackend
import OnlineFixture

private var file: EngineLanProfileFile?
@_cdecl("FixtureCommit") func fixtureCommit() -> Int32 {
    do { try file!.commit(); return 1 } catch { return 0 }
}
@main struct Main {
    static func main() {
        do { try run() } catch { print("PROFILE_FIXTURE_REFUSED \(error)"); exit(2) }
    }
    static func run() throws {
        file = try EngineLanProfileFile(directory: URL(fileURLWithPath: CommandLine.arguments[1]))
        let loaded = try file!.load()
        if !loaded {
            let name = Array("zema".utf8)
            precondition(name.withUnsafeBufferPointer { ZemaProfileConfigure(123456, $0.baseAddress, $0.count) } == 1)
        }
        if CommandLine.arguments.count > 2 && CommandLine.arguments[2] == "external-change" {
            let target = URL(fileURLWithPath: CommandLine.arguments[1]).appendingPathComponent("profile.zemapf")
            var changed = try Data(contentsOf: target); changed[changed.count - 1] ^= 1
            try changed.write(to: target)
            do { try file!.commit(); preconditionFailure("External change was overwritten") }
            catch EngineLanProfileFile.Failure.changed {
                let after = try Data(contentsOf: target); precondition(after == changed)
                print("EXTERNAL_CHANGE_PRESERVED_PASS"); return
            }
        }
        precondition(FixtureRun(loaded ? 1 : 0) == 0)
        if CommandLine.arguments.count > 2 && CommandLine.arguments[2] == "mutate" {
            let key = Array("hffffffff".utf8), value = [UInt8](repeating: 1, count: 8)
            precondition(key.withUnsafeBufferPointer { k in value.withUnsafeBufferPointer { v in ZemaProfileWrite(k.baseAddress,k.count,v.baseAddress,v.count) } } == 1)
        }
        try file!.commit()
        print(loaded ? "PROFILE_DISK_RESUME_PASS" : "PROFILE_DISK_SAVE_PASS")
    }
}
