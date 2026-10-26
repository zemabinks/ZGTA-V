import Foundation

// This harness never inflates an archive. Keep its C dependency unavailable.
func gi_inflate_raw(_ input: UnsafeRawPointer?, _ size: UInt32, _ output: UnsafeMutableRawPointer?, _ capacity: UInt32) -> Int32 {
    preconditionFailure("The localization harness must not call the inflater")
}

@main struct EnglishModErrorTests {
    static func main() throws {
        let catalog = try JSONDecoder().decode([String: [String: String]].self,
            from: Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1])))
        let model = "Đang triệu hồi-100%@"
        let error = ModError("Duplicate DLC package %@. Enable only one version.", model)
        precondition(error.message.hasPrefix("Duplicate "), "retain classification used by ModRuntime")
        precondition(error.message.contains(model), "retain exact model in diagnostic")
        precondition(error.localizedMessage(language: "en", catalog: catalog) == "Duplicate DLC package \(model). Enable only one version.")
        precondition(error.localizedMessage(language: "vi", catalog: catalog) == error.message)
        let raw = ModError("private filename: 100%@.zip")
        precondition(raw.localizedMessage(language: "en", catalog: catalog) == raw.message, "never treat untrusted raw filenames as format templates")
        let staticError = ModError("RPF data is truncated.")
        precondition(staticError.localizedMessage(language: "en", catalog: catalog) == "RPF data is truncated.")
        print("PASS: 6 mod-error localization checks; original classification and user data retained.")
    }
}
