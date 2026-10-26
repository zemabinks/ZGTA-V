import UIKit

/// Real controls for the approved launcher; game state stays in NativePortViewController.
final class HomeView: UIView {
    enum FilesState { case ready, attention, problem, busy }
    private enum Page { case home, solo, friends }

    let playButton = Theme.primaryButton(L10n.text("Play"), symbol: "play.fill")
    let multiplayerPlayButton = Theme.primaryButton(L10n.text("Play multiplayer"), symbol: "play.fill")
    let modButton = Theme.primaryButton(L10n.text("Open Mods"), symbol: "puzzlepiece.fill")
    let settingsButton = Theme.glassButton("", symbol: "gearshape.fill")
    let layoutButton = Theme.glassButton(L10n.text("Controls layout"), symbol: "hand.tap.fill")
    let saveButton = Theme.glassButton(L10n.text("Save game"), symbol: "externaldrive.fill")
    let preloadLabel = UILabel()
    let controllerLabel = UILabel()
    var onFiles: (() -> Void)?
    var onMode: ((Int) -> Void)?
    var onMap: ((Int) -> Void)?
    var multiplayerAction: ((String) -> Void)?

    private let filesCard = UIControl()
    private let filesIcon = UIImageView()
    private let filesLabel = UILabel()
    private let filesSpinner = UIActivityIndicatorView(style: .medium)
    private let homeBody = UIStackView()
    private let soloBody = UIStackView()
    private let friendsBody = UIStackView()
    private let multiplayerHome = UIStackView()
    private let multiplayerDetail = UILabel()
    private var multiplayerCards: [PureBlackModeCard] = []
    private let modeDetail = UILabel()
    private var modeCards: [PureBlackModeCard] = []
    private var cardHeight: NSLayoutConstraint!
    private let headline = UILabel()
    private var headingRow: UIView!
    private let homeScroll = UIScrollView()
    private let content = UIStackView()
    private var visibleBody: UIStackView?

    override func layoutSubviews() {
        super.layoutSubviews()
        // Card artwork must never determine the scroll content height.
        // Fit the whole composition into the available landscape safe area.
        let height = bounds.inset(by: safeAreaInsets).height
        let compact = height < 340
        cardHeight.constant = compact ? 100 : 112
        content.spacing = compact ? 12 : 16
        homeBody.spacing = compact ? 8 : 12
        homeBody.setCustomSpacing(compact ? 8 : 18, after: headingRow)
        headline.font = Theme.display(compact ? 28 : 32, .bold)
    }

    init(modes: [(title: String, symbol: String)], log: UIView) {
        super.init(frame: .zero)
        backgroundColor = Theme.night
        pin(Theme.backdrop(image: "LosSantosMap"))
        let scroll = homeScroll
        scroll.showsVerticalScrollIndicator = false
        scroll.translatesAutoresizingMaskIntoConstraints = false
        addSubview(scroll)
        content.axis = .vertical
        content.spacing = 16
        content.translatesAutoresizingMaskIntoConstraints = false
        scroll.addSubview(content)
        let guide = safeAreaLayoutGuide
        NSLayoutConstraint.activate([
            scroll.leadingAnchor.constraint(equalTo: guide.leadingAnchor), scroll.trailingAnchor.constraint(equalTo: guide.trailingAnchor),
            scroll.topAnchor.constraint(equalTo: guide.topAnchor), scroll.bottomAnchor.constraint(equalTo: guide.bottomAnchor),
            content.leadingAnchor.constraint(equalTo: scroll.contentLayoutGuide.leadingAnchor, constant: 12),
            content.trailingAnchor.constraint(equalTo: scroll.contentLayoutGuide.trailingAnchor, constant: -12),
            content.topAnchor.constraint(equalTo: scroll.contentLayoutGuide.topAnchor, constant: 14),
            content.bottomAnchor.constraint(equalTo: scroll.contentLayoutGuide.bottomAnchor, constant: -14),
            content.widthAnchor.constraint(equalTo: scroll.frameLayoutGuide.widthAnchor, constant: -24)
        ])

        let mark = UIImageView(image: UIImage(named: "ZPlayMark"))
        mark.contentMode = .scaleAspectFit
        mark.widthAnchor.constraint(equalToConstant: 38).isActive = true
        mark.heightAnchor.constraint(equalToConstant: 38).isActive = true
        let brandTitle = UILabel(); brandTitle.text = "ZGTA V"; brandTitle.font = Theme.display(28, .bold); brandTitle.textColor = .white
        let byline = UILabel(); byline.text = "by zema"; byline.font = Theme.body(13, .semibold); byline.textColor = Theme.secondaryText
        let brand = UIStackView(arrangedSubviews: [mark, brandTitle, byline]); brand.spacing = 9; brand.alignment = .center
        filesIcon.widthAnchor.constraint(equalToConstant: 19).isActive = true
        filesLabel.font = Theme.body(13, .semibold); filesLabel.textColor = .white
        filesLabel.lineBreakMode = .byTruncatingTail
        filesSpinner.color = Theme.accent; filesSpinner.hidesWhenStopped = true
        let filesRow = UIStackView(arrangedSubviews: [filesIcon, filesSpinner, filesLabel])
        filesRow.spacing = 7; filesRow.alignment = .center; filesRow.isUserInteractionEnabled = false
        filesRow.translatesAutoresizingMaskIntoConstraints = false
        filesCard.addSubview(filesRow)
        NSLayoutConstraint.activate([
            filesRow.leadingAnchor.constraint(equalTo: filesCard.leadingAnchor, constant: 8),
            filesRow.trailingAnchor.constraint(equalTo: filesCard.trailingAnchor, constant: -8),
            filesRow.topAnchor.constraint(equalTo: filesCard.topAnchor), filesRow.bottomAnchor.constraint(equalTo: filesCard.bottomAnchor),
            filesCard.heightAnchor.constraint(greaterThanOrEqualToConstant: 44)
        ])
        filesCard.isAccessibilityElement = true; filesCard.accessibilityTraits = .button
        filesCard.addAction(UIAction { [weak self] _ in self?.onFiles?() }, for: .touchUpInside)
        settingsButton.configuration?.title = nil
        settingsButton.accessibilityLabel = L10n.text("Settings")
        settingsButton.widthAnchor.constraint(equalToConstant: 48).isActive = true
        settingsButton.heightAnchor.constraint(equalToConstant: 48).isActive = true
        let header = UIStackView(arrangedSubviews: [brand, UIView(), filesCard, settingsButton])
        header.spacing = 9; header.alignment = .center
        content.addArrangedSubview(header)

        homeBody.axis = .vertical; homeBody.spacing = 12
        headline.text = L10n.text("How do you want to play?")
        headline.font = Theme.display(32); headline.textColor = .white; headline.numberOfLines = 0
        headline.accessibilityIdentifier = "home.heading"
        headingRow = leadingBounded(headline, maximumWidth: 528)
        homeBody.addArrangedSubview(headingRow)
        homeBody.setCustomSpacing(18, after: headingRow)
        let soloCard = PureBlackChoiceCard(image: "SoloCard", symbol: "gamecontroller.fill", title: L10n.text("On my own"), detail: L10n.text("Story mode or free roam"))
        let friendsCard = PureBlackChoiceCard(image: "FriendsCard", symbol: "person.3.fill", title: L10n.text("With friends"), detail: L10n.text("Join a lobby or host your own"))
        soloCard.addAction(UIAction { [weak self] _ in self?.show(.solo) }, for: .touchUpInside)
        friendsCard.addAction(UIAction { [weak self] _ in self?.show(.friends) }, for: .touchUpInside)
        let cards = UIStackView(arrangedSubviews: [soloCard, friendsCard]); cards.spacing = 12; cards.distribution = .fillEqually
        cardHeight = soloCard.heightAnchor.constraint(equalToConstant: 112)
        cardHeight.isActive = true
        soloCard.accessibilityIdentifier = "home.solo"
        friendsCard.accessibilityIdentifier = "home.friends"
        friendsCard.heightAnchor.constraint(equalTo: soloCard.heightAnchor).isActive = true
        homeBody.addArrangedSubview(leadingBounded(cards, maximumWidth: 492))
        let modsPanel = UIView(); modsPanel.backgroundColor = Theme.surface.withAlphaComponent(0.94)
        modsPanel.layer.cornerRadius = 12; modsPanel.layer.borderWidth = 1; modsPanel.layer.borderColor = Theme.panelStroke.cgColor
        let modsIcon = UIImageView(image: UIImage(systemName: "folder.fill")); modsIcon.tintColor = .white
        modsIcon.contentMode = .scaleAspectFit
        modsIcon.widthAnchor.constraint(equalToConstant: 32).isActive = true
        modsIcon.heightAnchor.constraint(equalToConstant: 32).isActive = true
        let puzzle = UIImageView(image: UIImage(systemName: "puzzlepiece.fill"))
        puzzle.tintColor = Theme.night; puzzle.contentMode = .scaleAspectFit
        puzzle.translatesAutoresizingMaskIntoConstraints = false; modsIcon.addSubview(puzzle)
        NSLayoutConstraint.activate([puzzle.widthAnchor.constraint(equalToConstant: 19), puzzle.heightAnchor.constraint(equalToConstant: 19), puzzle.centerXAnchor.constraint(equalTo: modsIcon.centerXAnchor), puzzle.centerYAnchor.constraint(equalTo: modsIcon.centerYAnchor, constant: 3)])
        let modsTitle = UILabel(); modsTitle.text = L10n.text("Want to add mods?"); modsTitle.font = Theme.display(16, .bold); modsTitle.textColor = .white
        let modsHint = UILabel(); modsHint.text = L10n.text("Import a compatible pack from Files"); modsHint.font = Theme.body(12); modsHint.textColor = Theme.secondaryText; modsHint.numberOfLines = 0
        let modsCopy = UIStackView(arrangedSubviews: [modsTitle, modsHint]); modsCopy.axis = .vertical; modsCopy.spacing = 2
        modButton.accessibilityIdentifier = "home.mods"
        modButton.heightAnchor.constraint(greaterThanOrEqualToConstant: 44).isActive = true
        modButton.configuration?.contentInsets = NSDirectionalEdgeInsets(top: 11, leading: 14, bottom: 11, trailing: 14)
        modButton.configuration?.titleTextAttributesTransformer = UIConfigurationTextAttributesTransformer { attributes in
            var attributes = attributes; attributes.font = Theme.body(14, .bold); return attributes
        }
        modButton.configuration?.image = UIImage(systemName: "chevron.right")
        modButton.configuration?.imagePlacement = .trailing
        let modsRow = UIStackView(arrangedSubviews: [modsIcon, modsCopy, UIView(), modButton]); modsRow.spacing = 12; modsRow.alignment = .center
        modsRow.translatesAutoresizingMaskIntoConstraints = false; modsPanel.addSubview(modsRow)
        NSLayoutConstraint.activate([
            modsRow.leadingAnchor.constraint(equalTo: modsPanel.leadingAnchor, constant: 18),
            modsRow.trailingAnchor.constraint(equalTo: modsPanel.trailingAnchor, constant: -16),
            modsRow.topAnchor.constraint(equalTo: modsPanel.topAnchor, constant: 10),
            modsRow.bottomAnchor.constraint(equalTo: modsPanel.bottomAnchor, constant: -10),
            modsPanel.heightAnchor.constraint(greaterThanOrEqualToConstant: 63)
        ])
        modsPanel.accessibilityIdentifier = "home.modsPanel"
        homeBody.addArrangedSubview(leadingBounded(modsPanel, maximumWidth: 620))

        soloBody.axis = .vertical; soloBody.spacing = 12
        soloBody.addArrangedSubview(backButton())
        soloBody.addArrangedSubview(pageHeading("On my own", detail: "Choose a world, then press Play."))
        for (index, mode) in modes.prefix(2).enumerated() {
            let card = PureBlackModeCard(title: index == 0 ? L10n.text("Story mode") : L10n.text("Free roam"),
                                         detail: index == 0 ? L10n.text("Play the story using your saves.") : L10n.text("Explore Los Santos at your pace."), symbol: mode.symbol)
            card.addAction(UIAction { [weak self] _ in self?.onMode?(index) }, for: .touchUpInside)
            modeCards.append(card)
        }
        let modeRow = UIStackView(arrangedSubviews: modeCards); modeRow.spacing = 12; modeRow.distribution = .fillEqually
        soloBody.addArrangedSubview(modeRow)
        modeDetail.font = Theme.body(14); modeDetail.textColor = Theme.secondaryText; modeDetail.numberOfLines = 0
        soloBody.addArrangedSubview(modeDetail)
        let playRow = UIStackView(arrangedSubviews: [playButton, UIView()]); soloBody.addArrangedSubview(playRow)
        playButton.widthAnchor.constraint(greaterThanOrEqualToConstant: 185).isActive = true
        for label in [preloadLabel, controllerLabel] {
            label.font = Theme.body(12); label.textColor = Theme.secondaryText; label.numberOfLines = 0
            soloBody.addArrangedSubview(label)
        }
        preloadLabel.isHidden = true

        friendsBody.axis = .vertical; friendsBody.spacing = 12
        friendsBody.addArrangedSubview(backButton())
        friendsBody.addArrangedSubview(pageHeading("With friends", detail: "Join a lobby or host your own."))
        multiplayerHome.spacing = 12; multiplayerHome.distribution = .fillEqually
        friendsBody.addArrangedSubview(multiplayerHome)
        multiplayerDetail.font = Theme.body(14); multiplayerDetail.textColor = Theme.secondaryText
        multiplayerDetail.numberOfLines = 0; multiplayerDetail.accessibilityIdentifier = "friends.status"
        friendsBody.addArrangedSubview(multiplayerDetail)
        multiplayerPlayButton.accessibilityIdentifier = "friends.play"
        multiplayerPlayButton.heightAnchor.constraint(greaterThanOrEqualToConstant: 48).isActive = true
        multiplayerPlayButton.widthAnchor.constraint(greaterThanOrEqualToConstant: 210).isActive = true
        let multiplayerPlayRow = UIStackView(arrangedSubviews: [multiplayerPlayButton, UIView()])
        multiplayerPlayRow.spacing = 12; multiplayerPlayRow.alignment = .center
        friendsBody.addArrangedSubview(multiplayerPlayRow)
        configureMultiplayerActions()
        setMultiplayerState(role: "join", detail: "Choose a lobby above, then press the green button to play.", ready: false, enabled: true)
        show(.home)

        log.translatesAutoresizingMaskIntoConstraints = false; addSubview(log)
        NSLayoutConstraint.activate([
            log.leadingAnchor.constraint(equalTo: guide.leadingAnchor, constant: 16),
            log.trailingAnchor.constraint(equalTo: guide.trailingAnchor, constant: -16),
            log.bottomAnchor.constraint(equalTo: guide.bottomAnchor, constant: -10),
            log.heightAnchor.constraint(lessThanOrEqualTo: guide.heightAnchor, multiplier: 0.5)
        ])
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is not used") }

    /// Bounded content keeps landscape phones from stretching artwork and type.
    private func leadingBounded(_ view: UIView, maximumWidth: CGFloat) -> UIView {
        let row = UIView()
        view.translatesAutoresizingMaskIntoConstraints = false; row.addSubview(view)
        let preferred = view.widthAnchor.constraint(equalTo: row.widthAnchor)
        preferred.priority = .defaultHigh
        NSLayoutConstraint.activate([
            view.leadingAnchor.constraint(equalTo: row.leadingAnchor),
            view.widthAnchor.constraint(lessThanOrEqualToConstant: maximumWidth),
            view.widthAnchor.constraint(lessThanOrEqualTo: row.widthAnchor), preferred,
            view.topAnchor.constraint(equalTo: row.topAnchor), view.bottomAnchor.constraint(equalTo: row.bottomAnchor)
        ])
        return row
    }

    private func show(_ next: Page) {
        let body = next == .home ? homeBody : next == .solo ? soloBody : friendsBody
        guard visibleBody !== body else { return }
        // Detach inactive stacks. Hiding a nested stack adds a zero-height
        // constraint that conflicts with its required card/button heights.
        if let previous = visibleBody {
            content.removeArrangedSubview(previous)
            previous.removeFromSuperview()
        }
        content.addArrangedSubview(body)
        visibleBody = body
        homeScroll.setContentOffset(.zero, animated: false)
        UIAccessibility.post(notification: .screenChanged, argument: next == .home ? homeBody : next == .solo ? soloBody : friendsBody)
    }
    private func backButton() -> UIView {
        let button = Theme.glassButton(L10n.text("Back"), symbol: "chevron.left")
        button.addAction(UIAction { [weak self] _ in self?.show(.home) }, for: .touchUpInside)
        let row = UIView()
        button.translatesAutoresizingMaskIntoConstraints = false; row.addSubview(button)
        NSLayoutConstraint.activate([
            button.leadingAnchor.constraint(equalTo: row.leadingAnchor),
            button.topAnchor.constraint(equalTo: row.topAnchor), button.bottomAnchor.constraint(equalTo: row.bottomAnchor),
            button.heightAnchor.constraint(greaterThanOrEqualToConstant: 44),
            button.trailingAnchor.constraint(lessThanOrEqualTo: row.trailingAnchor)
        ])
        return row
    }
    private func pageHeading(_ title: String, detail: String) -> UIView {
        let label = UILabel(); label.text = L10n.text(title); label.font = Theme.display(27); label.textColor = .white
        let hint = UILabel(); hint.text = L10n.text(detail); hint.font = Theme.body(15); hint.textColor = Theme.secondaryText
        let stack = UIStackView(arrangedSubviews: [label, hint]); stack.axis = .vertical; stack.spacing = 3
        return stack
    }
    func configureMultiplayerActions() {
        guard multiplayerHome.arrangedSubviews.isEmpty else { return }
        for (role, title, hint, icon) in [("choose", "Join or create", "Join a friend or host a lobby", "person.2.fill"),
                                         ("browse", "Find lobby", "Browse available and saved lobbies", "magnifyingglass")] {
            let card = PureBlackModeCard(title: L10n.text(title), detail: L10n.text(hint), symbol: icon)
            card.accessibilityIdentifier = "friends." + role
            card.addAction(UIAction { [weak self] _ in self?.multiplayerAction?(role) }, for: .touchUpInside)
            multiplayerCards.append(card); multiplayerHome.addArrangedSubview(card)
        }
    }
    func setMultiplayerState(role: String, detail: String, ready: Bool, enabled: Bool) {
        for (index, card) in multiplayerCards.enumerated() {
            card.isSelected = index == (role == "browse" ? 1 : 0)
            card.isEnabled = enabled
        }
        multiplayerDetail.text = L10n.text(detail)
        let title = L10n.text(role == "host" ? "Host multiplayer" : "Play multiplayer")
        multiplayerPlayButton.configuration?.title = title
        multiplayerPlayButton.accessibilityLabel = title
        multiplayerPlayButton.accessibilityHint = L10n.text(ready ? "Launch the configured multiplayer game" : "Finish lobby setup and connection first")
        multiplayerPlayButton.isEnabled = ready && enabled
    }
    func showMultiplayerSetupHint() {
        show(.friends)
        UIAccessibility.post(notification: .announcement, argument: L10n.text("Choose a lobby above, then press the green button to play."))
    }
    func setFiles(_ state: FilesState, title: String, detail: String) {
        filesLabel.text = L10n.text(state == .ready ? "Game files ready" : state == .busy ? "Checking game files" : "Game files need attention")
        filesIcon.isHidden = state == .busy
        if state == .busy { filesSpinner.startAnimating() } else { filesSpinner.stopAnimating() }
        let (symbol, color): (String, UIColor) = switch state {
        case .ready: ("checkmark.circle.fill", Theme.ok)
        case .attention: ("folder.badge.questionmark", Theme.warning)
        case .problem: ("exclamationmark.triangle.fill", Theme.problem)
        case .busy: ("", Theme.secondaryText)
        }
        filesIcon.image = symbol.isEmpty ? nil : UIImage(systemName: symbol)
        filesIcon.tintColor = color
        filesCard.accessibilityLabel = "\(filesLabel.text ?? "Game files"): \(title). \(detail)"
        filesCard.accessibilityHint = L10n.text("Open game files")
    }
    func setMap(_ index: Int, visible: Bool, enabled: Bool) { /* Los Santos is the only supported map. */ }
    func setMode(_ index: Int?, detail: String, enabled: Bool) {
        for (i, card) in modeCards.enumerated() { card.isSelected = i == index; card.isEnabled = enabled }
        modeDetail.text = L10n.text(detail)
    }
    private func pin(_ child: UIView) {
        child.translatesAutoresizingMaskIntoConstraints = false; addSubview(child)
        NSLayoutConstraint.activate([
            child.leadingAnchor.constraint(equalTo: leadingAnchor), child.trailingAnchor.constraint(equalTo: trailingAnchor),
            child.topAnchor.constraint(equalTo: topAnchor), child.bottomAnchor.constraint(equalTo: bottomAnchor)
        ])
    }
}

private final class PureBlackChoiceCard: UIControl {
    private let icon = UIImageView()
    private let heading = UILabel()
    private let caption = UILabel()
    init(image: String, symbol: String, title: String, detail: String) {
        super.init(frame: .zero)
        layer.cornerRadius = 12; layer.cornerCurve = .continuous; layer.borderWidth = 1
        layer.borderColor = Theme.panelStroke.cgColor; clipsToBounds = true
        let art = UIImageView(image: UIImage(named: image)); art.contentMode = .scaleAspectFill
        art.setContentHuggingPriority(.fittingSizeLevel, for: .vertical)
        art.setContentCompressionResistancePriority(.fittingSizeLevel, for: .vertical)
        art.setContentHuggingPriority(.fittingSizeLevel, for: .horizontal)
        art.setContentCompressionResistancePriority(.fittingSizeLevel, for: .horizontal)
        let shade = GradientView(colors: [.black.withAlphaComponent(image == "SoloCard" ? 0.14 : 0.03), .clear, .black.withAlphaComponent(0.12)], locations: [0, 0.45, 1], horizontal: false)
        for child in [art, shade] as [UIView] {
            child.translatesAutoresizingMaskIntoConstraints = false; addSubview(child)
            NSLayoutConstraint.activate([
                child.leadingAnchor.constraint(equalTo: leadingAnchor), child.trailingAnchor.constraint(equalTo: trailingAnchor),
                child.topAnchor.constraint(equalTo: topAnchor), child.bottomAnchor.constraint(equalTo: bottomAnchor)
            ])
        }
        icon.image = UIImage(systemName: symbol, withConfiguration: UIImage.SymbolConfiguration(pointSize: 38, weight: .semibold))
        icon.tintColor = .white; icon.contentMode = .scaleAspectFit; icon.translatesAutoresizingMaskIntoConstraints = false; addSubview(icon)
        heading.text = title; heading.font = Theme.display(21, .bold); heading.textColor = .white
        caption.text = detail; caption.font = Theme.body(11.5, .medium); caption.textColor = Theme.secondaryText; caption.numberOfLines = 0
        let copy = UIStackView(arrangedSubviews: [heading, caption]); copy.axis = .vertical; copy.spacing = 2; copy.alignment = .leading
        // Decorative copy must let the owning card receive the whole touch.
        copy.isUserInteractionEnabled = false
        copy.translatesAutoresizingMaskIntoConstraints = false; addSubview(copy)
        let arrow = UIImageView(image: UIImage(systemName: "chevron.right", withConfiguration: UIImage.SymbolConfiguration(pointSize: 17, weight: .bold)))
        arrow.tintColor = .white
        let arrowDisc = UIView(); arrowDisc.backgroundColor = Theme.accent; arrowDisc.layer.cornerRadius = 16; arrowDisc.isUserInteractionEnabled = false
        arrowDisc.translatesAutoresizingMaskIntoConstraints = false; addSubview(arrowDisc)
        arrow.translatesAutoresizingMaskIntoConstraints = false; arrowDisc.addSubview(arrow)
        NSLayoutConstraint.activate([
            icon.widthAnchor.constraint(equalToConstant: 30), icon.heightAnchor.constraint(equalToConstant: 23),
            icon.topAnchor.constraint(equalTo: topAnchor, constant: 12),
            icon.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 16),
            copy.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 16), copy.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -16),
            caption.trailingAnchor.constraint(equalTo: copy.trailingAnchor),
            copy.bottomAnchor.constraint(equalTo: bottomAnchor, constant: -12),
            heading.trailingAnchor.constraint(lessThanOrEqualTo: arrowDisc.leadingAnchor, constant: -8),
            arrowDisc.widthAnchor.constraint(equalToConstant: 32), arrowDisc.heightAnchor.constraint(equalToConstant: 32),
            arrowDisc.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -14), arrowDisc.centerYAnchor.constraint(equalTo: heading.centerYAnchor, constant: -4),
            arrow.centerXAnchor.constraint(equalTo: arrowDisc.centerXAnchor), arrow.centerYAnchor.constraint(equalTo: arrowDisc.centerYAnchor)
        ])
        isAccessibilityElement = true; accessibilityTraits = .button; accessibilityLabel = title + ". " + detail
        icon.accessibilityIdentifier = "card.icon"
        arrowDisc.accessibilityIdentifier = "card.arrow"
        heading.accessibilityIdentifier = "card.title"
        caption.accessibilityIdentifier = "card.subtitle"
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is not used") }
    override var isHighlighted: Bool { didSet { alpha = isHighlighted ? 0.75 : 1 } }
}

private final class PureBlackModeCard: UIControl {
    private let label = UILabel()
    init(title: String, detail: String, symbol: String) {
        super.init(frame: .zero)
        backgroundColor = Theme.surface; layer.cornerRadius = 15; layer.borderWidth = 1; layer.borderColor = Theme.panelStroke.cgColor
        let icon = UIImageView(image: UIImage(systemName: symbol)); icon.tintColor = Theme.accent
        icon.widthAnchor.constraint(equalToConstant: 26).isActive = true
        label.text = title
        label.font = Theme.body(15, .semibold)
        label.textColor = .white
        let hint = UILabel(); hint.text = detail; hint.font = Theme.body(12); hint.textColor = Theme.secondaryText; hint.numberOfLines = 0
        let copy = UIStackView(arrangedSubviews: [label, hint]); copy.axis = .vertical; copy.spacing = 3
        let row = UIStackView(arrangedSubviews: [icon, copy]); row.spacing = 12; row.alignment = .center; row.isUserInteractionEnabled = false
        row.translatesAutoresizingMaskIntoConstraints = false; addSubview(row)
        NSLayoutConstraint.activate([
            row.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 16), row.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -16),
            row.topAnchor.constraint(equalTo: topAnchor, constant: 12), row.bottomAnchor.constraint(equalTo: bottomAnchor, constant: -12),
            heightAnchor.constraint(greaterThanOrEqualToConstant: 68)
        ])
        isAccessibilityElement = true; accessibilityLabel = title + ". " + detail; update()
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is not used") }
    override var isSelected: Bool { didSet { update() } }
    override var isEnabled: Bool { didSet { update() } }
    override var isHighlighted: Bool { didSet { alpha = isHighlighted ? 0.75 : 1 } }
    private func update() {
        layer.borderColor = (isSelected ? Theme.accent : Theme.panelStroke).cgColor
        layer.borderWidth = isSelected ? 2 : 1
        label.textColor = isEnabled ? .white : Theme.tertiaryText
        accessibilityTraits = isSelected ? [.button, .selected] : .button
    }
}
