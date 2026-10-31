import UIKit

/// Live advertisements and explicit favorites on private-network hosts.
final class LobbyBrowserViewController: UITableViewController {
    var onJoin: ((LobbyRecord) -> Void)?
    private let picker = UISegmentedControl(items: ["Same Wi-Fi / LAN", "Remote / Tailscale"])
    private let category = UISegmentedControl(items: ["Online", "♥ Favorites"])
    private let status = UILabel()
    private let discovery = LobbyLANDiscovery()
    private var mode = EngineLanPreferences.selected()
    private var model = LobbyBrowserModel()
    private var rows: [LobbyBrowserEntry] = []
    private var probes: [String: LobbyHealthProbe] = [:]
    private var pending: [LobbyRecord] = []
    private var nearby = Set<String>()
    private var discoveryMessage: String?
    private var refreshTimer: Timer?
    private var generation = 0
    private var observers: [NSObjectProtocol] = []
    init() { super.init(style: .insetGrouped) }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    override func viewDidLoad() {
        super.viewDidLoad(); title = "Find lobbies"
        view.backgroundColor = Theme.night; tableView.backgroundColor = Theme.night
        tableView.rowHeight = UITableView.automaticDimension; tableView.estimatedRowHeight = 100
        tableView.accessibilityIdentifier = "lobby.list"
        navigationItem.leftBarButtonItem = UIBarButtonItem(barButtonSystemItem: .done, target: self, action: #selector(done))
        let addButton = UIBarButtonItem(barButtonSystemItem: .add, target: self, action: #selector(add))
        addButton.accessibilityLabel = "Add favorite"
        navigationItem.rightBarButtonItems = [addButton, UIBarButtonItem(barButtonSystemItem: .refresh, target: self, action: #selector(refresh))]
        picker.selectedSegmentIndex = mode == .lan ? 0 : 1
        picker.addTarget(self, action: #selector(changeMode), for: .valueChanged)
        category.selectedSegmentIndex = 0; category.accessibilityIdentifier = "lobby.filter"
        category.addTarget(self, action: #selector(changeCategory), for: .valueChanged)
        for control in [picker, category] { control.selectedSegmentTintColor = Theme.accent; control.setTitleTextAttributes([.foregroundColor: Theme.night], for: .selected) }
        let header = UIStackView(arrangedSubviews: [picker, category, status]); header.axis = .vertical; header.spacing = 13
        header.layoutMargins = UIEdgeInsets(top: 16, left: 20, bottom: 15, right: 20); header.isLayoutMarginsRelativeArrangement = true
        status.font = Theme.body(12); status.textColor = Theme.secondaryText; status.numberOfLines = 0
        header.frame = CGRect(x: 0, y: 0, width: tableView.bounds.width, height: 150); tableView.tableHeaderView = header
        discovery.onStatus = { [weak self] message in
            guard let self, self.mode == .lan else { return }
            self.discoveryMessage = message; self.reloadRows()
        }
        discovery.found = { [weak self] address in
            guard let self, self.mode == .lan, self.nearby.count < 8,
                  self.nearby.insert(address).inserted, let record = LobbyRecord.parse(address),
                  self.model.addCandidate(record) else { return }
            self.pending.append(record); self.reloadRows(); self.pump()
        }
        observers.append(NotificationCenter.default.addObserver(forName: UIApplication.didEnterBackgroundNotification, object: nil, queue: .main) { [weak self] _ in self?.refreshTimer?.invalidate(); self?.refreshTimer = nil; self?.stop() })
        observers.append(NotificationCenter.default.addObserver(forName: UIApplication.didBecomeActiveNotification, object: nil, queue: .main) { [weak self] _ in guard let self, self.viewIfLoaded?.window != nil else { return }; self.refresh(); self.scheduleRefresh() })
        refresh()
    }
    override func viewDidAppear(_ animated: Bool) { super.viewDidAppear(animated); scheduleRefresh() }
    private func scheduleRefresh() {
        refreshTimer?.invalidate()
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 15, repeats: true) { [weak self] _ in
            guard let self, self.viewIfLoaded?.window != nil, self.presentedViewController == nil else { return }
            self.reloadRows() // Expire stale results even while a batch is running.
            if self.probes.isEmpty && self.pending.isEmpty { self.refresh() }
        }
    }
    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        if let header = tableView.tableHeaderView {
            let size = header.systemLayoutSizeFitting(CGSize(width: tableView.bounds.width, height: UIView.layoutFittingCompressedSize.height), withHorizontalFittingPriority: .required, verticalFittingPriority: .fittingSizeLevel)
            if abs(size.height - header.frame.height) > 1 { header.frame.size.height = size.height; tableView.tableHeaderView = header }
        }
    }
    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        if isBeingDismissed || navigationController?.isBeingDismissed == true { refreshTimer?.invalidate(); refreshTimer = nil; stop() }
    }
    @objc private func done() { refreshTimer?.invalidate(); refreshTimer = nil; stop(); dismiss(animated: true) }
    private func stop() { generation += 1; discovery.stop(); for probe in probes.values { probe.cancel() }; probes.removeAll(); pending.removeAll() }
    @objc private func changeMode() { mode = picker.selectedSegmentIndex == 0 ? .lan : .remote; refresh() }
    @objc private func changeCategory() { reloadRows() }
    @objc private func refresh() {
        stop(); nearby.removeAll(); discoveryMessage = nil
        // History and the saved connection are probe seeds, never online results.
        // Do not invent a host at this phone's current IP address.
        var records = LobbyFavorites.load() + LobbyHistory.load()
        let saved = EngineLanPreferences.load(mode: mode)
        if let record = LobbyRecord.parse(saved.relay, room: saved.room) { records.append(record) }
        records += model.entries.map(\.record)
        pending = model.begin(records: records.filter { $0.connection == mode })
        reloadRows()
        if mode == .lan { discovery.start() }; pump()
    }
    private func reloadRows() {
        let favorites = LobbyFavorites.load()
        rows = model.visible(favorites: favorites, onlyFavorites: category.selectedSegmentIndex == 1, mode: mode)
        let count = model.visible(favorites: favorites, onlyFavorites: false, mode: mode).count
        let checking = !probes.isEmpty || !pending.isEmpty
        status.text = "\(count) online lobb\(count == 1 ? "y" : "ies")" + (checking ? " · Checking hosts… " : " · Live host responses only. ") + (mode == .lan ? "Nearby hosts appear on the same Wi-Fi." : "Remote checks your invites over Tailscale.")
        if mode == .lan, let discoveryMessage { status.text = (status.text ?? "") + "\n" + discoveryMessage }
        tableView.reloadData()
    }
    private func pump() {
        while probes.count < 4, !pending.isEmpty {
            let record = pending.removeFirst(), attempt = generation, relay = record.relay
            guard probes[relay] == nil else { continue }
            probes[relay] = LobbyHealthProbe(record: record) { [weak self] health in
                guard let self, self.generation == attempt else { return }
                self.probes.removeValue(forKey: relay); self.model.receive(relay: relay, health: health)
                self.pump()
            }
        }
        reloadRows()
    }
    @objc private func add() {
        let alert = UIAlertController(title: "Add favorite", message: "Paste a friend’s ZGTA V invite or private host address. Favorites stay saved when a host is offline.", preferredStyle: .alert)
        alert.addTextField { $0.placeholder = "Host address or zgtav://join?…"; $0.autocapitalizationType = .none; $0.autocorrectionType = .no }
        alert.addTextField { $0.placeholder = "Room"; $0.text = "LOS-SANTOS"; $0.autocapitalizationType = .allCharacters }
        alert.addAction(UIAlertAction(title: "Save to Favorites", style: .default) { [weak self, weak alert] _ in
            guard let self, let fields = alert?.textFields, fields.count == 2,
                  let record = LobbyRecord.parse(fields[0].text ?? "", room: fields[1].text ?? "") else { self?.message("That invite is not valid. Use a private Wi-Fi/Tailscale address and a room name."); return }
            guard LobbyFavorites.set(record, saved: true) else { self.message("Favorites is full. Remove a favorite before adding another."); return }
            self.mode = record.connection; self.picker.selectedSegmentIndex = self.mode == .lan ? 0 : 1
            self.category.selectedSegmentIndex = 1; self.refresh()
        })
        alert.addAction(UIAlertAction(title: "Cancel", style: .cancel)); present(alert, animated: true)
    }
    private func message(_ text: String) { let alert = UIAlertController(title: "Multiplayer", message: text, preferredStyle: .alert); alert.addAction(UIAlertAction(title: "OK", style: .default)); present(alert, animated: true) }
    override func numberOfSections(in tableView: UITableView) -> Int { 1 }
    override func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int { max(1, rows.count) }
    override func tableView(_ tableView: UITableView, titleForFooterInSection section: Int) -> String? {
        "Tap a heart to save or remove a favorite. Only advertised live rooms appear in Online. Favorites can stay offline; joining checks availability. Selecting a lobby prepares it; the green Play button starts the game."
    }
    override func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let cell = UITableViewCell(style: .subtitle, reuseIdentifier: nil)
        cell.backgroundColor = Theme.rowBackground; cell.textLabel?.textColor = Theme.text
        cell.detailTextLabel?.textColor = Theme.secondaryText; cell.detailTextLabel?.numberOfLines = 0; cell.detailTextLabel?.font = Theme.body(12)
        guard !rows.isEmpty else {
            cell.textLabel?.text = category.selectedSegmentIndex == 1 ? "No favorites yet" : "No online lobbies"
            cell.detailTextLabel?.text = category.selectedSegmentIndex == 1 ? "Save a lobby with its heart, or use + to add an invite." : "Start a host on this Wi-Fi, or save a friend’s invite with +. Offline hosts stay out of this list."
            cell.selectionStyle = .none; return cell
        }
        let row = rows[indexPath.row], now = Date(), saved = LobbyFavorites.contains(row.record)
        cell.accessibilityIdentifier = "lobby." + row.record.relay + "#" + row.record.room
        cell.textLabel?.text = row.record.room
        var detail = row.state(at: now)
        if row.hostOnline(at: now), let health = row.health {
            if let room = row.room { detail += " · \(room.players)/\(room.capacity) players"; if room.slots >= room.capacity { detail += " · Full or players reconnecting" } }
            detail += " · \(health.latency) ms response"
        }
        cell.detailTextLabel?.text = detail + "\n" + row.record.relay
        cell.imageView?.image = UIImage(systemName: row.listedOnline(at: now) ? "person.2.fill" : "network")
        cell.imageView?.tintColor = row.listedOnline(at: now) ? Theme.accent : Theme.secondaryText
        let heart = UIButton(type: .system); heart.frame = CGRect(x: 0, y: 0, width: 44, height: 44)
        heart.setImage(UIImage(systemName: saved ? "heart.fill" : "heart"), for: .normal); heart.tintColor = Theme.accent
        heart.accessibilityLabel = saved ? "Remove \(row.record.room) from Favorites" : "Add \(row.record.room) to Favorites"
        heart.addAction(UIAction { [weak self] _ in
            guard LobbyFavorites.set(row.record, saved: !saved) else { self?.message("Favorites is full. Remove a favorite before adding another."); return }
            self?.reloadRows()
        }, for: .touchUpInside)
        cell.accessoryView = heart
        return cell
    }
    override func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
        tableView.deselectRow(at: indexPath, animated: true); guard !rows.isEmpty else { return }
        let row = rows[indexPath.row]
        guard row.canJoin(at: Date()) else { message("This lobby is unavailable. Open the host game/relay, check the connection, then Refresh. An offline favorite stays saved."); return }
        if let room = row.room, room.slots >= room.capacity { message("This lobby is full, or its players are reconnecting. Try again shortly."); return }
        LobbyHistory.remember(row.record); let selected = onJoin
        refreshTimer?.invalidate(); refreshTimer = nil; stop(); dismiss(animated: true) { selected?(row.record) }
    }
    deinit { refreshTimer?.invalidate(); for observer in observers { NotificationCenter.default.removeObserver(observer) }; discovery.stop(); for probe in probes.values { probe.cancel() } }
}

enum LobbyBrowserPresenter {
    static func present(from controller: UIViewController, selected: @escaping (LobbyRecord) -> Void) {
        let browser = LobbyBrowserViewController(); browser.onJoin = selected
        let navigation = UINavigationController(rootViewController: browser); Theme.styleNavigation(navigation)
        controller.present(navigation, animated: true)
    }
}
