import UIKit
import UniformTypeIdentifiers

/// The game files screen: where the files are and whether every one of them checks out, finding them
/// anywhere on this iPhone, and getting them from a link (your own game server, or an archive the app
/// downloads, unpacks and checks by itself) or from an archive already in Files.
final class GameFilesViewController: UIViewController, UIDocumentPickerDelegate, UITextFieldDelegate {
    /// Called whenever the game files in use changed.
    var onChange: (() -> Void)?
    /// Called with a game server address the user entered (streams the files instead of storing them).
    var onServer: ((String) -> Void)?
    /// Where unpacked games go: inside the app's folder, so the app finds them like any other.
    static var installFolder: URL { GameFolder.appFolder.appendingPathComponent("GTA V") }

    private let stack = UIStackView()
    private let statusIcon = UIImageView()
    private let statusTitle = UILabel()
    private let statusDetail = UILabel()
    private let detailsButton = Theme.glassButton(L10n.text("Show problem details"), symbol: "list.bullet")
    private let anywayButton = Theme.glassButton(L10n.text("Try playing anyway"), symbol: "exclamationmark.triangle")
    private let linkField = UITextField()
    private let linkButton = Theme.primaryButton(L10n.text("Continue"), symbol: "arrow.down.circle.fill")
    private let archivesStack = UIStackView()
    private let progressPanel = Theme.panel()
    private let progressBar = UIProgressView(progressViewStyle: .default)
    private let progressTitle = UILabel()
    private let progressDetail = UILabel()
    private let cancelButton = Theme.glassButton(L10n.text("Cancel"), symbol: "xmark")
    private var lastReport: GameFiles.Report?
    private var pickingArchive = false
    private let searchQueue = DispatchQueue(label: "com.zemabinks.zgta.files-search", qos: .userInitiated)
    private var searchGeneration = 0
    private var install: GameInstallManager { .shared }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = L10n.text("Game data")
        view.backgroundColor = Theme.night
        let backdrop = Theme.backdrop(image: "SettingsBackground", darken: 0.8)
        backdrop.frame = view.bounds
        backdrop.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.addSubview(backdrop)
        navigationItem.rightBarButtonItem = UIBarButtonItem(systemItem: .done, primaryAction: UIAction { [weak self] _ in self?.close() })
        navigationItem.rightBarButtonItem?.tintColor = Theme.accent

        let scroll = UIScrollView()
        scroll.translatesAutoresizingMaskIntoConstraints = false
        scroll.keyboardDismissMode = .interactive
        view.addSubview(scroll)
        stack.axis = .vertical
        stack.spacing = 14
        stack.translatesAutoresizingMaskIntoConstraints = false
        scroll.addSubview(stack)
        let guide = view.safeAreaLayoutGuide
        NSLayoutConstraint.activate([
            scroll.leadingAnchor.constraint(equalTo: view.leadingAnchor), scroll.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            scroll.topAnchor.constraint(equalTo: view.topAnchor), scroll.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            stack.topAnchor.constraint(equalTo: scroll.contentLayoutGuide.topAnchor, constant: 16),
            stack.bottomAnchor.constraint(equalTo: scroll.contentLayoutGuide.bottomAnchor, constant: -24),
            stack.centerXAnchor.constraint(equalTo: guide.centerXAnchor),
            stack.widthAnchor.constraint(lessThanOrEqualToConstant: 640),
            stack.widthAnchor.constraint(lessThanOrEqualTo: guide.widthAnchor, constant: -40)
        ])
        let wide = stack.widthAnchor.constraint(equalTo: guide.widthAnchor, constant: -40)
        wide.priority = .defaultHigh
        wide.isActive = true

        stack.addArrangedSubview(statusSection())
        stack.addArrangedSubview(findSection())
        stack.addArrangedSubview(linkSection())
        stack.addArrangedSubview(archiveSection())
        stack.addArrangedSubview(progressSection())
        NotificationCenter.default.addObserver(self, selector: #selector(installChanged), name: .gameInstallChanged, object: nil)
        // An install may already be running (started before this screen was closed).
        if install.isRunning { installChanged() } else { refresh(recheck: true) }
        // Automation: --install-link <url> starts a link install; --install-cancel-after <s> cancels it.
        let arguments = ProcessInfo.processInfo.arguments
        if let i = arguments.firstIndex(of: "--install-link"), i + 1 < arguments.count {
            linkField.text = arguments[i + 1]
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { self.useLink() }
            if let c = arguments.firstIndex(of: "--install-cancel-after"), c + 1 < arguments.count, let seconds = Double(arguments[c + 1]) {
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.5 + seconds) {
                    GameFolder.log("Automation: cancelling the install")
                    self.install.cancel()
                }
            }
            // Bring the progress into view.
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                guard let scroll = self.stack.superview as? UIScrollView else { return }
                scroll.setContentOffset(CGPoint(x: 0, y: max(0, scroll.contentSize.height - scroll.bounds.height + scroll.adjustedContentInset.bottom)), animated: false)
            }
        }
    }

    // MARK: Sections

    private func statusSection() -> UIView {
        statusIcon.preferredSymbolConfiguration = UIImage.SymbolConfiguration(pointSize: 26, weight: .semibold)
        statusIcon.contentMode = .scaleAspectFit
        statusIcon.widthAnchor.constraint(equalToConstant: 34).isActive = true
        statusTitle.font = Theme.display(19, .bold)
        statusTitle.accessibilityIdentifier = "gamefiles.status"
        statusTitle.textColor = Theme.text
        statusTitle.numberOfLines = 0
        statusDetail.font = Theme.body(14)
        statusDetail.textColor = Theme.secondaryText
        statusDetail.numberOfLines = 0
        let texts = UIStackView(arrangedSubviews: [statusTitle, statusDetail])
        texts.axis = .vertical
        texts.spacing = 4
        let row = UIStackView(arrangedSubviews: [statusIcon, texts])
        row.spacing = 14
        row.alignment = .top
        detailsButton.addAction(UIAction { [weak self] _ in self?.showDetails() }, for: .touchUpInside)
        let check = Theme.glassButton(L10n.text("Check every file again"), symbol: "checkmark.shield")
        check.accessibilityIdentifier = "gamefiles.recheck"
        check.addAction(UIAction { [weak self] _ in self?.refresh(recheck: true) }, for: .touchUpInside)
        anywayButton.addAction(UIAction { [weak self] _ in self?.confirmPlayAnyway() }, for: .touchUpInside)
        anywayButton.isHidden = true
        let buttons = UIStackView(arrangedSubviews: [check, detailsButton, anywayButton, UIView()])
        buttons.spacing = 10
        return card(nil, [row, buttons])
    }

    private func findSection() -> UIView {
        let find = Theme.glassButton(L10n.text("Look again"), symbol: "magnifyingglass")
        find.accessibilityIdentifier = "gamefiles.search"
        find.addAction(UIAction { [weak self] _ in self?.lookInAppFolder() }, for: .touchUpInside)
        let pick = Theme.glassButton(L10n.text("Choose a folder…"), symbol: "folder")
        pick.addAction(UIAction { [weak self] _ in self?.pickFolder() }, for: .touchUpInside)
        let buttons = UIStackView(arrangedSubviews: [find, pick, UIView()])
        buttons.spacing = 10
        return card(L10n.text("Already on this iPhone"), [
            note("In Files, place your unpacked game or archive in On My iPhone › ZGTA V. The app searches accessible subfolders and checks any game it finds."),
            note("Somewhere else? Choose the folder containing your game or archive. If a broad search misses it, choose a folder closer to the files."),
            buttons
        ])
    }

    private func linkSection() -> UIView {
        linkField.placeholder = "https://…"
        linkField.text = GameSettings.shared.assetServer
        linkField.keyboardType = .URL
        linkField.autocapitalizationType = .none
        linkField.autocorrectionType = .no
        linkField.returnKeyType = .go
        linkField.clearButtonMode = .whileEditing
        linkField.delegate = self
        linkField.textColor = Theme.text
        linkField.font = Theme.body(16)
        linkField.backgroundColor = UIColor(white: 1, alpha: 0.08)
        linkField.layer.cornerRadius = 12
        linkField.layer.cornerCurve = .continuous
        linkField.leftView = UIView(frame: CGRect(x: 0, y: 0, width: 12, height: 1))
        linkField.leftViewMode = .always
        linkField.heightAnchor.constraint(equalToConstant: 46).isActive = true
        linkField.accessibilityLabel = L10n.text("Link to your game files")
        linkButton.addAction(UIAction { [weak self] _ in self?.useLink() }, for: .touchUpInside)
        return card(L10n.text("From a link"), [
            note("Paste a direct link to your game archive (zip or rar): the app downloads it, unpacks it as it goes, checks every file and deletes the archive. It needs about \(GameFiles.Report.size(Self.gameBytes)) free, not double. Keep the app open while it works."),
            note(L10n.text("A download page where you tap Download first works too: it opens here in a browser, and the app takes the download over.")),
            note(L10n.text("Or the address of your own game server (for example your computer over Tailscale): the game then streams its files from there.")),
            linkField, linkButton
        ])
    }

    private func archiveSection() -> UIView {
        archivesStack.axis = .vertical
        archivesStack.spacing = 8
        let pick = Theme.glassButton(L10n.text("Choose an archive…"), symbol: "doc.zipper")
        pick.addAction(UIAction { [weak self] _ in self?.pickArchive() }, for: .touchUpInside)
        let buttons = UIStackView(arrangedSubviews: [pick, UIView()])
        return card(L10n.text("From an archive in Files"), [
            note(L10n.text("Got a .zip or .rar of the game (or all parts of a multi-part one) in Files? The app unpacks it straight into its own folder and checks every file. No separate unzip app needed.")),
            archivesStack, buttons
        ])
    }

    private func progressSection() -> UIView {
        progressTitle.font = Theme.body(16, .semibold)
        progressTitle.textColor = Theme.text
        progressDetail.font = .monospacedDigitSystemFont(ofSize: 13, weight: .regular)
        progressDetail.textColor = Theme.secondaryText
        progressDetail.numberOfLines = 0
        progressBar.progressTintColor = Theme.accent
        progressBar.trackTintColor = UIColor(white: 1, alpha: 0.12)
        cancelButton.addAction(UIAction { [weak self] _ in self?.install.cancel() }, for: .touchUpInside)
        let buttons = UIStackView(arrangedSubviews: [cancelButton, UIView()])
        let inner = UIStackView(arrangedSubviews: [progressTitle, progressBar, progressDetail, buttons])
        inner.axis = .vertical
        inner.spacing = 10
        fill(progressPanel, with: inner)
        progressPanel.isHidden = true
        return progressPanel
    }

    // MARK: State

    /// Shows the files in use (checking every one when asked) and any archives seen.
    private func refresh(recheck: Bool) {
        searchGeneration += 1
        let generation = searchGeneration
        setStatus(nil, title: "Checking your game files…", detail: "")
        searchQueue.async {
            let found = GameFolder.refreshSearch()
            let report = found && recheck ? GameFolder.checkChosen() : nil
            DispatchQueue.main.async {
                guard generation == self.searchGeneration else { return }
                self.show(report: report, found: found)
            }
        }
    }

    private func show(report: GameFiles.Report?, found: Bool) {
        lastReport = report ?? GameFolder.appFolderReport
        let server = GameSettings.shared.assetServer
        if let report, found {
            if report.isComplete {
                setStatus(true, title: "Ready to play", detail: "\"\(GameFolder.name)\" \(GameFolder.inAppFolder ? "in the ZGTA V folder" : "on this iPhone"): all \(report.fileCount) game files checked (\(GameFiles.Report.size(report.totalBytes))).")
            } else {
                // In use with problems: the player chose Play anyway for this folder.
                setStatus(true, title: "Ready, with \(report.problems.count) problem \(report.problems.count == 1 ? "file" : "files")", detail: "You chose to play anyway. " + report.explanation.message)
            }
        } else if found {
            setStatus(true, title: "Ready to play", detail: "\"\(GameFolder.name)\" on this iPhone.")
        } else if let problem = GameFolder.appFolderReport {
            let explanation = problem.explanation
            setStatus(false, title: explanation.title, detail: "The folder \"\(problem.data.lastPathComponent)\" is incomplete. " + explanation.message)
        } else if !server.isEmpty {
            setStatus(true, title: L10n.text("Streaming from your server"), detail: server)
        } else if lookedAgain {
            setStatus(false, title: "No complete game found", detail: "Choose the folder containing your unpacked game or archive. The app searches accessible subfolders. If it is not found, choose a folder closer to the game; other apps and cloud providers may require a fresh permission grant.")
        } else {
            setStatus(nil, title: "No game files yet", detail: "Use one of the ways below. Whichever you choose, the app checks every file before you play.")
        }
        lookedAgain = false
        detailsButton.isHidden = lastReport?.isComplete ?? true
        anywayButton.isHidden = found || !(lastReport.map(GameFolder.playAnywayAllowed) ?? false)
        showArchives()
        onChange?()
    }

    private func setStatus(_ ok: Bool?, title: String, detail: String) {
        statusTitle.text = L10n.text(title)
        statusDetail.text = L10n.text(detail)
        statusDetail.isHidden = detail.isEmpty
        statusIcon.image = UIImage(systemName: ok == true ? "checkmark.circle.fill" : ok == false ? "exclamationmark.triangle.fill" : "folder.badge.questionmark")
        statusIcon.tintColor = ok == true ? Theme.ok : ok == false ? Theme.problem : Theme.warning
    }

    private func showArchives() {
        archivesStack.arrangedSubviews.forEach { $0.removeFromSuperview() }
        // Each button captures the archive and its original directory grant as
        // one value. A later search cannot turn this into an unscoped file open.
        let candidates = GameFolder.archiveCandidates
        for candidate in candidates {
            let archive = candidate.url
            let root = candidate.accessRoot
            let scoped = root.startAccessingSecurityScopedResource()
            let size = (try? archive.resourceValues(forKeys: [.fileSizeKey]).fileSize).map { GameFiles.Report.size(UInt64($0)) } ?? ""
            if scoped { root.stopAccessingSecurityScopedResource() }
            let source: GameInstallSource = candidate.ownedByApp
                ? .file(archive, ownedByApp: true)
                : .fileInFolder(archive, folder: root)
            let button = Theme.glassButton("Unpack \(archive.lastPathComponent) (\(size))", symbol: "archivebox")
            button.accessibilityIdentifier = "gamefiles.archive.\(archive.lastPathComponent)"
            button.contentHorizontalAlignment = .leading
            button.addAction(UIAction { [weak self] _ in self?.startInstall(source) }, for: .touchUpInside)
            archivesStack.addArrangedSubview(button)
        }
        archivesStack.isHidden = GameFolder.archivesFound.isEmpty
    }

    private func confirmPlayAnyway() {
        guard let report = lastReport else { return }
        let alert = UIAlertController(title: "Play with \(report.problems.count) problem \(report.problems.count == 1 ? "file" : "files")?", message: "The game starts, but it may crash or show missing things wherever it needs those files. Fixing the folder (unpacking again) is the real cure.", preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: L10n.text("Cancel"), style: .cancel))
        alert.addAction(UIAlertAction(title: "Play anyway", style: .destructive) { [weak self] _ in
            guard let self else { return }
            self.searchQueue.async {
                let ok = GameFolder.playAnyway(report)
                DispatchQueue.main.async {
                    if ok {
                        self.setStatus(true, title: "Ready, with \(report.problems.count) problem \(report.problems.count == 1 ? "file" : "files")", detail: "You chose to play anyway. The game may crash where it needs them.")
                        self.anywayButton.isHidden = true
                        self.onChange?()
                    } else {
                        self.setStatus(false, title: "Couldn't use that folder", detail: "Try choosing it again.")
                    }
                }
            }
        })
        present(alert, animated: true)
    }

    private func showDetails() {
        guard let report = lastReport else { return }
        let text = UITextView()
        text.text = report.explanation.message + "\n\nEvery problem:\n" + report.details
        text.isEditable = false
        text.font = .monospacedSystemFont(ofSize: 12, weight: .regular)
        text.textColor = Theme.text
        text.backgroundColor = Theme.night
        let controller = UIViewController()
        controller.title = "\(report.problems.count) problems"
        controller.view = text
        controller.navigationItem.rightBarButtonItem = UIBarButtonItem(systemItem: .action, primaryAction: UIAction { [weak controller] _ in
            let share = UIActivityViewController(activityItems: [text.text ?? ""], applicationActivities: nil)
            share.popoverPresentationController?.barButtonItem = controller?.navigationItem.rightBarButtonItem
            controller?.present(share, animated: true)
        })
        navigationController?.pushViewController(controller, animated: true)
    }

    // MARK: Finding

    private var lookedAgain = false
    private func lookInAppFolder() {
        lookedAgain = true
        refresh(recheck: true)
    }

    private func pickFolder() {
        pickingArchive = false
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.folder])
        picker.delegate = self
        present(picker, animated: true)
    }

    private func pickArchive() {
        pickingArchive = true
        let types = ["zip", "rar", "tar", "gz", "tgz", "001"].compactMap { UTType(filenameExtension: $0) } + [.zip, .archive]
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: types, asCopy: false)
        picker.allowsMultipleSelection = true
        picker.delegate = self
        present(picker, animated: true)
    }

    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        if pickingArchive {
            let parts = urls.sorted { $0.lastPathComponent.localizedStandardCompare($1.lastPathComponent) == .orderedAscending }
            guard let first = parts.first else { return }
            startInstall(parts.count > 1 ? .parts(parts) : .file(first, ownedByApp: GameFolder.ownsFile(first)))
            return
        }
        guard let folder = urls.first else { return }
        searchGeneration += 1
        let generation = searchGeneration
        setStatus(nil, title: "Searching \"\(folder.lastPathComponent)\"…", detail: L10n.text("Looking through every folder inside for your game, then checking each file."))
        searchQueue.async {
            let choice = GameFolder.choose(folder)
            DispatchQueue.main.async {
                guard generation == self.searchGeneration else { return }
                switch choice {
                case let .accepted(report): self.show(report: report, found: true)
                case let .incomplete(report):
                    self.lastReport = report
                    let explanation = report.explanation
                    self.setStatus(false, title: explanation.title, detail: "Found the game in \"\(report.data.deletingLastPathComponent().lastPathComponent)\", but it can't be used yet. " + explanation.message)
                    self.detailsButton.isHidden = false
                    self.anywayButton.isHidden = !GameFolder.playAnywayAllowed(report)
                    self.showArchives()
                case let .archivesOnly(archives):
                    self.lastReport = nil
                    self.detailsButton.isHidden = true
                    self.anywayButton.isHidden = true
                    self.setStatus(nil, title: "Found an archive", detail: "\(archives[0].lastPathComponent) is not unpacked. Tap Unpack below to check and install its game files.")
                    self.showArchives()
                case let .refused(message):
                    self.lastReport = nil
                    self.detailsButton.isHidden = true
                    self.anywayButton.isHidden = true
                    self.setStatus(false, title: "No game in that folder", detail: message)
                    self.showArchives()
                }
            }
        }
    }

    // MARK: Link

    func textFieldShouldReturn(_ textField: UITextField) -> Bool { useLink(); return true }

    /// A game server answers with the game's file list; anything else is treated as an archive download.
    private func useLink() {
        linkField.resignFirstResponder()
        var text = (linkField.text ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        if !text.contains("://") { text = "https://" + text }
        guard let url = URL(string: text), let scheme = url.scheme?.lowercased(), ["http", "https"].contains(scheme), url.host != nil else {
            setStatus(false, title: "That isn't a web link", detail: "Paste the full link, starting with https://")
            return
        }
        setStatus(nil, title: "Checking the link…", detail: text)
        // A link to an archive file is always an install (some file hosts answer "OK" to any path).
        let archiveName = url.lastPathComponent.lowercased()
        if [".zip", ".rar", ".7z", ".001"].contains(where: archiveName.hasSuffix) || archiveName.range(of: #"\.(z|r)\d\d$"#, options: .regularExpression) != nil {
            startInstall(.url(url))
            return
        }
        // Otherwise it's a game server only if it really serves the game's file list.
        var server = text
        while server.hasSuffix("/") { server.removeLast() }
        var request = URLRequest(url: URL(string: server + "/data/manifest.json")!, timeoutInterval: 10)
        request.setValue("bytes=0-65535", forHTTPHeaderField: "Range")
        URLSession.shared.dataTask(with: request) { [weak self] data, response, _ in
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            let head = data.flatMap { String(data: $0.prefix(4096), encoding: .utf8) } ?? ""
            let isGameList = (code == 200 || code == 206) && head.trimmingCharacters(in: .whitespacesAndNewlines).hasPrefix("{") && head.contains("\"files\"")
            DispatchQueue.main.async {
                guard let self else { return }
                if isGameList {
                    self.onServer?(server)
                    self.setStatus(true, title: L10n.text("Streaming from your server"), detail: "\(server) answers with the game's file list. The game reads its files from there while you play.")
                    self.onChange?()
                } else {
                    self.openOrInstall(url)
                }
            }
        }.resume()
    }

    /// A direct file link is installed; a web page (a download portal) opens in the download
    /// browser, which hands over the file when the page starts it.
    private func openOrInstall(_ url: URL) {
        var request = URLRequest(url: url, timeoutInterval: 15)
        request.setValue("bytes=0-1023", forHTTPHeaderField: "Range")
        URLSession.shared.dataTask(with: request) { [weak self] _, response, _ in
            let type = response?.mimeType?.lowercased() ?? ""
            DispatchQueue.main.async {
                guard let self else { return }
                if type.contains("html") { self.openBrowser(url) } else { self.startInstall(.url(url)) }
            }
        }.resume()
    }

    private func openBrowser(_ url: URL) {
        setStatus(nil, title: L10n.text("That link is a web page"), detail: L10n.text("Use the page's download button in the browser; the app takes over the download."))
        let browser = DownloadBrowserViewController(url: url)
        browser.onDownload = { [weak self] file, headers in self?.startInstall(.url(file, headers: headers)) }
        let navigation = UINavigationController(rootViewController: browser)
        Theme.styleNavigation(navigation)
        navigation.modalPresentationStyle = .fullScreen
        present(navigation, animated: true)
    }

    // MARK: Installing

    static var gameBytes: UInt64 { GameFiles.manifest.reduce(0) { $0 + $1.1 } }

    private func startInstall(_ source: GameInstallSource, confirmed: Bool = false) {
        guard !install.isRunning else { return }
        if case let .file(url, true) = source, !confirmed {
            let alert = UIAlertController(title: "Unpack \(url.lastPathComponent)?", message: "Keep the archive and unpack the game using about \(GameFiles.Report.size(Self.gameBytes)) of additional space. The optional space-saving mode removes archive data while unpacking; if interrupted, it needs a fresh archive.", preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: L10n.text("Cancel"), style: .cancel))
            let keep = UIAlertAction(title: "Unpack and keep archive", style: .default) { [weak self] _ in self?.startInstall(.file(url, ownedByApp: false), confirmed: true) }
            alert.addAction(keep)
            alert.preferredAction = keep
            alert.addAction(UIAlertAction(title: "Use archive space (removes archive)", style: .destructive) { [weak self] _ in self?.startInstall(source, confirmed: true) })
            present(alert, animated: true)
            return
        }
        // Installing replaces streaming: a link saved as a game server earlier is forgotten.
        if !GameSettings.shared.assetServer.isEmpty { GameSettings.shared.assetServer = ""; onChange?() }
        progressPanel.isHidden = false
        progressTitle.text = "Starting…"
        progressDetail.text = ""
        progressBar.progress = 0
        // The status card at the top follows the install too, and the progress comes into view.
        setStatus(nil, title: "Getting your game files…", detail: "Downloading and unpacking. Keep the app open; progress is shown below.")
        DispatchQueue.main.async {
            guard let scroll = self.stack.superview as? UIScrollView else { return }
            scroll.scrollRectToVisible(scroll.convert(self.progressPanel.bounds, from: self.progressPanel).insetBy(dx: 0, dy: -20), animated: true)
        }
        UIApplication.shared.isIdleTimerDisabled = true
        install.start(source, to: Self.installFolder)
    }

    /// Shows the shared install's state (it keeps running while this screen is closed).
    @objc private func installChanged() {
        switch install.state {
        case .idle:
            break
        case let .running(update):
            progressPanel.isHidden = false
            cancelButton.isHidden = false
            progressTitle.text = update.title
            progressDetail.text = update.detail
            progressBar.setProgress(Float(update.fraction), animated: true)
            setStatus(nil, title: update.title, detail: update.detail.split(separator: "\n").first.map(String.init) ?? "")
        case let .finished(result):
            install.acknowledge()
            switch result {
            case .success:
                progressPanel.isHidden = false
                progressTitle.text = "Done: every game file unpacked and checked"
                progressDetail.text = ""
                progressBar.progress = 1
                cancelButton.isHidden = true
                refresh(recheck: true)
            case let .failure(message):
                progressPanel.isHidden = false
                progressTitle.text = "Couldn't finish"
                progressDetail.text = message
                cancelButton.isHidden = true
                setStatus(false, title: "Couldn't get the game files", detail: message)
            case let .webPage(url):
                progressPanel.isHidden = true
                openBrowser(url)
            }
        }
    }

    // MARK: Layout helpers

    private func card(_ title: String?, _ views: [UIView]) -> UIView {
        let panel = Theme.panel()
        var items = views
        if let title {
            let label = UILabel()
            label.text = L10n.text(title)
            label.font = Theme.display(18, .bold)
            label.textColor = Theme.text
            items.insert(label, at: 0)
        }
        let inner = UIStackView(arrangedSubviews: items)
        inner.axis = .vertical
        inner.spacing = 10
        inner.alignment = .fill
        fill(panel, with: inner)
        return panel
    }
    private func note(_ text: String) -> UILabel {
        let label = UILabel()
        label.text = L10n.text(text)
        label.font = Theme.body(14)
        label.textColor = Theme.secondaryText
        label.numberOfLines = 0
        return label
    }
    private func fill(_ panel: UIVisualEffectView, with content: UIView) {
        content.translatesAutoresizingMaskIntoConstraints = false
        panel.contentView.addSubview(content)
        NSLayoutConstraint.activate([
            content.leadingAnchor.constraint(equalTo: panel.contentView.leadingAnchor, constant: 18),
            content.trailingAnchor.constraint(equalTo: panel.contentView.trailingAnchor, constant: -18),
            content.topAnchor.constraint(equalTo: panel.contentView.topAnchor, constant: 16),
            content.bottomAnchor.constraint(equalTo: panel.contentView.bottomAnchor, constant: -16)
        ])
    }
    /// Closing is fine while an install runs: it carries on, and the start screen shows its progress.
    private func close() {
        dismiss(animated: true)
    }
}
