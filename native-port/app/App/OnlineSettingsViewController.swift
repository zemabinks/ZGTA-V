import UIKit
import Darwin

enum OnlineSettings {
    private static let preferences = OnlinePreferences()
    static var enabled: Bool {
        get { preferences.enabled }
        set { preferences.enabled = newValue }
    }
    static var server: String {
        get { preferences.server }
        set { preferences.server = newValue }
    }
    static var name: String {
        get { preferences.name }
        set { preferences.name = newValue }
    }
    static var room: String {
        get { preferences.room }
        set { preferences.room = newValue }
    }
    static let roles = OnlinePreferences.roles
    static var role: String {
        get { preferences.role }
        set { preferences.role = newValue }
    }
    static var pvp: Bool {
        get { preferences.pvp }
        set { preferences.pvp = newValue }
    }
    static func configure(mode: GameMode) -> Bool {
        guard !enabled || OnlineInput.valid(server: server, name: name, room: room, role: role) else { return false }
        setenv("MUGUET_PVP", enabled && pvp ? "1" : "0", 1)
        let displayName = OnlinePreferences.wireName(name: name, role: role)
        return (enabled ? server : "").withCString { server in
            displayName.withCString { name in room.withCString { room in
                MugoatOnlineConfigure(server, name, room, Int32(mode.rawValue))
            } }
        }
    }
    static var status: String {
        var bytes = [CChar](repeating: 0, count: 512)
        bytes.withUnsafeMutableBufferPointer { _ = MugoatOnlineStatus($0.baseAddress, $0.count) }
        return L10n.text(String(cString: bytes))
    }
}

final class OnlineSettingsViewController: UIViewController {
    private let running: Bool
    private let enabled = UISwitch()
    private let rolePicker = UISegmentedControl(items: OnlineSettings.roles.map { L10n.text($0) })
    private let pvp = UISwitch()
    private let server = UITextField()
    private let name = UITextField()
    private let room = UITextField()
    private let status = UILabel()
    private var statusTimer: Timer?
    var changed: (() -> Void)?
    init(running: Bool) { self.running = running; super.init(nibName: nil, bundle: nil) }
    required init?(coder: NSCoder) { fatalError() }
    override func viewDidLoad() {
        super.viewDidLoad()
        title = L10n.text("Online server")
        view.backgroundColor = Theme.night
        enabled.isOn = OnlineSettings.enabled; enabled.isEnabled = !running
        let label = UILabel(); label.text = L10n.text("Play online"); label.textColor = Theme.text
        let toggle = UIStackView(arrangedSubviews: [label, enabled]); toggle.alignment = .center
        let roleLabel = UILabel(); roleLabel.text = L10n.text("Character role"); roleLabel.textColor = Theme.text
        roleLabel.font = Theme.body(14)
        rolePicker.selectedSegmentIndex = OnlineSettings.roles.firstIndex(of: OnlineSettings.role) ?? 0
        rolePicker.isEnabled = !running
        rolePicker.overrideUserInterfaceStyle = .dark
        pvp.isOn = OnlineSettings.pvp; pvp.isEnabled = !running
        let pvpLabel = UILabel(); pvpLabel.text = L10n.text("PvP: attack other players"); pvpLabel.textColor = Theme.text
        let pvpRow = UIStackView(arrangedSubviews: [pvpLabel, pvp]); pvpRow.alignment = .center
        server.text = OnlineSettings.server; server.placeholder = "IP / hostname:47520"; server.keyboardType = .URL
        name.text = OnlineSettings.name; name.placeholder = L10n.text("Player name")
        room.text = OnlineSettings.room; room.placeholder = L10n.text("Room")
        for field in [server, name, room] {
            field.borderStyle = .roundedRect; field.autocapitalizationType = .none
            field.autocorrectionType = .no; field.isEnabled = !running
            field.heightAnchor.constraint(equalToConstant: 44).isActive = true
        }
        let explanation = UILabel()
        explanation.text = L10n.text(running ? "Restart the app to change servers." : "Enter your local server's IPv4 address or hostname, optionally :47520. Use the same room and game mode on each device. This app uses UDP, not a ws:// browser server. Networking starts when you enter the game. Rooms containing -pvp enable PvP even when the switch is off; use a -peace room to disable it. Names, including role prefixes, must fit 24 characters and 48 UTF-8 bytes.")
        explanation.font = Theme.body(13); explanation.textColor = Theme.secondaryText; explanation.numberOfLines = 0
        status.text = running ? OnlineSettings.status : ""; status.textColor = Theme.accent; status.numberOfLines = 0
        let save = Theme.primaryButton(L10n.text("Save"), symbol: "checkmark")
        save.isEnabled = !running
        save.addAction(UIAction { [weak self] _ in self?.save() }, for: .touchUpInside)
        let column = UIStackView(arrangedSubviews: [toggle, roleLabel, rolePicker, server, name, room, pvpRow, explanation, status, save]); column.axis = .vertical; column.spacing = 16
        let scroll = UIScrollView(); scroll.keyboardDismissMode = .interactive
        scroll.translatesAutoresizingMaskIntoConstraints = false; view.addSubview(scroll)
        column.translatesAutoresizingMaskIntoConstraints = false; scroll.addSubview(column)
        NSLayoutConstraint.activate([
            scroll.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor), scroll.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor),
            scroll.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor), scroll.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor),
            column.topAnchor.constraint(equalTo: scroll.contentLayoutGuide.topAnchor, constant: 20), column.bottomAnchor.constraint(equalTo: scroll.contentLayoutGuide.bottomAnchor, constant: -20),
            column.leadingAnchor.constraint(equalTo: scroll.contentLayoutGuide.leadingAnchor, constant: 24), column.trailingAnchor.constraint(equalTo: scroll.contentLayoutGuide.trailingAnchor, constant: -24),
            column.widthAnchor.constraint(equalTo: scroll.frameLayoutGuide.widthAnchor, constant: -48)
        ])
        navigationItem.rightBarButtonItem = UIBarButtonItem(title: L10n.text("Close"), style: .done, target: self, action: #selector(close))
    }
    @objc private func close() { dismiss(animated: true) }
    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        if running { statusTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.status.text = OnlineSettings.status } }
    }
    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated); statusTimer?.invalidate(); statusTimer = nil
    }
    private func save() {
        let host = (server.text ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let player = (name.text ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let channel = (room.text ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let index = rolePicker.selectedSegmentIndex
        let selectedRole = OnlineSettings.roles.indices.contains(index) ? OnlineSettings.roles[index] : OnlineSettings.roles[0]
        guard !enabled.isOn || OnlineInput.valid(server: host, name: player, room: channel, role: selectedRole) else {
            let alert = UIAlertController(title: L10n.text("Invalid server"), message: L10n.text("Use IPv4 or a hostname with an optional port from 1 to 65535. Player name and room must be nonempty and contain no control characters. The name plus role prefix must fit 24 characters / 48 UTF-8 bytes; room: 64 UTF-8 bytes."), preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "OK", style: .default)); present(alert, animated: true); return
        }
        OnlineSettings.server = host; OnlineSettings.name = player; OnlineSettings.room = channel; OnlineSettings.enabled = enabled.isOn
        OnlineSettings.pvp = pvp.isOn
        let roleIdx = rolePicker.selectedSegmentIndex
        if OnlineSettings.roles.indices.contains(roleIdx) {
            OnlineSettings.role = OnlineSettings.roles[roleIdx]
        }
        changed?(); dismiss(animated: true)
    }
}
