import UIKit
import UniformTypeIdentifiers

final class SaveViewController: UITableViewController, UIDocumentPickerDelegate {
    private let engineRunning: Bool
    private let store: SaveStore
    private var files: [SaveStore.File] = []
    private var importingFolder = false
    private var importingStory = false
    private var working = false {
        didSet {
            navigationItem.rightBarButtonItem?.isEnabled = !working
            navigationController?.isModalInPresentation = working
        }
    }

    init(engineRunning: Bool) {
        self.engineRunning = engineRunning
        let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        store = SaveStore(root: URL(fileURLWithPath: EnginePaths.filesRoot().path), backups: documents.appendingPathComponent("SaveBackups"))
        super.init(style: .insetGrouped)
        title = L10n.text("Save game")
        overrideUserInterfaceStyle = .dark
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is not used") }
    override func viewDidLoad() {
        super.viewDidLoad()
        navigationItem.rightBarButtonItem = UIBarButtonItem(systemItem: .done, primaryAction: UIAction { [weak self] _ in self?.dismiss(animated: true) })
        tableView.backgroundView = Theme.dimmedBackdrop(image: "SettingsBackground")
        refreshControl = UIRefreshControl()
        refreshControl?.addAction(UIAction { [weak self] _ in self?.reloadFiles() }, for: .valueChanged)
        reloadFiles()
    }
    private func reloadFiles() {
        do { files = try store.files(); tableView.reloadData() }
        catch { message(L10n.text("Cannot read save files"), error.localizedDescription) }
        refreshControl?.endRefreshing()
    }
    override func numberOfSections(in tableView: UITableView) -> Int { 2 }
    override func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int { section == 0 ? 5 : max(1, files.count) }
    override func tableView(_ tableView: UITableView, titleForHeaderInSection section: Int) -> String? { section == 0 ? L10n.text("Backup & restore") : L10n.text("Current files") + " · \(files.count)" }
    override func tableView(_ tableView: UITableView, titleForFooterInSection section: Int) -> String? {
        guard section == 0 else { return nil }
        return L10n.text("Save progress using the phone or a save point in GTA V, then back up here. Backups are in Files › ZGTA V › SaveBackups. Restore before starting the game; existing saves are backed up before replacement.")
    }
    override func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let cell = UITableViewCell(style: .subtitle, reuseIdentifier: nil)
        cell.backgroundColor = Theme.rowBackground
        cell.textLabel?.textColor = Theme.text
        cell.detailTextLabel?.textColor = Theme.secondaryText
        cell.detailTextLabel?.numberOfLines = 2
        if indexPath.section == 0 {
            let titles = [L10n.text("Back up all saves"), L10n.text("Import a backup"), L10n.text("Refresh files"), L10n.text("Import a save folder"), L10n.text("Add a Story save")]
            let symbols = ["square.and.arrow.up", "square.and.arrow.down", "arrow.clockwise", "folder.badge.plus", "doc.badge.plus"]
            cell.textLabel?.text = titles[indexPath.row]
            cell.imageView?.image = UIImage(systemName: symbols[indexPath.row]); cell.imageView?.tintColor = Theme.accent
            cell.detailTextLabel?.text = indexPath.row == 0 ? L10n.text("Create a backup, then save or share it") : indexPath.row == 1 ? (engineRunning ? L10n.text("Reopen the app and import before pressing Play") : L10n.text("Choose an exported game backup")) : L10n.text("Refresh after the game has saved")
            cell.accessoryType = .disclosureIndicator
            if indexPath.row == 3 { cell.detailTextLabel?.text = L10n.text("Choose a folder containing userdata and sandbox, for example ZGTA V/saves") }
            if indexPath.row == 4 { cell.detailTextLabel?.text = L10n.text(engineRunning ? "Close the game before adding a Story save." : "Choose one SGTA5 file. Uses an empty manual slot; existing saves and autosave are kept.") }
            if [1, 3, 4].contains(indexPath.row) && engineRunning { cell.textLabel?.textColor = Theme.tertiaryText }
        } else if files.isEmpty {
            cell.textLabel?.text = L10n.text("No save files yet")
            cell.detailTextLabel?.text = L10n.text("Play Story mode and save in the game, then return here.")
            cell.selectionStyle = .none
        } else {
            let file = files[indexPath.row]
            cell.textLabel?.text = file.url.lastPathComponent
            let date = DateFormatter.localizedString(from: file.modified, dateStyle: .short, timeStyle: .short)
            let size = ByteCountFormatter.string(fromByteCount: Int64(file.size), countStyle: .file)
            cell.detailTextLabel?.text = "\(file.path)\n\(size) · \(date)"
            cell.imageView?.image = UIImage(systemName: "doc.fill"); cell.imageView?.tintColor = Theme.accent
            cell.accessoryType = .disclosureIndicator
        }
        return cell
    }
    override func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
        tableView.deselectRow(at: indexPath, animated: true)
        guard !working else { return }
        if indexPath.section == 1 {
            guard !files.isEmpty else { return }
            let file = files[indexPath.row]
            do {
                guard file.size <= SaveStore.totalLimit else { throw SaveStore.Failure.tooLarge }
                let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
                try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
                let copy = directory.appendingPathComponent(file.url.lastPathComponent)
                let bytes = try Data(contentsOf: file.url)
                guard bytes.count <= SaveStore.totalLimit, bytes == (try Data(contentsOf: file.url)) else { throw SaveStore.Failure.changed }
                try bytes.write(to: copy, options: .atomic)
                share(copy, from: tableView.cellForRow(at: indexPath))
            } catch { message(L10n.text("Cannot export file"), error.localizedDescription) }
            return
        }
        switch indexPath.row {
        case 0:
            working = true
            DispatchQueue.global(qos: .userInitiated).async { [weak self] in
                guard let self else { return }
                let result = Result { try self.store.export() }
                DispatchQueue.main.async {
                    self.working = false
                    switch result {
                    case .success(let url): self.share(url, from: self.tableView.cellForRow(at: indexPath))
                    case .failure(let error): self.message(L10n.text("Cannot create backup"), error.localizedDescription)
                    }
                }
            }
        case 1, 3, 4:
            guard !engineRunning else { message(L10n.text("Restore before starting the game"), L10n.text("Reopen the app and open Save game before pressing Play.")); return }
            importingFolder = indexPath.row == 3
            importingStory = indexPath.row == 4
            let picker = UIDocumentPickerViewController(forOpeningContentTypes: importingFolder ? [.folder] : [.data], asCopy: !importingFolder && !importingStory)
            picker.delegate = self
            present(picker, animated: true)
        default: reloadFiles()
        }
    }
    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        guard !engineRunning, let source = urls.first else { return }
        if importingStory { addStory(source); return }
        let isFolder = importingFolder
        let alert = UIAlertController(title: L10n.text("Restore these saves?"), message: L10n.text("Saves at matching paths will be replaced. The app backs up existing saves first."), preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: L10n.text("Cancel"), style: .cancel))
        alert.addAction(UIAlertAction(title: L10n.text("Restore"), style: .default) { [weak self] _ in
            guard let self else { return }
            self.working = true
            DispatchQueue.global(qos: .userInitiated).async {
                let scoped = source.startAccessingSecurityScopedResource()
                defer { if scoped { source.stopAccessingSecurityScopedResource() } }
                let result = Result {
                    if isFolder {
                        let temporary = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
                        defer { try? FileManager.default.removeItem(at: temporary) }
                        let imported = SaveStore(root: source, backups: temporary)
                        let package = try imported.export()
                        try self.store.restore(from: package)
                    } else {
                        try self.store.restore(from: source)
                    }
                }
                DispatchQueue.main.async {
                    self.working = false
                    switch result {
                    case .success: self.reloadFiles(); self.message(L10n.text("Save files restored"), L10n.text("Select Story mode and start the game to load your progress."))
                    case .failure(let error): self.message(L10n.text("Cannot restore backup"), error.localizedDescription)
                    }
                }
            }
        })
        present(alert, animated: true)
    }
    private func addStory(_ source: URL) {
        guard !working && !engineRunning else { return }
        working = true
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self else { return }
            let scoped = source.startAccessingSecurityScopedResource()
            defer { if scoped { source.stopAccessingSecurityScopedResource() } }
            let result = Result {
                let data = try StorySave.read(source)
                let current = try self.store.files()
                guard current.count < 256, current.allSatisfy({ $0.size >= 0 && $0.size <= SaveStore.totalLimit }),
                      current.reduce(data.count, { $0 + $1.size }) <= SaveStore.totalLimit else { throw SaveStore.Failure.tooLarge }
                return try StorySave.install(data, filename: source.lastPathComponent, root: self.store.root)
            }
            DispatchQueue.main.async {
                self.working = false
                switch result {
                case .success(let imported):
                    self.reloadFiles()
                    self.message(L10n.text("Story save added"), "\(imported.title)\n\(L10n.text("Manual slot")) \(imported.slot)\n\n" + L10n.text("Select Story, then use Pause → Game → Load Game. A save from a newer GTA version may not load in this port."))
                case .failure(let error): self.message(L10n.text("Could not add Story save"), error.localizedDescription)
                }
            }
        }
    }
    private func share(_ url: URL, from source: UIView?) {
        let sheet = UIActivityViewController(activityItems: [url], applicationActivities: nil)
        sheet.popoverPresentationController?.sourceView = source ?? view
        sheet.popoverPresentationController?.sourceRect = (source ?? view).bounds
        present(sheet, animated: true)
    }
    private func message(_ title: String, _ text: String) {
        let alert = UIAlertController(title: title, message: text, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: L10n.text("Close"), style: .cancel))
        present(alert, animated: true)
    }
}
