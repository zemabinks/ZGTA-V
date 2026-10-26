import Foundation
import ZemaLanBackend

@main struct ProfileDirectoryFixture {
    static func main() {
        do { try run() }
        catch { print("PROFILE_DIRECTORY_REFUSED \(error)"); exit(2) }
    }
    static func run() throws {
        let mode = CommandLine.arguments[2]
        let documents = mode == "nonfile" ? URL(string: "https://example.invalid/")!
            : URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
        if mode == "legacy" {
            let old = documents.resolvingSymlinksInPath()
                .appendingPathComponent("zema-engine-lan-profile-v1", isDirectory: true)
            do { _ = try EngineLanProfileFile(directory: old); fatalError("Expected the reproduced system alias refusal") }
            catch EngineLanProfileFile.Failure.symlink { print("LEGACY_SYSTEM_ALIAS_REFUSAL_REPRODUCED"); return }
        }
        let directory = try EngineLanProfileFile.profileDirectory(inAppDocuments: documents)
        let file = try EngineLanProfileFile(directory: directory)
        let loaded = try file.load()
        if mode == "resume" { precondition(loaded) }
        else {
            precondition(!loaded)
            let name = Array("zema".utf8)
            precondition(name.withUnsafeBufferPointer { ZemaProfileConfigure(123456,$0.baseAddress,$0.count) } == 1)
        }
        try file.commit()
        print("CANONICAL_APP_DOCUMENTS_PROFILE_\(loaded ? "RESUME" : "SAVE")_PASS")
    }
}
