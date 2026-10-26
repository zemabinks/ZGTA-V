import Foundation

/// The game's file list: `{"files": [[path under data/, size, ...], ...]}`.
struct GameManifest {
    struct File { let path: String; let size: Int64 }
    let files: [File]
    let totalBytes: Int64
    private let exact: [String: Int]
    private let folded: [String: Int]

    init(url: URL) throws {
        guard let data = try? Data(contentsOf: url),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let list = json["files"] as? [[Any]] else {
            throw InstallError(.manifestUnreadable, "The app's game file list (manifest.json) is missing or damaged.", detail: url.path)
        }
        var files: [File] = []
        files.reserveCapacity(list.count)
        for entry in list {
            guard entry.count >= 2, let path = entry[0] as? String, let size = (entry[1] as? NSNumber)?.int64Value else { continue }
            // The list is app data, but never let a bad entry point outside data/.
            guard GameManifest.components(of: path) != nil else { continue }
            files.append(File(path: path, size: size))
        }
        guard !files.isEmpty else {
            throw InstallError(.manifestUnreadable, "The app's game file list (manifest.json) is empty.", detail: url.path)
        }
        self.files = files
        totalBytes = files.reduce(0) { $0 + $1.size }
        var exact: [String: Int] = [:], folded: [String: Int] = [:]
        for (i, f) in files.enumerated() { exact[f.path] = i; folded[f.path.lowercased()] = i }
        self.exact = exact
        self.folded = folded
    }

    func index(of path: String) -> Int? { exact[path] ?? folded[path.lowercased()] }

    /// Splits an archive path into safe components, or nil when it is unsafe
    /// (absolute, "..", empty, NUL). Backslashes (Windows zips) count as separators.
    static func components(of rawPath: String) -> [Substring]? {
        if rawPath.isEmpty || rawPath.contains("\0") { return nil }
        let path = rawPath.replacingOccurrences(of: "\\", with: "/")
        if path.hasPrefix("/") { return nil }
        if path.count >= 2, path.dropFirst().first == ":" { return nil } // C:\...
        var parts: [Substring] = []
        for part in path.split(separator: "/", omittingEmptySubsequences: true) {
            if part == "." { continue }
            if part == ".." { return nil }
            parts.append(part)
        }
        return parts.isEmpty ? nil : parts
    }
}

/// Maps archive entry paths onto manifest paths. The first entry that matches a manifest
/// file fixes the folder prefix (e.g. "Some Folder/GTA/data/"); after that only entries
/// under that prefix are used, so a stray second copy can't mix in.
struct GameRootMatcher {
    let manifest: GameManifest
    private(set) var prefix: [Substring]?

    init(manifest: GameManifest) { self.manifest = manifest }

    var prefixString: String { prefix.map { $0.isEmpty ? "" : $0.joined(separator: "/") + "/" } ?? "" }

    enum Match { case file(Int), notGame, unsafe }

    mutating func match(_ rawPath: String) -> Match {
        guard let parts = GameManifest.components(of: rawPath) else { return .unsafe }
        if let prefix {
            guard parts.count > prefix.count else { return .notGame }
            for (a, b) in zip(prefix, parts) where a.lowercased() != b.lowercased() { return .notGame }
            let rest = parts[prefix.count...].joined(separator: "/")
            return manifest.index(of: rest).map { .file($0) } ?? .notGame
        }
        for start in 0..<parts.count {
            // macOS zips carry "__MACOSX/..." resource-fork copies: never a game root.
            if parts[..<start].contains(where: { $0 == "__MACOSX" }) { break }
            let rest = parts[start...].joined(separator: "/")
            if let i = manifest.index(of: rest) {
                prefix = Array(parts[..<start])
                return .file(i)
            }
        }
        return .notGame
    }
}
