import Foundation
import CryptoKit

/// A reversible manifest overlay. Original installed files and saves are never written.
enum ModernMapIcons {
    static let archivePath = "x64/data/cdimages/scaleform_minimap.rpf"
    static let originalSHA = "0f51cbf88739c7ac46779acfd7ef9e181aeeb54efee55ce721194b1e90463449"
    struct Edit: Decodable { let offset: Int; let before: String; let after: String }
    struct Patch: Decodable {
        let format: String; let path: String
        let baseSha256: String; let baseBytes: Int
        let resultSha256: String; let resultBytes: Int
        let edits: [Edit]; let appendBase64: String
    }
    struct Invalid: Error { }
    static func digest(_ data: Data) -> String { SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined() }
    static func hex(_ text: String) throws -> Data {
        guard text.count == 32, text.utf8.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }) else { throw Invalid() }
        var output = Data(); var index = text.startIndex
        while index < text.endIndex {
            let end = text.index(index, offsetBy: 2)
            guard let byte = UInt8(text[index..<end], radix: 16) else { throw Invalid() }
            output.append(byte); index = end
        }
        return output
    }
    static func apply(_ original: Data, patch: Patch) throws -> Data {
        guard patch.format == "zgta-modern-map-delta-v1", patch.path == archivePath,
              patch.baseSha256 == originalSHA, original.count == patch.baseBytes,
              digest(original) == originalSHA, patch.edits.count == 1,
              patch.resultBytes > original.count, patch.resultBytes - original.count < 512 * 1024,
              let append = Data(base64Encoded: patch.appendBase64), append.count == patch.resultBytes - original.count else { throw Invalid() }
        var result = original
        for edit in patch.edits {
            let before = try hex(edit.before), after = try hex(edit.after)
            guard edit.offset >= 16, edit.offset % 16 == 0, edit.offset <= original.count - 16,
                  original.subdata(in: edit.offset..<(edit.offset + 16)) == before else { throw Invalid() }
            result.replaceSubrange(edit.offset..<(edit.offset + 16), with: after)
        }
        result.append(append)
        guard result.count == patch.resultBytes, digest(result) == patch.resultSha256 else { throw Invalid() }
        return result
    }
    static func prepare(manifest: URL, localData: URL, runtime: URL, patchURL: URL? = nil) throws -> URL {
        guard let resource = patchURL ?? Bundle.main.url(forResource: "modern-map-icons", withExtension: "json") else { throw Invalid() }
        let decoder = JSONDecoder(); decoder.keyDecodingStrategy = .convertFromSnakeCase
        let patch = try decoder.decode(Patch.self, from: Data(contentsOf: resource))
        guard var metadata = try JSONSerialization.jsonObject(with: Data(contentsOf: manifest)) as? [String: Any],
              var files = metadata["files"] as? [[Any]] else { throw Invalid() }
        var overrides = metadata["_mugoatOverrides"] as? [String: String] ?? [:]
        // A user-provided archive or a previous overlay wins unchanged.
        if overrides.keys.contains(where: { $0.lowercased() == archivePath }) { return manifest }
        let matches = files.indices.filter { (files[$0].first as? String)?.lowercased() == archivePath }
        guard matches.count == 1, let index = matches.first, files[index].count >= 2,
              let originalSize = files[index][1] as? NSNumber, originalSize.intValue == patch.baseBytes,
              let originalName = files[index][0] as? String else { throw Invalid() }
        let originalURL = localData.appendingPathComponent(archivePath)
        let values = try originalURL.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey])
        guard values.isRegularFile == true, values.isSymbolicLink != true, values.fileSize == patch.baseBytes else { throw Invalid() }
        let updated = try apply(Data(contentsOf: originalURL), patch: patch)
        let folder = runtime.appendingPathComponent("modern-map-" + patch.resultSha256)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let target = folder.appendingPathComponent("scaleform_minimap.rpf")
        try updated.write(to: target, options: .atomic)
        files[index][1] = updated.count; overrides[originalName] = target.path
        metadata["files"] = files; metadata["_mugoatOverrides"] = overrides
        metadata["_zemaModernMapIcons"] = ["sha256": patch.resultSha256]
        let output = folder.appendingPathComponent("manifest.json")
        try JSONSerialization.data(withJSONObject: metadata, options: [.sortedKeys]).write(to: output, options: .atomic)
        return output
    }
}
