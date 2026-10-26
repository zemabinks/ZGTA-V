// Compiled with the production GameFiles/GameFolder against private temporary fixtures.
import Foundation

let fm = FileManager.default
func directory(_ url: URL) throws { try fm.createDirectory(at: url, withIntermediateDirectories: true) }
func write(_ root: URL, _ path: String, _ bytes: Data = Data([1, 2])) throws {
    let url = root.appendingPathComponent(path)
    try directory(url.deletingLastPathComponent())
    try bytes.write(to: url)
}
func complete(_ root: URL) throws {
    for (path, _) in Fixture.files { try write(root.appendingPathComponent("data"), path) }
}
func partial(_ root: URL) throws {
    try directory(root.appendingPathComponent("data/x64"))
    try write(root.appendingPathComponent("data"), "common/config.xml")
}
func require(_ condition: @autoclosure () -> Bool, _ message: String) {
    precondition(condition(), message)
}
try directory(Fixture.appRoot)
try JSONSerialization.data(withJSONObject: ["files": Fixture.files.map { [$0.0, $0.1] as [Any] }]).write(to: Fixture.manifest)
try partial(Fixture.appRoot)
try write(Fixture.appRoot, "Mirror.zip", Data([80, 75, 3, 4]))
try write(Fixture.appRoot, "set.zip.001")
try write(Fixture.appRoot, "set.zip.002")
try write(Fixture.appRoot, "game.part1.rar")
try write(Fixture.appRoot, "game.part2.rar")
try write(Fixture.appRoot, "unsupported.7z")
let scan = GameFiles.scan(Fixture.appRoot)
require(scan.best?.problems.count == 3, "Partial scaffold must still be reported accurately")
require(Set(scan.archives.map(\.lastPathComponent)) == Set(["Mirror.zip", "set.zip.001", "game.part1.rar"]), "Archives beside a partial data folder must remain visible; only first supported parts appear")
let nested = Fixture.appRoot.appendingPathComponent("nested/full")
try complete(nested)
let nestedScan = GameFiles.scan(Fixture.appRoot)
require(nestedScan.best?.data.resolvingSymlinksInPath().path == nested.appendingPathComponent("data").resolvingSymlinksInPath().path, "A complete nested copy outranks the partial scaffold: \(nestedScan.folders.map { ($0.data.path, $0.details) })")
require(GameFiles.scan(Fixture.appRoot).archives.contains { $0.resolvingSymlinksInPath().path == Fixture.appRoot.appendingPathComponent("Mirror.zip").resolvingSymlinksInPath().path }, "Finding a complete nested game must not hide sibling archives")
try fm.removeItem(at: nested)

let outside = Fixture.root.appendingPathComponent("selected-folder")
try partial(outside)
try write(outside, "Selected.zip")
if case .incomplete = GameFolder.choose(outside) {} else { preconditionFailure("Must report the partial selected folder") }
let selected = outside.appendingPathComponent("Selected.zip")
require(GameFolder.archivesFound.contains { $0.resolvingSymlinksInPath().path == selected.resolvingSymlinksInPath().path }, "An incomplete result retains archive candidates")
require(GameFolder.accessRoot(for: selected)?.resolvingSymlinksInPath().path == outside.resolvingSymlinksInPath().path, "The source remembers the folder that supplied its permission")
require(!GameFolder.ownsFile(selected), "A folder-selected external archive must not be consumed")
// Simulate an alias/provider mapping changing after the enumeration grant
// ends. Looking up the parent must not resolve that file again without access.
let providerRoot = Fixture.root.appendingPathComponent("provider-directory")
try directory(providerRoot)
let alias = providerRoot.appendingPathComponent("Provider.zip")
try fm.createSymbolicLink(at: alias, withDestinationURL: selected)
if case .archivesOnly = GameFolder.choose(providerRoot) {} else { preconditionFailure("Provider directory must retain the archive") }
let candidate = GameFolder.archiveCandidates.first!
let remapped = Fixture.root.appendingPathComponent("provider-remapped")
try write(remapped, "Selected.zip")
try fm.removeItem(at: alias)
try fm.createSymbolicLink(at: alias, withDestinationURL: remapped.appendingPathComponent("Selected.zip"))
require(GameFolder.accessRoot(for: candidate.url)?.standardizedFileURL == providerRoot.standardizedFileURL, "Changing a resolved path must not lose its original security-scoped parent")
require(!candidate.ownedByApp, "A provider archive never gains consume permission")
GameFolder.findInAppFolder()
require(candidate.accessRoot.standardizedFileURL == providerRoot.standardizedFileURL, "A captured archive keeps its own parent even after the next search replaces the list")
_ = GameFolder.choose(outside)
require(GameFolder.ownsFile(Fixture.appRoot.appendingPathComponent("Mirror.zip")), "An actual app archive is recognized")
let sibling = Fixture.root.appendingPathComponent("app-documents-sibling/Mirror.zip")
try write(sibling.deletingLastPathComponent(), sibling.lastPathComponent)
require(!GameFolder.ownsFile(sibling), "A common textual prefix does not imply ownership")
let link = Fixture.appRoot.appendingPathComponent("external.zip")
try fm.createSymbolicLink(at: link, withDestinationURL: selected)
require(!GameFolder.ownsFile(link), "A symlink to an external archive is not app-owned")
try fm.createSymbolicLink(at: Fixture.appRoot.appendingPathComponent("external-copy.zip"), withDestinationURL: selected)
GameFolder.findInAppFolder()
let physicalArchives = GameFolder.archivesFound.map { $0.resolvingSymlinksInPath().path }
require(Set(physicalArchives).count == physicalArchives.count, "Multiple aliases must not duplicate an archive or trap the permission map")

try complete(outside)
require(GameFolder.refreshSearch(), "Look again must rescan the previously selected folder")
require(GameFolder.checkChosen()?.isComplete == true, "The repaired folder becomes usable")
try write(outside, "Later.zip")
require(GameFolder.refreshSearch(), "A remembered selection remains usable")
require(GameFolder.archivesFound.contains { $0.resolvingSymlinksInPath().path == outside.appendingPathComponent("Later.zip").resolvingSymlinksInPath().path }, "Remembering a folder must not skip fresh archive discovery")
try fm.removeItem(at: outside.appendingPathComponent("data/x64/second.dat"))
require(!GameFolder.refreshSearch(), "A stale incomplete remembered folder cannot remain Ready")
require(GameFolder.appFolderReport?.problems.count == 1, "The latest check reports the actual missing file")
let report = GameFiles.check(outside.appendingPathComponent("data"))
require(!report.explanation.message.lowercased().contains("delete"), "Missing files do not justify deleting the source folder")
require(!report.explanation.message.lowercased().contains("ran out"), "A file listing must not invent a storage diagnosis")
try complete(outside)
require(GameFolder.refreshSearch() && GameFolder.isChosen, "Repaired external game can be selected again")
try fm.removeItem(at: outside.appendingPathComponent("data"))
require(!GameFolder.refreshSearch() && !GameFolder.isChosen, "A moved/unavailable external data folder clears stale Ready even when no report can be made")
let empty = GameFiles.Report(data: outside, fileCount: 0, totalBytes: 0, problems: [])
require(!empty.isComplete, "An unavailable manifest cannot declare a game complete")
print("PASS: discovery, partial/nested candidates, supported archive parts, parent access, ownership boundaries, rescan, stale readiness and non-destructive diagnostics")
