import Foundation

/// Shared rules for importing and listing mod files. Readme files are never mods.
enum ModFiles {
    static let modExtensions: Set<String> = [
        "rpf", "meta", "asi", "lua", "cs", "xml", "ini", "dat",
        "yft", "ytd", "ydr", "ydd", "ybn", "ymap", "ytyp", "ymt", "ycd", "ypt"
    ]
    static let archiveExtensions: Set<String> = ["zip", "rar", "7z", "tar", "gz"]
    static var importExtensions: Set<String> { modExtensions.union(archiveExtensions) }

    struct Entry {
        let name: String
        let url: URL
        let size: Int64
        let modified: Date
        let isEnabled: Bool
    }

    static func scan(_ directory: URL) -> [Entry] {
        let directory = directory.resolvingSymlinksInPath().standardizedFileURL
        let keys: Set<URLResourceKey> = [.fileSizeKey, .contentModificationDateKey, .isRegularFileKey, .isDirectoryKey, .isSymbolicLinkKey]
        guard let enumerator = FileManager.default.enumerator(at: directory, includingPropertiesForKeys: Array(keys), options: [.skipsHiddenFiles]) else { return [] }
        let baseComponents = directory.pathComponents.count
        var entries: [Entry] = []
        for case let url as URL in enumerator {
            guard let values = try? url.resourceValues(forKeys: keys) else { continue }
            if values.isSymbolicLink == true || (values.isDirectory == true && url.pathExtension.lowercased() == "disabled") {
                enumerator.skipDescendants()
                continue
            }
            guard values.isRegularFile == true else { continue }
            let enabled = url.pathExtension.lowercased() != "disabled"
            let original = enabled ? url : url.deletingPathExtension()
            guard modExtensions.contains(original.pathExtension.lowercased()) else { continue }
            let name = url.standardizedFileURL.pathComponents.dropFirst(baseComponents).joined(separator: "/")
            entries.append(Entry(name: name, url: url,
                                 size: Int64(values.fileSize ?? 0), modified: values.contentModificationDate ?? .distantPast,
                                 isEnabled: enabled))
        }
        return entries.sorted { $0.modified == $1.modified ? $0.name < $1.name : $0.modified > $1.modified }
    }
}
