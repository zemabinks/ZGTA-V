import Foundation

/// Where your own copy of the game lives on this iPhone. Two ways:
/// - In the app's own folder (Files › On My iPhone › ZGTA V): found automatically, at any
///   depth, with no picking and no permissions. Moving a folder within On My iPhone is instant.
/// - A folder picked in Files, which can be any folder above the game (even On My iPhone itself):
///   the app looks through it for the game and keeps access between launches with a bookmark.
/// Either way every game file is checked first (GameFiles), and the app reads the files directly
/// while you play, so no server is needed.
enum GameFolder {
    private static let bookmarkKey = "gameFolderBookmark"
    private static let nameKey = "gameFolderName"
    private static let subpathKey = "gameFolderSubpath" // from the picked folder (or the app folder) down to data/
    private static let inAppKey = "gameFolderInApp"
    private static let searchBookmarkKey = "zgta.game-search-folder.v1"
    private static var lastSearchRoot: URL?
    struct ArchiveCandidate {
        let url: URL
        let accessRoot: URL
        let ownedByApp: Bool
        /// Captured while the directory grant is active; never re-resolve it
        /// after access has ended just to look up that same grant.
        fileprivate let identity: String
    }
    /// "Play anyway": the folder (subpath) and how many problems the player accepted for it.
    private static let acceptedKey = "gameFolderAcceptedProblems"
    /// The last folder picked in Files that had problems, so the player can still use it.
    private static var pendingPick: (url: URL, report: GameFiles.Report)?
    private static var accessing: URL?
    /// Lines for the app's log (Settings › Share log), so a refused folder can be diagnosed.
    static var log: (String) -> Void = { _ in }
    /// The check of a game folder found in the app's folder that can't be used yet (shown on the start screen).
    static private(set) var appFolderReport: GameFiles.Report?
    static var appFolderProblem: String? { appFolderReport.map { $0.explanation.message } }
    /// Problem files in the folder in use, when the player chose Play anyway (0: all files fine).
    static private(set) var acceptedProblemCount = 0
    /// Supported game archive candidates seen by the last search.
    static private(set) var archiveCandidates: [ArchiveCandidate] = []
    static var archivesFound: [URL] { archiveCandidates.map(\.url) }

    static var isChosen: Bool { inAppFolder || UserDefaults.standard.data(forKey: bookmarkKey) != nil }
    static var inAppFolder: Bool { UserDefaults.standard.bool(forKey: inAppKey) }
    static var name: String { UserDefaults.standard.string(forKey: nameKey) ?? "folder" }
    static var appFolder: URL { FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0] }

    /// Resolve symlinks and require a path-component boundary, not a common prefix.
    static func ownsFile(_ file: URL) -> Bool {
        let root = appFolder.resolvingSymlinksInPath().standardizedFileURL.path
        return file.resolvingSymlinksInPath().standardizedFileURL.path.hasPrefix(root + "/")
    }

    static func accessRoot(for archive: URL) -> URL? {
        archiveCandidates.first { $0.url.standardizedFileURL == archive.standardizedFileURL }?.accessRoot
    }

    private static func recordArchives(_ urls: [URL], root: URL, ownedByApp: Bool = false) {
        var seen = Set<String>()
        archiveCandidates = urls.compactMap { url in
            let identity = url.resolvingSymlinksInPath().standardizedFileURL.path
            guard seen.insert(identity).inserted else { return nil }
            return ArchiveCandidate(url: url, accessRoot: root,
                                    ownedByApp: ownedByApp && ownsFile(url), identity: identity)
        }
    }

    /// Every explicit recheck searches again, including the last folder selected
    /// for an archive. Remembering a folder must not short-circuit discovery.
    @discardableResult
    static func refreshSearch() -> Bool {
        let ownFound = findInAppFolder()
        let ownArchives = archiveCandidates
        var root = lastSearchRoot
        if root == nil, let data = UserDefaults.standard.data(forKey: searchBookmarkKey)
            ?? UserDefaults.standard.data(forKey: bookmarkKey) {
            var stale = false
            root = try? URL(resolvingBookmarkData: data, options: [], relativeTo: nil, bookmarkDataIsStale: &stale)
        }
        guard let root else {
            if !ownFound { clear() }
            return ownFound
        }
        let choice = choose(root)
        let selectedArchives = Set(archiveCandidates.map(\.identity))
        archiveCandidates += ownArchives.filter { !selectedArchives.contains($0.identity) }
        if case .accepted = choice { return true }
        // A previous selection may still be valid when another search root has
        // no complete game. Validate it rather than trusting its saved bookmark.
        if let current = checkChosen() {
            let subpath = UserDefaults.standard.string(forKey: subpathKey) ?? ""
            if current.isComplete || accepted(current, subpath: subpath) { return true }
            appFolderReport = current
            clear()
        }
        if !ownFound {
            // An unreadable/moved data folder has no report at all. Its saved
            // bookmark must not keep the home screen or launcher in Ready.
            clear()
            if case let .incomplete(report) = choice { appFolderReport = report }
        }
        return ownFound
    }

    static func clear() {
        for key in [bookmarkKey, nameKey, subpathKey, inAppKey] { UserDefaults.standard.removeObject(forKey: key) }
    }

    // MARK: The app's own folder

    /// Looks for the game anywhere inside Files › On My iPhone › ZGTA V and checks every file.
    /// Returns true when a complete game was found (and remembers it). Does nothing when a picked
    /// folder is already in use. Takes about a second.
    @discardableResult
    static func findInAppFolder() -> Bool {
        let previous = appFolderReport?.explanation.message
        appFolderReport = nil
        let scan = GameFiles.scan(appFolder)
        recordArchives(scan.archives, root: appFolder, ownedByApp: true)
        if isChosen && !inAppFolder { return false }
        guard let best = scan.best else {
            if inAppFolder { log("The game folder is no longer in the app's folder."); clear() }
            return false
        }
        let subpath = relative(best.data, to: appFolder)
        guard best.isComplete || accepted(best, subpath: subpath) else {
            if previous != best.explanation.message {
                log("Game folder in the app's folder can't be used (\(subpath)): \(best.problems.count) problems")
                log(best.details.split(separator: "\n").prefix(20).joined(separator: "\n"))
            }
            appFolderReport = best
            if inAppFolder { clear() }
            return false
        }
        acceptedProblemCount = best.problems.count
        if !inAppFolder || UserDefaults.standard.string(forKey: subpathKey) != subpath {
            log("Game folder found in the app's folder: \(subpath) (\(best.isComplete ? "all \(best.fileCount) files checked" : "\(best.problems.count) problem files, played anyway"))")
        }
        UserDefaults.standard.removeObject(forKey: bookmarkKey)
        UserDefaults.standard.set(true, forKey: inAppKey)
        UserDefaults.standard.set(subpath, forKey: subpathKey)
        UserDefaults.standard.set(displayName(best.data), forKey: nameKey)
        return true
    }

    // MARK: A folder picked in Files

    /// What happened with a picked folder.
    enum Choice {
        case accepted(GameFiles.Report)
        case incomplete(GameFiles.Report)
        case archivesOnly([URL])
        case refused(String)
    }

    /// Looks through a folder picked in Files (any folder above the game, even On My iPhone itself),
    /// checks the best game folder in it and remembers it when it's complete.
    static func choose(_ picked: URL) -> Choice {
        archiveCandidates = []
        // Folders picked in Files need security-scoped access; plain paths (tests) don't.
        let scoped = picked.startAccessingSecurityScopedResource()
        defer { if scoped { picked.stopAccessingSecurityScopedResource() } }
        log("Folder picked: \(picked.path) (access granted: \(scoped), \(describeLocation(picked)))")
        guard FileManager.default.isReadableFile(atPath: picked.path) else {
            return .refused("The app was not allowed to open that folder. Move your game folder to Files › On My iPhone › ZGTA V instead; the app finds it there by itself.")
        }
        lastSearchRoot = picked
        if let bookmark = try? picked.bookmarkData(options: [], includingResourceValuesForKeys: nil, relativeTo: nil) {
            UserDefaults.standard.set(bookmark, forKey: searchBookmarkKey)
        }
        let scan = GameFiles.scan(picked)
        recordArchives(scan.archives, root: picked)
        guard let best = scan.best else {
            if !scan.archives.isEmpty { log("No unpacked game in the picked folder; archives: \(scan.archives.map(\.lastPathComponent))"); return .archivesOnly(scan.archives) }
            return .refused(wrongFolderMessage(picked))
        }
        let subpath = relative(best.data, to: picked)
        guard best.isComplete || accepted(best, subpath: subpath) else {
            pendingPick = (picked, best)
            log("Picked game folder can't be used (\(subpath.isEmpty ? "the picked folder" : subpath)): \(best.problems.count) problems")
            log(best.details.split(separator: "\n").prefix(20).joined(separator: "\n"))
            return .incomplete(best)
        }
        do {
            let bookmark = try picked.bookmarkData(options: [], includingResourceValuesForKeys: nil, relativeTo: nil)
            UserDefaults.standard.set(bookmark, forKey: bookmarkKey)
            UserDefaults.standard.set(false, forKey: inAppKey)
            UserDefaults.standard.set(subpath, forKey: subpathKey)
            UserDefaults.standard.set(displayName(best.data), forKey: nameKey)
            acceptedProblemCount = best.problems.count
            log("Game folder accepted: data at \(subpath.isEmpty ? "(the picked folder)" : subpath), all \(best.fileCount) files checked")
            return .accepted(best)
        } catch {
            return .refused("The app could not remember that folder: \(error.localizedDescription)")
        }
    }

    // MARK: Play anyway

    /// A folder with a few damaged or missing files can still be used, at the player's risk: the
    /// game may crash where it needs them. Not for iCloud-only files, which can't be read at all.
    static func playAnywayAllowed(_ report: GameFiles.Report) -> Bool {
        report.fileCount > 0 && !report.isComplete && report.inICloud.isEmpty && report.problems.count <= 20
    }
    private static func accepted(_ report: GameFiles.Report, subpath: String) -> Bool {
        guard let saved = UserDefaults.standard.string(forKey: acceptedKey) else { return false }
        let parts = saved.split(separator: "\u{1}", maxSplits: 1).map(String.init)
        return parts.count == 2 && parts[1] == subpath && report.problems.count <= Int(parts[0]) ?? 0 && playAnywayAllowed(report)
    }
    /// Uses the folder that was just refused (in the app's folder, or the last one picked) anyway.
    @discardableResult
    static func playAnyway(_ report: GameFiles.Report) -> Bool {
        guard playAnywayAllowed(report) else { return false }
        if let pick = pendingPick, pick.report.data == report.data {
            let subpath = relative(report.data, to: pick.url)
            UserDefaults.standard.set("\(report.problems.count)\u{1}\(subpath)", forKey: acceptedKey)
            if case .accepted = choose(pick.url) { pendingPick = nil; return true }
            return false
        }
        let subpath = relative(report.data, to: appFolder)
        UserDefaults.standard.set("\(report.problems.count)\u{1}\(subpath)", forKey: acceptedKey)
        log("Playing anyway with \(report.problems.count) problem files in \(subpath)")
        return findInAppFolder()
    }

    /// The chosen game's data/ folder, with access granted for the rest of this launch.
    static func open() -> URL? {
        let subpath = UserDefaults.standard.string(forKey: subpathKey) ?? ""
        if inAppFolder {
            let data = subpath.isEmpty ? appFolder : appFolder.appendingPathComponent(subpath)
            return GameFiles.gameData(at: data)?.resolvingSymlinksInPath().path == data.resolvingSymlinksInPath().path ? data : nil
        }
        guard let bookmark = UserDefaults.standard.data(forKey: bookmarkKey) else { return nil }
        var stale = false
        guard let root = try? URL(resolvingBookmarkData: bookmark, options: [], relativeTo: nil, bookmarkDataIsStale: &stale) else { return nil }
        if accessing != root {
            accessing?.stopAccessingSecurityScopedResource()
            accessing = root.startAccessingSecurityScopedResource() ? root : nil
        }
        guard FileManager.default.isReadableFile(atPath: root.path) else { return nil }
        if stale, let fresh = try? root.bookmarkData(options: [], includingResourceValuesForKeys: nil, relativeTo: nil) {
            UserDefaults.standard.set(fresh, forKey: bookmarkKey)
        }
        // Folders remembered by older versions have no subpath: look again.
        let data = subpath.isEmpty ? (GameFiles.scan(root, depth: 4).best?.data ?? root) : root.appendingPathComponent(subpath)
        return GameFiles.gameData(at: data)?.resolvingSymlinksInPath().path == data.resolvingSymlinksInPath().path ? data : nil
    }

    /// Checks every file of the game in use (Settings › Check game files).
    static func checkChosen() -> GameFiles.Report? {
        guard let data = open() else { return nil }
        return GameFiles.check(data)
    }

    // MARK: Helpers

    /// Explains what to pick instead when the picked folder has no game in it.
    private static func wrongFolderMessage(_ picked: URL) -> String {
        let name = picked.lastPathComponent
        let manager = FileManager.default
        let hasEngine = manager.fileExists(atPath: picked.appendingPathComponent("game.wasm").path)
            || manager.fileExists(atPath: picked.appendingPathComponent("8b0b5899ed/game.wasm").path)
        if name == "b" || name == "8b0b5899ed" || name == "shaders" || hasEngine {
            return "You opened the \"\(name)\" folder. Go back up one or two levels and pick the folder that has both \"data\" and \"b\" inside, then tap Open there."
        }
        return "There is no game in \"\(name)\". Pick the folder that has your game in it (any folder above it works, even On My iPhone itself).\n\nEasiest: move your game folder into Files › On My iPhone › ZGTA V. The app finds it there by itself."
    }

    /// The name shown for a game folder: the folder holding data/, or data/'s own name.
    private static func displayName(_ data: URL) -> String {
        data.lastPathComponent == "data" ? data.deletingLastPathComponent().lastPathComponent : data.lastPathComponent
    }
    private static func relative(_ url: URL, to base: URL) -> String {
        let full = url.resolvingSymlinksInPath().standardizedFileURL.path
        let root = base.resolvingSymlinksInPath().standardizedFileURL.path
        guard full == root || full.hasPrefix(root + "/") else { return full }
        return String(full.dropFirst(root.count)).trimmingCharacters(in: CharacterSet(charactersIn: "/"))
    }
    private static func describeLocation(_ url: URL) -> String {
        let values = try? url.resourceValues(forKeys: [.isUbiquitousItemKey, .volumeNameKey, .volumeIsInternalKey])
        var parts: [String] = []
        if values?.isUbiquitousItem == true { parts.append("iCloud") }
        if let volume = values?.volumeName { parts.append("volume \(volume)") }
        if values?.volumeIsInternal == false { parts.append("external drive") }
        if url.path.contains("/File Provider Storage/") || url.path.contains("/Containers/Shared/AppGroup/") { parts.append("On My iPhone") }
        else if url.path.contains("/Library/CloudStorage/") || url.path.contains("FileProvider") { parts.append("cloud or app provider") }
        return parts.isEmpty ? "location unknown" : parts.joined(separator: ", ")
    }
}
