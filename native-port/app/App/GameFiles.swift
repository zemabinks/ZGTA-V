import Foundation

/// Finding the game's files anywhere the app can see, and checking them against the game's file list.
///
/// A game folder is recognised by its layout: a `data` folder (or a folder) that holds both `x64` and
/// `common`. Every file in the game's list (the app's bundled manifest) is then checked for presence
/// and exact size, so a problem can be reported by file name with the likely cause.
enum GameFiles {
    /// One game file the check found wrong.
    struct Problem {
        enum Kind { case missing, wrongSize(actual: UInt64), inICloud }
        let path: String
        let expected: UInt64
        let kind: Kind
    }

    /// The result of checking a game folder.
    struct Report {
        let data: URL
        let fileCount: Int
        let totalBytes: UInt64
        let problems: [Problem]
        var isComplete: Bool { fileCount > 0 && problems.isEmpty }

        var missing: [Problem] { problems.filter { if case .missing = $0.kind { return true }; return false } }
        var wrongSize: [Problem] { problems.filter { if case .wrongSize = $0.kind { return true }; return false } }
        var inICloud: [Problem] { problems.filter { if case .inICloud = $0.kind { return true }; return false } }

        /// A short title and an explanation of what is wrong and what to do.
        var explanation: (title: String, message: String) {
            if fileCount == 0 { return ("Game file list unavailable", "The app could not load its required game-file list. Install the verified ZGTA V package again while keeping the app's data.") }
            if isComplete { return ("Game files OK", "All \(fileCount) game files are there and complete.") }
            var parts: [String] = []
            if !inICloud.isEmpty {
                parts.append("\(Self.count(inICloud.count, "file is", "files are")) only in iCloud, not on this iPhone (for example \(inICloud[0].path)). The game can't read them from there: move the game folder to Files › On My iPhone › ZGTA V.")
            }
            if !missing.isEmpty {
                let bytes = missing.reduce(0) { $0 + $1.expected }
                var text = "\(Self.count(missing.count, "file is", "files are")) missing (\(Self.size(bytes)) in all), for example \(Self.examples(missing))."
                if missing.count == fileCount {
                    text = "This folder has none of the game's files."
                } else {
                    text += " These files were not found in this folder. Choose the complete unpacked game folder, or install from one of the archives found below. A file check alone cannot tell whether copying stopped or a different folder was selected."
                }
                parts.append(text)
            }
            if !wrongSize.isEmpty {
                let first = wrongSize[0]
                var actual: UInt64 = 0
                if case let .wrongSize(size) = first.kind { actual = size }
                parts.append("\(Self.count(wrongSize.count, "file has", "files have")) a different size from this build's file list, for example \(first.path) (\(Self.size(actual)) instead of \(Self.size(first.expected))). Check that you selected the matching prepared game files. Keep your existing files while checking another folder or archive.")
            }
            let title = !inICloud.isEmpty ? "Game files are in iCloud" : !wrongSize.isEmpty ? "Some game file sizes differ" : "Some game files are missing"
            return (title, parts.joined(separator: "\n\n"))
        }

        /// Every problem, one per line, for the log or for sharing.
        var details: String {
            problems.map { problem in
                switch problem.kind {
                case .missing: return "missing: \(problem.path) (\(problem.expected) bytes)"
                case .inICloud: return "only in iCloud: \(problem.path)"
                case let .wrongSize(actual): return "wrong size: \(problem.path) is \(actual) bytes, expected \(problem.expected)"
                }
            }.joined(separator: "\n")
        }

        private static func count(_ n: Int, _ one: String, _ many: String) -> String { n == 1 ? "1 \(one)" : "\(n) \(many)" }
        private static func examples(_ list: [Problem]) -> String { list.prefix(2).map(\.path).joined(separator: " and ") }
        static func size(_ bytes: UInt64) -> String { ByteCountFormatter.string(fromByteCount: Int64(bytes), countStyle: .file) }
    }

    /// What a scan found: game folders (best first) and archives that may contain the game.
    struct ScanResult {
        var folders: [Report] = []
        var archives: [URL] = []
        var best: Report? { folders.first }
    }

    /// The game's file list: (path under data/, size). Read once from the app bundle.
    static let manifest: [(String, UInt64)] = {
        guard let path = EnginePaths.manifest,
              let json = try? JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: path))) as? [String: Any],
              let files = json["files"] as? [[Any]] else { return [] }
        return files.compactMap { entry in
            guard entry.count >= 2, let name = entry[0] as? String, let size = (entry[1] as? NSNumber)?.uint64Value else { return nil }
            // The developers' debug web pages: the game never reads them, and web downloads often
            // change their size slightly, so they're left out of the check.
            if name.hasPrefix("common/non_final/www/") { return nil }
            return (name, size)
        }
    }()

    /// Checks every file of the game in `data` (presence and exact size). Takes well under a second.
    static func check(_ data: URL) -> Report {
        let list = manifest
        var problems: [Problem] = []
        var total: UInt64 = 0
        let base = data.path
        for (name, expected) in list {
            total += expected
            var info = stat()
            let path = base + "/" + name
            if stat(path, &info) != 0 {
                let file = URL(fileURLWithPath: path)
                let cloud = file.deletingLastPathComponent().appendingPathComponent("." + file.lastPathComponent + ".icloud").path
                problems.append(Problem(path: name, expected: expected, kind: FileManager.default.fileExists(atPath: cloud) ? .inICloud : .missing))
            } else if UInt64(info.st_size) != expected {
                problems.append(Problem(path: name, expected: expected, kind: .wrongSize(actual: UInt64(info.st_size))))
            }
        }
        return Report(data: data, fileCount: list.count, totalBytes: total, problems: problems)
    }

    /// Looks for game folders and game archives inside `root`, up to `depth` folders down, and checks
    /// every game folder it finds. Complete folders come first, then the least broken ones.
    static func scan(_ root: URL, depth: Int = 6) -> ScanResult {
        var result = ScanResult()
        var seen = Set<String>()
        var level = [root]
        var visited = 0
        let manager = FileManager.default
        for _ in 0...depth {
            var next: [URL] = []
            for folder in level {
                visited += 1
                if visited > 4000 { break }
                if let data = gameData(at: folder), seen.insert(data.resolvingSymlinksInPath().path).inserted {
                    result.folders.append(check(data))
                    // Partial installs can sit beside a complete game or its archive.
                    // Still inspect siblings; x64/common/b are pruned below.
                }
                let children = (try? manager.contentsOfDirectory(at: folder, includingPropertiesForKeys: [.isDirectoryKey, .fileSizeKey], options: [.skipsHiddenFiles])) ?? []
                for child in children {
                    if isDirectory(child) {
                        if !skippedFolders.contains(child.lastPathComponent) && !child.lastPathComponent.hasPrefix("AssetCache-") { next.append(child) }
                    } else if isGameArchive(child) {
                        result.archives.append(child)
                    }
                }
            }
            if next.isEmpty || visited > 4000 { break }
            level = next
        }
        result.folders.sort { ($0.problems.count, $0.data.path.count) < ($1.problems.count, $1.data.path.count) }
        return result
    }

    /// The game's data folder at `folder`: the folder itself or its `data` child, holding x64 and common.
    static func gameData(at folder: URL) -> URL? {
        let data = folder.appendingPathComponent("data")
        if isData(data) { return data }
        return isData(folder) ? folder : nil
    }

    private static let skippedFolders: Set<String> = ["x64", "common", "b", "EngineFiles", "__MACOSX", "Library", "tmp", ".Trash"]

    private static func isData(_ url: URL) -> Bool {
        isDirectory(url.appendingPathComponent("x64")) && isDirectory(url.appendingPathComponent("common"))
    }
    private static func isDirectory(_ url: URL) -> Bool {
        var directory: ObjCBool = false
        return FileManager.default.fileExists(atPath: url.path, isDirectory: &directory) && directory.boolValue
    }
    /// A supported archive or the first part of a split set. Its contents are
    /// validated by the installer; size alone does not establish that it is a game.
    private static func isGameArchive(_ url: URL) -> Bool {
        let name = url.lastPathComponent.lowercased()
        guard ["zip", "rar", "tar"].contains(url.pathExtension.lowercased())
            || name.hasSuffix(".tar.gz") || name.hasSuffix(".tgz")
            || name.hasSuffix(".zip.001") else { return false }
        if let part = name.range(of: #"\.part(\d+)\.rar$"#, options: .regularExpression), Int(name[part].filter(\.isNumber)) != 1 { return false }
        let size = ((try? FileManager.default.attributesOfItem(atPath: url.resolvingSymlinksInPath().path))?[.size] as? NSNumber)?.int64Value ?? 0
        return size > 0
    }
}
