import Foundation
import Darwin
import ZemaLanBackend

@main struct ProfileSyncFixture {
    static func main() throws {
        let folder = URL(fileURLWithPath: CommandLine.arguments[1])
        var calls = 0
        let file = try EngineLanProfileFile(directory:folder,directorySync:{ fd in
            calls += 1
            if calls == 1 { return -1 }
            return Darwin.fsync(fd)
        })
        let loaded = try file.load(); precondition(!loaded)
        let name=Array("zema".utf8)
        precondition(name.withUnsafeBufferPointer { ZemaProfileConfigure(123456,$0.baseAddress,$0.count) } == 1)
        do { try file.commit(); preconditionFailure("Failed directory sync was acknowledged") }
        catch EngineLanProfileFile.Failure.io {}
        let target=folder.appendingPathComponent("profile.zemapf"),before=try Data(contentsOf:target)
        try file.commit()
        precondition(calls == 2)
        let after = try Data(contentsOf:target); precondition(after == before)
        print("DIRECTORY_SYNC_FAILURE_REFUSED_AND_SAME_BYTES_RETRY_PASS")
    }
}
