import UIKit
import UniformTypeIdentifiers

/// Dedicated Mod Manager screen: manage installed mods, import mod archives/files (.zip, .rpf, .meta, .asi),
/// and spawn installed add-on/DLC vehicles and iconic GTA V vehicles directly into the game.
final class ModManagerViewController: UITableViewController, UIDocumentPickerDelegate, UISearchResultsUpdating {
    private let engineRunning: Bool
    private let fileManager = FileManager.default
    private var modFiles: [ModFile] = []
    private var dlcCatalog: ModRuntime.Catalog = ModRuntime.Catalog()
    private var changes: ModChangeQueue { ModChangeQueue(directory: Self.modsDirectory) }
    /// Set by the game screen: spawns through it (with progress and failure messages on the game view).
    var spawnHandler: ((String) -> Void)?
    var teleportHandler: (() -> Void)?
    var cheatHandler: ((String, CheatInputMode) -> Void)?
    /// The immutable set registered in this engine launch, not next-launch disk changes.
    var loadedVehicleModels = Set<String>()
    var cheatsAllowed = !MugoatOnlineEnabled() && GameSettings.shared.gameMode != .sandbox
    private var inputMode: CheatInputMode = .console
    private let actionSearch = UISearchController(searchResultsController: nil)
    private var filteredCheats: [CheatItem] {
        let query = actionSearch.searchBar.text?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return CHEAT_LIST.filter { query.isEmpty || [L10n.text($0.name), L10n.text($0.desc), L10n.text($0.category), $0.code].contains { $0.localizedCaseInsensitiveContains(query) } }
    }

    typealias ModFile = ModFiles.Entry

    private var expandedVehicleCategories = Set<String>()
    private var includeDLCVehicles = true
    private var availabilityTimer: Timer?
    private func vehicleAvailability(_ model: String) -> Int32 {
        guard engineRunning else { return -1 }
        return model.withCString { PGVehicleModelAvailability($0) }
    }
    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        availabilityTimer?.invalidate()
        availabilityTimer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in
            guard let self else { return }
            for index in self.tableView.indexPathsForVisibleRows ?? [] where index.section == 3 {
                guard index.row < self.vehicleRows.count, case .vehicle = self.vehicleRows[index.row], let cell = self.tableView.cellForRow(at: index) else { continue }
                self.configureVehicleCell(cell, row: self.vehicleRows[index.row])
            }
        }
    }
    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated); availabilityTimer?.invalidate(); availabilityTimer = nil
    }
    deinit { availabilityTimer?.invalidate() }
    // One snapshot per user change. Table callbacks must not rebuild/sort the
    // whole catalog for every cell or disagree during a row insertion/deletion.
    private var vehicleRows: [VehicleCatalog.Row] = []

    private func makeVehicleRows() -> [VehicleCatalog.Row] {
        VehicleCatalog.rows(query: actionSearch.searchBar.text ?? "", expanded: expandedVehicleCategories,
                            includeDLC: includeDLCVehicles, modModels: dlcCatalog.vehicleModels + Array(loadedVehicleModels))
    }

    private func updateVehicleRows() {
        let next = makeVehicleRows()
        let change = VehicleCatalog.rowChanges(from: vehicleRows, to: next)
        // Reloading an inset-grouped section discards all its visible cells.
        // Keep those cells and the tapped category alive throughout the change.
        UIView.performWithoutAnimation {
            tableView.beginUpdates()
            vehicleRows = next
            tableView.deleteRows(at: change.removed.map { IndexPath(row: $0, section: 3) }, with: .none)
            tableView.insertRows(at: change.inserted.map { IndexPath(row: $0, section: 3) }, with: .none)
            tableView.endUpdates()
            for path in tableView.indexPathsForVisibleRows ?? [] where path.section == 3 {
                if let cell = tableView.cellForRow(at: path) {
                    configureVehicleCell(cell, row: vehicleRows[path.row])
                }
            }
            tableView.layoutIfNeeded()
        }
    }

    /// The dedicated mods directory: Files › On My iPhone › ZGTA V › mods
    static var modsDirectory: URL {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let url = docs.appendingPathComponent("mods")
        if !FileManager.default.fileExists(atPath: url.path) {
            try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        }
        return url
    }

    init(engineRunning: Bool) {
        self.engineRunning = engineRunning
        super.init(style: .insetGrouped)
        title = L10n.text("Mod Manager")
        overrideUserInterfaceStyle = .dark
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) is not used") }

    override func viewDidLoad() {
        super.viewDidLoad()
        navigationItem.rightBarButtonItem = UIBarButtonItem(systemItem: .done, primaryAction: UIAction { [weak self] _ in
            self?.dismiss(animated: true)
        })
        tableView.backgroundView = Theme.dimmedBackdrop(image: "SettingsBackground")
        navigationItem.rightBarButtonItem?.tintColor = Theme.accent
        actionSearch.searchResultsUpdater = self
        actionSearch.obscuresBackgroundDuringPresentation = false
        actionSearch.searchBar.placeholder = "Search vehicles, models or cheat actions"
        navigationItem.searchController = actionSearch
        definesPresentationContext = true
        refreshControl = UIRefreshControl()
        refreshControl?.addAction(UIAction { [weak self] _ in self?.scanMods() }, for: .valueChanged)
        _ = Self.modsDirectory
        scanMods()
    }

    private func scanMods() {
        modFiles = ModFiles.scan(Self.modsDirectory)
        dlcCatalog = ModRuntime.catalog(Self.modsDirectory)
        vehicleRows = makeVehicleRows()
        tableView.reloadData()
        refreshControl?.endRefreshing()
    }

    // MARK: - Table view data source

    func updateSearchResults(for searchController: UISearchController) {
        vehicleRows = makeVehicleRows()
        tableView.reloadData()
    }

    override func numberOfSections(in tableView: UITableView) -> Int { 6 }

    override func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        switch section {
        case 0: return 4 // Import, folder, refresh and pending changes
        case 1: return max(1, modFiles.count) // Installed mod files
        case 2: return 1 // Player actions
        case 3: return vehicleRows.count
        case 4: return 2
        case 5: return max(1, filteredCheats.count)
        default: return 0
        }
    }

    override func tableView(_ tableView: UITableView, titleForHeaderInSection section: Int) -> String? {
        switch section {
        case 0: return L10n.text("Mod Settings & Files")
        case 1: return L10n.text("Installed Mods") + " · \(modFiles.count)"
        case 2: return "Player actions"
        case 3: return "Vehicle spawner"
        case 4: return "Cheat controls"
        case 5: return "Cheat actions · \(filteredCheats.count)"
        default: return nil
        }
    }

    override func tableView(_ tableView: UITableView, titleForFooterInSection section: Int) -> String? {
        switch section {
        case 0:
            let support = "Only compatible add-on RPF packs load in this build. Loose files and Windows script mods are stored, but do not run."
            return (engineRunning ? "Changes to installed mods apply next time you start the app. Import new mods before starting a game." : L10n.text("Copy mod files (.rpf, .meta, .yft, .ytd) into Files › On My iPhone › ZGTA V › mods. Use Import Mod to extract archives. Readme .txt files are not counted as mods.")) + "\n\n" + support
        case 2:
            return "Available during offline play and Engine LAN. Select a waypoint on the map first."
        case 3:
            return "Expand a category or search by vehicle name/model. Tap a vehicle to preview it, then press Spawn. DLC entries require matching installed game files; this list does not download them. Boats need water and planes need room. Detected mod packs must be loaded by the current game; new changes apply next launch."
        case 4:
            return "Console and Auto send a code through the game console. Gamepad sends its button sequence. A delivered command does not confirm the game accepted it."
        case 5:
            return !engineRunning ? "Start a game before applying an action." : cheatsAllowed ? "Select an action to return to the game and apply it." : "Cheat codes are disabled in this game mode. Vehicle and waypoint tools remain available above."
        default: return nil
        }
    }

    override func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let cell = UITableViewCell(style: .subtitle, reuseIdentifier: nil)
        cell.backgroundColor = Theme.rowBackground
        cell.textLabel?.textColor = Theme.text
        cell.detailTextLabel?.textColor = Theme.secondaryText
        cell.detailTextLabel?.numberOfLines = 2

        switch indexPath.section {
        case 0:
            let titles = [
                L10n.text("Import Mod from file (.zip, .rpf, .meta)"),
                L10n.text("Mods Folder Location"),
                L10n.text("Refresh Mod List"),
                "Pending mod changes"
            ]
            let subs = [
                L10n.text("Choose a file from Files or iCloud to import into ZGTA V"),
                "Files › On My iPhone › ZGTA V › mods",
                L10n.text("Rescan after copying files from a computer or the Files app"),
                "Cancel changes waiting for the next launch."
            ]
            let icons = ["square.and.arrow.down.fill", "folder.fill.badge.gearshape", "arrow.clockwise", "clock.arrow.circlepath"]
            cell.textLabel?.text = titles[indexPath.row]
            cell.detailTextLabel?.text = subs[indexPath.row]
            cell.imageView?.image = UIImage(systemName: icons[indexPath.row])
            cell.imageView?.tintColor = Theme.accent
            cell.accessoryType = indexPath.row == 0 ? .disclosureIndicator : .none

        case 1:
            if modFiles.isEmpty {
                cell.textLabel?.text = L10n.text("No mods installed")
                cell.detailTextLabel?.text = L10n.text("Tap 'Import Mod from File' above, or copy files into ZGTA V/mods.")
                cell.imageView?.image = UIImage(systemName: "tray")
                cell.imageView?.tintColor = Theme.secondaryText
                cell.selectionStyle = .none
            } else {
                let mod = modFiles[indexPath.row]
                cell.textLabel?.text = mod.name
                let sizeStr = ByteCountFormatter.string(fromByteCount: mod.size, countStyle: .file)
                let dateStr = DateFormatter.localizedString(from: mod.modified, dateStyle: .short, timeStyle: .short)
                cell.detailTextLabel?.text = "\(sizeStr) · \(dateStr) · \(mod.isEnabled ? L10n.text("Enabled") : L10n.text("Disabled"))"
                cell.imageView?.image = UIImage(systemName: mod.isEnabled ? "checkmark.circle.fill" : "xmark.circle")
                cell.imageView?.tintColor = mod.isEnabled ? Theme.accent : .systemGray
                if mod.isEnabled && !dlcCatalog.packs.contains(where: { $0.url.standardizedFileURL == mod.url.standardizedFileURL }) {
                    cell.detailTextLabel?.text = "\(sizeStr) · Stored only · not a compatible add-on pack"
                    cell.imageView?.image = UIImage(systemName: "doc")
                    cell.imageView?.tintColor = Theme.secondaryText
                }
                if let pending = try? changes.pending(for: mod) {
                    let detail: String
                    switch pending {
                    case .enable: detail = "Enable after restart"
                    case .disable: detail = "Disable after restart"
                    case .remove: detail = "Remove after restart"
                    }
                    cell.detailTextLabel?.text = "\(sizeStr) · \(detail)"
                }
                cell.accessoryType = .detailButton
            }

        case 2:
            cell.textLabel?.text = "Spawn to waypoint"
            cell.detailTextLabel?.text = "Move to the waypoint selected on the map."
            cell.imageView?.image = UIImage(systemName: "mappin.and.ellipse")
            cell.imageView?.tintColor = Theme.accent
            cell.accessoryType = .disclosureIndicator

        case 3:
            configureVehicleCell(cell, row: vehicleRows[indexPath.row])

        case 4:
            cell.textLabel?.text = indexPath.row == 0 ? "Activation method" : "Enter custom cheat"
            cell.detailTextLabel?.text = indexPath.row == 0 ? L10n.text(inputMode.rawValue) : "Enter a code such as PAINKILLER."
            cell.imageView?.image = UIImage(systemName: indexPath.row == 0 ? "slider.horizontal.3" : "text.cursor")
            cell.imageView?.tintColor = Theme.accent
            cell.accessoryType = .disclosureIndicator
        case 5:
            if filteredCheats.isEmpty {
                cell.textLabel?.text = "No matching cheat actions"
                cell.selectionStyle = .none
            } else {
                let action = filteredCheats[indexPath.row]
                cell.textLabel?.text = L10n.text(action.name)
                cell.detailTextLabel?.text = "\(L10n.text(action.category)) · \(action.code)\n\(L10n.text(action.desc))"
                cell.imageView?.image = UIImage(systemName: "sparkles")
                cell.imageView?.tintColor = Theme.accent
                cell.accessoryType = .disclosureIndicator
                if !engineRunning || !cheatsAllowed { cell.textLabel?.textColor = Theme.secondaryText }
            }
        default: break
        }

        return cell
    }

    private func configureVehicleCell(_ cell: UITableViewCell, row: VehicleCatalog.Row) {
        cell.imageView?.tintColor = Theme.accent
        cell.textLabel?.textColor = Theme.text
        cell.detailTextLabel?.textColor = Theme.secondaryText
        cell.selectionStyle = .default
        cell.accessoryView = nil
        switch row {
        case .custom:
            cell.textLabel?.text = "Spawn by model name…"
            cell.detailTextLabel?.text = "Use a model name from the game or a compatible loaded mod."
            cell.imageView?.image = UIImage(systemName: "magnifyingglass.circle.fill")
            cell.accessoryType = .disclosureIndicator
        case .dlcFilter:
            cell.textLabel?.text = "Show DLC vehicle models"
            cell.detailTextLabel?.text = "Includes newer models that may need additional game files."
            cell.accessoryType = includeDLCVehicles ? .checkmark : .none
            cell.accessibilityValue = includeDLCVehicles ? "On" : "Off"
        case let .category(category, count, open):
            cell.textLabel?.text = "\(category.name) · \(count)"
            cell.detailTextLabel?.text = open ? "Tap to collapse" : "Tap to expand"
            cell.imageView?.image = VehicleCategoryIcons.image(named: category.icon)
            cell.accessoryView = UIImageView(image: UIImage(systemName: open ? "chevron.down" : "chevron.right"))
            cell.accessoryView?.tintColor = Theme.accent
            cell.accessibilityValue = open ? "Expanded" : "Collapsed"
            cell.accessibilityTraits.insert(.button)
        case let .vehicle(vehicle):
            cell.textLabel?.text = vehicle.name
            let pending = vehicle.kind == "mod" && engineRunning && !loadedVehicleModels.contains(vehicle.model)
            cell.detailTextLabel?.text = pending ? "\(vehicle.model) · Available next launch" : vehicle.detail
            let availability = pending || !vehicle.canSpawn ? -1 : vehicleAvailability(vehicle.model)
            if availability == 0 || availability == -2 {
                cell.detailTextLabel?.text = vehicle.model + (availability == 0 ? (vehicle.kind == "mod" && loadedVehicleModels.contains(vehicle.model) ? " · Installed pack not loaded" : " · Files unavailable") : " · Unsupported model")
                cell.detailTextLabel?.textColor = UIColor.systemRed.withAlphaComponent(0.8)
                cell.textLabel?.textColor = Theme.secondaryText
                let mark = UIImageView(image: UIImage(systemName: "xmark.circle.fill"))
                mark.tintColor = UIColor.systemRed.withAlphaComponent(0.8)
                mark.isAccessibilityElement = false
                cell.accessoryView = mark
                cell.accessibilityValue = availability == 0 ? "Required vehicle files are missing or not loaded in this game" : "Not a vehicle model in this game"
            } else { cell.accessibilityValue = availability == 2 ? "Checking game files" : nil }
            cell.indentationLevel = 1
            cell.accessoryType = vehicle.canSpawn && !pending ? .disclosureIndicator : .none
            if !vehicle.canSpawn || pending { cell.selectionStyle = .none; cell.textLabel?.textColor = Theme.secondaryText }
        case .emptyMods:
            cell.textLabel?.text = "No compatible mod vehicles detected"
            cell.detailTextLabel?.text = "Import an add-on DLC pack, then refresh mods."
            cell.selectionStyle = .none
        }
    }

    override func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
        tableView.deselectRow(at: indexPath, animated: true)

        switch indexPath.section {
        case 0:
            if indexPath.row == 0 { pickModFile() }
            else if indexPath.row == 1 { showFolderInfo() }
            else if indexPath.row == 2 { scanMods() }
            else if indexPath.row == 3 {
                let alert = UIAlertController(title: "Pending mod changes", message: "Cancel all queued changes? Installed mods and the running game are kept.", preferredStyle: .alert)
                alert.addAction(UIAlertAction(title: "Keep changes", style: .cancel))
                alert.addAction(UIAlertAction(title: "Cancel pending changes", style: .destructive) { [weak self] _ in
                    guard let self else { return }
                    do { try self.changes.cancelAll(); self.scanMods() }
                    catch { self.showAlert("Mod changes", error.localizedDescription) }
                })
                present(alert, animated: true)
            }

        case 1:
            guard !modFiles.isEmpty, indexPath.row < modFiles.count else { return }
            toggleMod(at: indexPath.row)

        case 2:
            requestWaypointTeleport()

        case 3:
            switch vehicleRows[indexPath.row] {
            case .custom:
                promptCustomVehicleSpawn()
            case .dlcFilter:
                includeDLCVehicles.toggle()
                updateVehicleRows()
            case let .category(category, _, _):
                if !expandedVehicleCategories.insert(category.id).inserted { expandedVehicleCategories.remove(category.id) }
                updateVehicleRows()
            case let .vehicle(vehicle):
                if vehicle.canSpawn && (vehicle.kind != "mod" || !engineRunning || loadedVehicleModels.contains(vehicle.model)) {
                    let preview = VehiclePreviewViewController(vehicle: vehicle, availability: { [weak self] in self?.vehicleAvailability(vehicle.model) ?? -1 }) { [weak self] in
                        self?.spawnVehicle(named: vehicle.model)
                    }
                    present(preview, animated: true)
                }
            case .emptyMods: break
            }

        case 4:
            if indexPath.row == 0 { chooseInputMode() } else { promptCustomCheat() }
        case 5:
            guard !filteredCheats.isEmpty else { return }
            requestCheat(filteredCheats[indexPath.row].code)
        default: break
        }
    }

    private func chooseInputMode() {
        let alert = UIAlertController(title: "Activation method", message: nil, preferredStyle: .alert)
        for mode in CheatInputMode.allCases {
            alert.addAction(UIAlertAction(title: L10n.text(mode.rawValue), style: .default) { [weak self] _ in
                self?.inputMode = mode
                self?.tableView.reloadData()
            })
        }
        alert.addAction(UIAlertAction(title: L10n.text("Cancel"), style: .cancel))
        present(alert, animated: true)
    }

    private func promptCustomCheat() {
        let alert = UIAlertController(title: "Enter custom cheat", message: "Enter a cheat code to apply in your offline game.", preferredStyle: .alert)
        alert.addTextField { field in field.placeholder = "PAINKILLER"; field.autocapitalizationType = .allCharacters; field.autocorrectionType = .no }
        alert.addAction(UIAlertAction(title: "Apply", style: .default) { [weak self, weak alert] _ in
            self?.requestCheat(alert?.textFields?.first?.text ?? "")
        })
        alert.addAction(UIAlertAction(title: L10n.text("Cancel"), style: .cancel))
        present(alert, animated: true)
    }

    private func requestCheat(_ code: String) {
        guard engineRunning, cheatsAllowed, !MugoatOnlineEnabled(), let cheatHandler else {
            showAlert("Cheat unavailable", !engineRunning ? "Enter the game first." : "Cheat codes are disabled in this game mode.")
            return
        }
        guard !CheatManager.isApplying else { showAlert("Action running", "Wait for the current cheat action to finish."); return }
        let code = code.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        guard !code.isEmpty, code.utf8.count <= 63, code.allSatisfy({ $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "_") }) else {
            showAlert("Invalid cheat", "Use 1–63 letters, digits or underscores."); return
        }
        let mode = inputMode
        actionSearch.isActive = false
        returnToGame { cheatHandler(code, mode) }
    }

    private func returnToGame(_ action: @escaping () -> Void) {
        // Dismiss the owning sheet, including a custom-code/model prompt or
        // search presentation, before sending keyboard/gamepad input.
        let presenter = navigationController?.presentingViewController ?? presentingViewController
        if let presenter { presenter.dismiss(animated: true, completion: action) }
        else { dismiss(animated: true, completion: action) }
    }

    // MARK: - Mod File Actions

    private func pickModFile() {
        guard !engineRunning else {
            showAlert("Import mods", "Import new mods before starting a game. Your current game and mods are kept.")
            return
        }
        let types = ModFiles.importExtensions.sorted().map {
            UTType(filenameExtension: $0) ?? UTType(importedAs: "vn.iosvn.mugoat.mod.\($0)", conformingTo: .data)
        }
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: types, asCopy: true)
        picker.delegate = self
        picker.allowsMultipleSelection = true
        present(picker, animated: true)
    }

    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        guard !engineRunning else {
            showAlert("Import mods", "Import new mods before starting a game. Your current game and mods are kept.")
            return
        }
        let destDir = Self.modsDirectory
        var extractedCount = 0
        var copiedCount = 0
        var rejected: [String] = []

        for url in urls {
            let ext = url.pathExtension.lowercased()
            guard ModFiles.importExtensions.contains(ext),
                  (try? url.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) == true else {
                rejected.append(url.lastPathComponent)
                continue
            }
            if ModFiles.archiveExtensions.contains(ext) {
                let count = gi_extract_archive(url.path, destDir.path)
                if count > 0 {
                    extractedCount += Int(count)
                } else {
                    rejected.append(url.lastPathComponent)
                }
            } else if ext == "rpf" {
                do {
                    _ = try ModRuntime.importPack(url, into: destDir)
                    copiedCount += 1
                } catch {
                    let target = destDir.appendingPathComponent(url.lastPathComponent)
                    try? fileManager.removeItem(at: target)
                    if (try? fileManager.copyItem(at: url, to: target)) != nil {
                        copiedCount += 1
                    } else {
                        rejected.append("\(url.lastPathComponent): \(error.localizedDescription)")
                    }
                }
            } else {
                let target = destDir.appendingPathComponent(url.lastPathComponent)
                try? fileManager.removeItem(at: target)
                if (try? fileManager.copyItem(at: url, to: target)) != nil {
                    copiedCount += 1
                } else {
                    rejected.append(url.lastPathComponent)
                }
            }
        }
        scanMods()
        var messages: [String] = []
        if extractedCount > 0 {
            messages.append(String(format: L10n.text("Extracted %d files into mods. Readme files are not counted as mods."), extractedCount))
        }
        if copiedCount > 0 {
            messages.append(String(format: L10n.text("Added %d mod files."), copiedCount))
        }
        if !rejected.isEmpty {
            messages.append(L10n.text("Could not import these files (unsupported format or unable to read/extract):") + "\n" + rejected.joined(separator: "\n"))
        }
        guard !messages.isEmpty else { return }
        showAlert(L10n.text("Mod Import Results"), messages.joined(separator: "\n\n"))
    }

    private func toggleMod(at index: Int) {
        let mod = modFiles[index]
        let sheet = UIAlertController(title: mod.name, message: engineRunning ? "Changes apply after restarting the app. Your running game keeps its current mods." : L10n.text("Choose an action for this mod:"), preferredStyle: .actionSheet)
        let toggleTitle = mod.isEnabled ? L10n.text("Disable This Mod (.disabled)") : L10n.text("Enable This Mod")
        sheet.addAction(UIAlertAction(title: toggleTitle, style: .default) { [weak self] _ in
            guard let self else { return }
            self.change(mod.isEnabled ? .disable : .enable, for: mod)
        })
        sheet.addAction(UIAlertAction(title: L10n.text("Delete Permanently"), style: .destructive) { [weak self] _ in
            guard let self else { return }
            self.change(.remove, for: mod)
        })
        if (try? changes.pending(for: mod)) != nil {
            sheet.addAction(UIAlertAction(title: "Cancel pending change", style: .default) { [weak self] _ in
                guard let self else { return }
                do { try self.changes.cancel(for: mod); self.scanMods() }
                catch { self.showAlert("Mod changes", error.localizedDescription) }
            })
        }
        sheet.addAction(UIAlertAction(title: L10n.text("Close"), style: .cancel))
        if let cell = tableView.cellForRow(at: IndexPath(row: index, section: 1)) {
            sheet.popoverPresentationController?.sourceView = cell
        }
        present(sheet, animated: true)
    }

    private func change(_ action: ModChangeQueue.Action, for mod: ModFile) {
        do {
            try changes.queue(action, for: mod)
            if !engineRunning { try changes.applyBeforeLaunch() }
            scanMods()
        } catch { showAlert("Mod changes", error.localizedDescription) }
    }

    private func showFolderInfo() {
        let path = Self.modsDirectory.path
        let alert = UIAlertController(
            title: L10n.text("ZGTA V Mod Folder"),
            message: "Path on iPhone:\n\(path)\n\nOpen Files › On My iPhone › ZGTA V › mods to manage or replace mod files.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: L10n.text("Copy Path"), style: .default) { _ in
            UIPasteboard.general.string = path
        })
        alert.addAction(UIAlertAction(title: L10n.text("Got It"), style: .cancel))
        present(alert, animated: true)
    }

    // MARK: - Vehicle Spawner

    private func spawnVehicle(named model: String) {
        guard engineRunning else {
            showAlert(L10n.text("Game Not Running"), L10n.text("Enter the game before spawning a vehicle."))
            return
        }
        guard PGWorldToolsMode() != 0 else {
            showAlert("Unavailable", "Vehicle spawning is available in offline play and Engine LAN.")
            return
        }
        if let spawnHandler {
            let name = model.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            guard !name.isEmpty else { return }
            returnToGame { spawnHandler(name) }
            return
        }
        var cleanModel = model.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if cleanModel == "mbs1k" { cleanModel = "mbslk" }
        guard !cleanModel.isEmpty else { return }
        let result = cleanModel.withCString { PGQueueSpawnVehicle($0) }
        if result == 1 {
            showAlert(L10n.text("Vehicle Requested"), String(format: L10n.text("Loading model '%@'. The vehicle will appear in front of your character."), cleanModel))
        } else {
            showAlert("Vehicle not queued", VehicleSpawnFeedback.failure(status: result, model: cleanModel))
        }
    }

    private func requestWaypointTeleport() {
        guard engineRunning else {
            showAlert("Enter the game first", "Start the game and select a waypoint on the map before teleporting.")
            return
        }
        guard PGWorldToolsMode() != 0 else {
            showAlert("Unavailable", "Waypoint teleport is available in offline play and Engine LAN.")
            return
        }
        guard let teleportHandler else {
            showAlert("Unavailable", "Open Mod Manager from the running game's settings to teleport.")
            return
        }
        returnToGame { teleportHandler() }
    }

    private func promptCustomVehicleSpawn() {
        let alert = UIAlertController(
            title: L10n.text("Spawn Vehicle by Model Name"),
            message: L10n.text("Enter a model from an installed mod (for example: mbslk) or GTA V (for example: sultan, adder, buzzard):"),
            preferredStyle: .alert
        )
        alert.addTextField { tf in
            tf.placeholder = "mbslk, sultan, buzzard..."
            tf.autocapitalizationType = .none
            tf.autocorrectionType = .no
        }
        alert.addAction(UIAlertAction(title: L10n.text("Spawn Vehicle"), style: .default) { [weak self, weak alert] _ in
            guard let text = alert?.textFields?.first?.text else { return }
            self?.spawnVehicle(named: text)
        })
        alert.addAction(UIAlertAction(title: L10n.text("Cancel"), style: .cancel))
        present(alert, animated: true)
    }

    private func showAlert(_ title: String, _ message: String) {
        let alert = UIAlertController(title: title, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: L10n.text("Got It"), style: .default))
        present(alert, animated: true)
    }
}
