// Separate Simulator fixture. Game, profile, transport and listener adapters are inert.
import UIKit
func friendsLayoutEvidence(_ home: HomeView, in root: UIView) -> [String: Any] {
    func all(_ v: UIView) -> [UIView] { [v] + v.subviews.flatMap(all) }
    home.showFriendsForPreview(); root.setNeedsLayout(); home.setNeedsLayout()
    RunLoop.main.run(until: Date().addingTimeInterval(0.08))
    root.layoutIfNeeded(); home.layoutIfNeeded(); root.layoutIfNeeded()
    let views = all(home), safe = root.bounds.inset(by: root.safeAreaInsets)
    var failures = [String](), frames = [[String: Any]](), actions = [String]()
    let previous = home.multiplayerAction
    home.multiplayerAction = { actions.append($0) }
    for id in ["friends.choose", "friends.browse"] {
        guard let card = views.first(where: { $0.accessibilityIdentifier == id }) as? UIControl else { failures.append("Missing \(id)"); continue }
        card.sendActions(for: .touchUpInside)
        if card.bounds.width < 44 || card.bounds.height < 44 { failures.append("Small \(id)") }
        for label in all(card).compactMap({ $0 as? UILabel }) {
            if !card.bounds.insetBy(dx: -0.5, dy: -0.5).contains(label.convert(label.bounds, to: card)) { failures.append("Clipped card text") }
            if label.sizeThatFits(CGSize(width: label.bounds.width, height: .greatestFiniteMagnitude)).height > label.bounds.height + 1 { failures.append("Truncated card text") }
        }
        frames.append(["id": id, "frame": String(describing: card.convert(card.bounds, to: root))])
    }
    if actions != ["choose", "browse"] { failures.append("Setup routing") }; home.multiplayerAction = previous
    if views.contains(where: { $0.accessibilityIdentifier == "friends.connection" }) { failures.append("Redundant Connection control") }
    let play = home.multiplayerPlayButton
    for role in ["join", "host", "browse"] {
        let expected = role == "host" ? "Host multiplayer" : "Play multiplayer"
        home.setMultiplayerState(role: role, detail: "Setup", ready: false, enabled: true)
        if play.isEnabled || play.configuration?.title != expected { failures.append("Unready \(role)") }
        home.setMultiplayerState(role: role, detail: "Ready", ready: true, enabled: true)
        if !play.isEnabled || play.configuration?.title != expected { failures.append("Ready \(role)") }
        home.setMultiplayerState(role: role, detail: "Starting", ready: true, enabled: false)
        if play.isEnabled { failures.append("Startup guard \(role)") }
    }
    home.setMultiplayerState(role: "join", detail: "Choose a lobby above, then press the green button to play.", ready: false, enabled: true)
    root.layoutIfNeeded(); home.layoutIfNeeded(); root.layoutIfNeeded()
    var scrollRequired = false
    if let scroll = views.compactMap({ $0 as? UIScrollView }).first {
        scrollRequired = scroll.contentSize.height > scroll.bounds.height + 1
        scroll.scrollRectToVisible(play.convert(play.bounds, to: scroll), animated: false)
    }
    let finalFrame = play.convert(play.bounds, to: root)
    if !safe.insetBy(dx: -0.5, dy: -0.5).contains(finalFrame) { failures.append("Green action not fully reachable") }
    if finalFrame.height < 44 || finalFrame.width < 44 { failures.append("Small green action") }
    if let first = views.first(where: { $0.accessibilityIdentifier == "friends.choose" }), let second = views.first(where: { $0.accessibilityIdentifier == "friends.browse" }) {
        let a = first.convert(first.bounds, to: root), b = second.convert(second.bounds, to: root)
        if abs(a.minY-b.minY) > 0.5 || abs(a.height-b.height) > 0.5 || abs(b.minX-a.maxX-12) > 0.5 { failures.append("Card row geometry") }
    }
    return ["pass": failures.isEmpty, "failures": failures, "root": String(describing: root.bounds), "safe_area": String(describing: safe), "cards": frames, "setup_actions": actions, "final_button_frame": String(describing: finalFrame), "scroll_required": scrollRequired, "states_checked": ["join", "host", "browse", "unready", "ready", "engine starting"]]
}
