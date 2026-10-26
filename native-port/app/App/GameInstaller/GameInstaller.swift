import Foundation

/// Downloads (or reads) an archive of the game and unpacks only the game's files into
/// `<destination>/data/`, without ever needing room for both the archive and the game.
///
/// ```swift
/// let task = GameInstaller.install(
///     from: .url(URL(string: "https://example.com/GTA.zip")!),
///     to: documentsFolder,
///     manifest: Bundle.main.url(forResource: "manifest", withExtension: "json")!,
///     progress: { p in label.text = "\(p.extractedBytes) of \(p.totalBytes)" },
///     completion: { result in ... })
/// // task.cancel()
/// ```
///
/// - Formats: zip (incl. zip64), rar (v4), rar5, tar, tar.gz. Multi-part rar sets
///   (`x.part1.rar`, `x.part2.rar`... or `x.rar`, `x.r00`...) and byte-split sets
///   (`x.zip.001`, `x.zip.002`...) are read as one stream.
/// - Only files listed in the manifest are written; everything else is skipped. The folder
///   that holds the game inside the archive (e.g. `Some Folder/GTA/data/`) is found by itself.
/// - Nothing is ever written outside `<destination>/data/`.
public enum GameInstaller {

    /// Where the archive comes from.
    public enum Source {
        /// One archive over HTTP(S). Streamed through small rolling chunk files.
        case url(URL)
        /// A multi-part set over HTTP(S), in order (part 1 first).
        case urls([URL])
        /// A local archive file. Other parts of a multi-part set next to it are found by name.
        case file(URL)
        /// Local parts of a multi-part set, in order.
        case files([URL])
    }

    public struct Options {
        /// Local files only: the installer may destroy the archive as it reads it
        /// (frees the read part with F_PUNCHHOLE on APFS and deletes finished parts, and the
        /// archive itself after a successful unpack). Then the archive and the game hardly
        /// ever need disk space at the same time. If unpacking fails half way, the archive is gone.
        public var allowModifyingSource = false
        /// URL only: most bytes of downloaded-but-not-yet-unpacked data kept on disk.
        public var maxPendingBytes: Int64 = 256 << 20
        /// URL only: size of each rolling chunk file.
        public var chunkSize: Int64 = 8 << 20
        /// Space to leave free on top of what the install needs.
        public var spaceMargin: Int64 = 500_000_000
        /// URL only: give up when the network has made no progress for this long.
        public var giveUpAfter: TimeInterval = 180
        /// URL only: a connection with no data for this long is dropped and resumed.
        public var requestTimeout: TimeInterval = 30
        /// URL only: extra HTTP headers (e.g. a cookie or token for the file host).
        public var httpHeaders: [String: String] = [:]
        /// Queue for the progress and completion callbacks.
        public var callbackQueue: DispatchQueue = .main
        /// How often progress is reported.
        public var progressInterval: TimeInterval = 0.25
        /// Copies the manifest to `<destination>/data/manifest.json` when the install succeeds
        /// (the app's GameFolder check looks for it).
        public var writeManifest = true
        /// Log lines (plain text, any thread). Useful for the app's shareable log.
        public var log: ((String) -> Void)?
        /// Manifest paths whose size may differ from the manifest without failing verification
        /// (they must still exist). For this game's Archive.zip:
        /// `common/non_final/www/parser/psomismatch.html` and `.../schemas.html` are 2 bytes larger
        /// than the manifest says (also in the mirror's own unpacked copy). Tolerated ones are
        /// listed in `Report.toleratedSizeMismatches`.
        public var toleratedSizeMismatches: Set<String> = []
        /// Tests only: pretend this much space is free.
        public var freeSpaceOverride: Int64?
        public init() {}
    }

    public enum Phase: String {
        case checking, downloading, unpacking, verifying, finished
    }

    public struct Progress {
        public var phase: Phase
        /// URL mode: bytes received from the network so far (all parts). Local mode: archive bytes read.
        public var downloadedBytes: Int64
        /// Size of the whole archive when known (Content-Length / file sizes).
        public var downloadTotalBytes: Int64?
        /// Game bytes written so far, and the game's total size (from the manifest).
        public var extractedBytes: Int64
        public var totalBytes: Int64
        public var filesDone: Int
        public var filesTotal: Int
        /// The file being written right now (manifest path), if any.
        public var currentFile: String?
        /// Unpack speed (game bytes per second) over the last few seconds.
        public var bytesPerSecond: Double?
        /// Estimated seconds left, when there is enough data to guess.
        public var secondsRemaining: Double?
        /// URL mode: downloaded bytes waiting on disk to be unpacked.
        public var pendingBytes: Int64
        /// Times a dropped connection was resumed.
        public var retries: Int
        public var fraction: Double { totalBytes > 0 ? min(1, Double(extractedBytes) / Double(totalBytes)) : 0 }
    }

    public struct Report {
        /// The game's data folder: `<destination>/data`.
        public var dataFolder: URL
        public var filesWritten: Int
        public var bytesWritten: Int64
        public var duration: TimeInterval
        /// Folder inside the archive that held the game (e.g. "Some Folder/GTA/data/"), "" for the root.
        public var archivePrefix: String
        /// Archive entries that were not game files (skipped).
        public var skippedEntries: Int
        /// Entries refused for safety (absolute paths, "..", links).
        public var unsafeEntries: [String]
        /// URL mode: largest amount of downloaded data waiting on disk at once.
        public var peakPendingBytes: Int64
        /// Largest growth of disk use during the install, compared with the start
        /// (archive bytes still allocated + game bytes written + pending chunks).
        public var peakDiskIncrease: Int64
        public var downloadedBytes: Int64
        public var retries: Int
        public var format: String
        /// Files whose size differs from the manifest but were allowed by `toleratedSizeMismatches`.
        public var toleratedSizeMismatches: [String] = []
    }

    /// Starts an install. Returns at once; work happens on background threads.
    /// `completion` is called exactly once (also after `cancel()`).
    @discardableResult
    public static func install(from source: Source,
                               to destination: URL,
                               manifest: URL,
                               options: Options = Options(),
                               progress: @escaping (Progress) -> Void,
                               completion: @escaping (Result<Report, InstallError>) -> Void) -> InstallTask {
        let task = InstallTask()
        let job = InstallJob(source: source, destination: destination, manifestURL: manifest,
                             options: options, task: task, progress: progress, completion: completion)
        task.job = job
        job.start()
        return task
    }
}

/// Handle for a running install.
public final class InstallTask {
    var job: InstallJob?
    /// Stops the install as soon as possible. Completion then reports `.cancelled`.
    /// Files already unpacked are kept; the half-written file and downloaded chunks are removed.
    public func cancel() { job?.cancel() }
}

/// Plain-English install failures.
public struct InstallError: Error, LocalizedError, CustomStringConvertible {
    public enum Kind: String {
        case notEnoughSpace, outOfSpace, webPageNotFile, httpError, networkLost, fileChangedOnServer
        case notAnArchive, unsupported, passwordProtected, corrupted, truncated, missingPart
        case noGameFiles, verificationFailed, sourceUnreadable, manifestUnreadable, cancelled, writeFailed
    }
    public var kind: Kind
    /// A sentence or two a player can act on.
    public var message: String
    /// Files involved (corrupted file, missing/wrong-size files after verification...).
    public var files: [String] = []
    /// Technical detail for logs (libarchive message, HTTP status...).
    public var detail: String?
    public var errorDescription: String? { message }
    public var description: String { "[\(kind.rawValue)] \(message)" + (detail.map { " (\($0))" } ?? "") }

    init(_ kind: Kind, _ message: String, files: [String] = [], detail: String? = nil) {
        self.kind = kind; self.message = message; self.files = files; self.detail = detail
    }
}

func formatBytes(_ bytes: Int64) -> String {
    let b = Double(bytes)
    if abs(b) >= 1e9 { return String(format: "%.2f GB", b / 1e9) }
    if abs(b) >= 1e6 { return String(format: "%.0f MB", b / 1e6) }
    if abs(b) >= 1e3 { return String(format: "%.0f KB", b / 1e3) }
    return "\(bytes) bytes"
}
