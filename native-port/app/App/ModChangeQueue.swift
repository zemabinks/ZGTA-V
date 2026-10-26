import Foundation

/// File operations requested during play are applied before the next engine launch.
/// Keep failed requests so a launch never silently loses an intended change.
struct ModChangeQueue {
    enum Action: String, Codable { case enable, disable, remove }
    private struct Request: Codable {
        let source: String
        let action: Action
        let inode: UInt64
        let size: UInt64
        let modified: Date
    }
    private struct Journal: Codable {
        let version: Int
        var requests: [String: Request]
    }
    struct Failure: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }
    let directory: URL
    init(directory: URL) {
        // iOS and macOS expose system aliases such as /var -> /private/var.
        // Resolve the known parent, but never follow the mods directory itself.
        var path = directory.deletingLastPathComponent().resolvingSymlinksInPath()
            .appendingPathComponent(directory.lastPathComponent).path
        // NSURL standardization can shorten /private/var back to /var.
        if path.hasPrefix("/var/") { path = "/private" + path }
        if path.hasPrefix("/tmp/") { path = "/private" + path }
        self.directory = URL(fileURLWithPath: path, isDirectory: true)
    }
    private var journalURL: URL { directory.appendingPathComponent(".pending-changes.json") }
    private let fm = FileManager.default

    private func checked(_ relative: String) throws -> URL {
        let components = relative.split(separator: "/", omittingEmptySubsequences: false)
        guard !components.isEmpty, components.allSatisfy({ !$0.isEmpty && $0 != "." && $0 != ".." && !$0.contains("\\") }),
              !relative.hasPrefix("."), relative.utf8.count <= 1024 else {
            throw Failure(message: "Invalid mod path. Your files were kept.")
        }
        let root = directory
        // Never follow a linked directory or file into another folder.
        var path = URL(fileURLWithPath: "/", isDirectory: true)
        for component in root.pathComponents.dropFirst() + components.map(String.init) {
            path.appendPathComponent(component)
            if let attributes = try? fm.attributesOfItem(atPath: path.path), attributes[.type] as? FileAttributeType == .typeSymbolicLink {
                throw Failure(message: "Linked mod paths cannot be changed (\(path.lastPathComponent)). Your files were kept.")
            }
        }
        return root.appendingPathComponent(relative)
    }

    private func load() throws -> Journal {
        _ = try checked("pending-check")
        if !fm.fileExists(atPath: journalURL.path) { return Journal(version: 1, requests: [:]) }
        let attributes = try fm.attributesOfItem(atPath: journalURL.path)
        guard attributes[.type] as? FileAttributeType == .typeRegular,
              (attributes[.size] as? NSNumber)?.intValue ?? Int.max <= 262144 else {
            throw Failure(message: "The pending mod changes cannot be read. Your files were kept.")
        }
        let journal = try JSONDecoder().decode(Journal.self, from: Data(contentsOf: journalURL))
        guard journal.version == 1, journal.requests.count <= 256 else {
            throw Failure(message: "The pending mod changes use an unsupported format. Your files were kept.")
        }
        for (key, request) in journal.requests {
            _ = try checked(key); _ = try checked(request.source)
            guard key == base(request.source), ModFiles.modExtensions.contains(URL(fileURLWithPath: key).pathExtension.lowercased()) else { throw Failure(message: "Invalid pending mod change. Your files were kept.") }
        }
        return journal
    }

    private func save(_ journal: Journal) throws {
        _ = try checked("pending-check")
        if fm.fileExists(atPath: journalURL.path) {
            guard try fm.attributesOfItem(atPath: journalURL.path)[.type] as? FileAttributeType == .typeRegular else {
                throw Failure(message: "The pending mod changes cannot be saved. Your files were kept.")
            }
        }
        let data = try JSONEncoder().encode(journal)
        guard data.count <= 262144 else { throw Failure(message: "Too many pending mod changes. Restart the app to apply them first.") }
        try data.write(to: journalURL, options: .atomic)
        try fm.setAttributes([.posixPermissions: 0o600], ofItemAtPath: journalURL.path)
    }

    private func base(_ name: String) -> String {
        name.lowercased().hasSuffix(".disabled") ? String(name.dropLast(9)) : name
    }

    func pending(for entry: ModFiles.Entry) throws -> Action? { try load().requests[base(entry.name)]?.action }

    func cancel(for entry: ModFiles.Entry) throws {
        var journal = try load(); journal.requests.removeValue(forKey: base(entry.name)); try save(journal)
    }

    /// Recovery for an unreadable journal, without touching any installed mod.
    func cancelAll() throws {
        _ = try checked("pending-check")
        if fm.fileExists(atPath: journalURL.path) {
            guard try fm.attributesOfItem(atPath: journalURL.path)[.type] as? FileAttributeType == .typeRegular else {
                throw Failure(message: "The pending changes file is not a regular file. Your mods were kept.")
            }
            let backup = directory.appendingPathComponent(".pending-changes-saved-" + UUID().uuidString + ".json")
            try fm.moveItem(at: journalURL, to: backup)
        }
    }

    func queue(_ action: Action, for entry: ModFiles.Entry) throws {
        var journal = try load()
        let url = try checked(entry.name)
        guard url.standardizedFileURL == entry.url.standardizedFileURL,
              ModFiles.modExtensions.contains(URL(fileURLWithPath: base(entry.name)).pathExtension.lowercased()) else { throw Failure(message: "This mod moved. Refresh the list and try again.") }
        let attributes = try fm.attributesOfItem(atPath: url.path)
        guard attributes[.type] as? FileAttributeType == .typeRegular,
              let inode = attributes[.systemFileNumber] as? NSNumber,
              let size = attributes[.size] as? NSNumber,
              let date = attributes[.modificationDate] as? Date else { throw Failure(message: "This mod cannot be changed. Your files were kept.") }
        if (action == .enable && entry.isEnabled) || (action == .disable && !entry.isEnabled) {
            journal.requests.removeValue(forKey: base(entry.name))
        } else {
            guard journal.requests.count < 256 || journal.requests[base(entry.name)] != nil else { throw Failure(message: "Restart the app to apply pending mod changes first.") }
            journal.requests[base(entry.name)] = Request(source: entry.name, action: action, inode: inode.uint64Value, size: size.uint64Value, modified: date)
        }
        try save(journal)
    }

    /// Must run on the UI thread before the engine is started or any mod file is opened.
    func applyBeforeLaunch() throws {
        var journal = try load()
        for key in journal.requests.keys.sorted() {
            guard let request = journal.requests[key] else { continue }
            let source = try checked(request.source)
            let target = try checked(request.action == .disable ? key + ".disabled" : key)
            let sourceExists = fm.fileExists(atPath: source.path)
            if request.action == .remove && !sourceExists {
                journal.requests.removeValue(forKey: key); try save(journal); continue
            }
            // A rename may have completed before a journal write failed. Accept only
            // the same inode, size and modification time at its intended destination.
            let candidate = !sourceExists && request.action != .remove ? target : source
            let attributes = try fm.attributesOfItem(atPath: candidate.path)
            guard attributes[.type] as? FileAttributeType == .typeRegular,
                  (attributes[.systemFileNumber] as? NSNumber)?.uint64Value == request.inode,
                  (attributes[.size] as? NSNumber)?.uint64Value == request.size,
                  attributes[.modificationDate] as? Date == request.modified else {
                throw Failure(message: "\(key) changed since the request. Cancel its pending change in Mod Manager, then try again. Your files were kept.")
            }
            if request.action == .remove { try fm.removeItem(at: source) }
            else if sourceExists && source != target { try fm.moveItem(at: source, to: target) }
            journal.requests.removeValue(forKey: key)
            try save(journal)
        }
    }
}
