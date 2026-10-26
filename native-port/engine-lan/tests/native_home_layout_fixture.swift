// This native-only fixture exercises the real HomeView Auto Layout tree.
// It belongs in the separate simulator preview target, never the game app.
import UIKit

func launcherLayoutEvidence(_ home: HomeView, in root: UIView) -> [String: Any] {
    func all(_ view: UIView) -> [UIView] { [view] + view.subviews.flatMap(all) }
    let views = all(home)
    let safe = root.bounds.inset(by: root.safeAreaInsets)
    var failures = [String]()
    var controls = [[String: Any]]()
    for id in ["home.solo", "home.friends", "home.mods"] {
        guard let control = views.first(where: { $0.accessibilityIdentifier == id }) else { failures.append("Missing \(id)"); continue }
        let rect = control.convert(control.bounds, to: root)
        let visible = safe.insetBy(dx: -0.5, dy: -0.5).contains(rect)
        if !visible { failures.append("Clipped \(id)") }
        if rect.width < 44 || rect.height < 44 { failures.append("Small target \(id)") }
        controls.append(["id": id, "frame": String(describing: rect), "fully_visible": visible])
        if id != "home.mods" {
            if rect.width > 241 || rect.height > 113 { failures.append("Oversized play card \(id)") }
            let children = all(control)
            if let title = children.first(where: { $0.accessibilityIdentifier == "card.title" }),
               let arrow = children.first(where: { $0.accessibilityIdentifier == "card.arrow" }),
               title.convert(title.bounds, to: control).intersects(arrow.convert(arrow.bounds, to: control)) {
                failures.append("Title overlaps arrow \(id)")
            }
        }
        for label in all(control).compactMap({ $0 as? UILabel }) {
            let frame = label.convert(label.bounds, to: control)
            if !control.bounds.insetBy(dx: -0.5, dy: -0.5).contains(frame) { failures.append("Clipped label \(label.text ?? "")") }
            let needed = label.sizeThatFits(CGSize(width: label.bounds.width, height: .greatestFiniteMagnitude))
            if needed.height > label.bounds.height + 1 || needed.width > label.bounds.width + 1 { failures.append("Truncated label \(label.text ?? "")") }
        }
    }
    var cardGap: CGFloat = -1
    if let solo = views.first(where: { $0.accessibilityIdentifier == "home.solo" }),
       let friends = views.first(where: { $0.accessibilityIdentifier == "home.friends" }) {
        cardGap = friends.convert(friends.bounds, to: root).minX - solo.convert(solo.bounds, to: root).maxX
        if abs(cardGap - 12) > 0.5 { failures.append("Play-card gap differs from 12 points") }
    }
    var alignment = [[String: Any]]()
    for id in ["home.heading", "home.solo", "home.modsPanel"] {
        guard let view = views.first(where: { $0.accessibilityIdentifier == id }) else { failures.append("Missing alignment anchor \(id)"); continue }
        let rect = view.convert(view.bounds, to: root)
        let matches = abs(rect.minX - (safe.minX + 12)) < 1
        if !matches { failures.append("Left alignment differs for \(id)") }
        alignment.append(["id": id, "frame": String(describing: rect), "matches_content_left": matches])
    }
    for scroll in views.compactMap({ $0 as? UIScrollView }) where !scroll.isHidden && scroll.bounds.height > 0 && scroll.contentSize.height > scroll.bounds.height + 1 {
        failures.append("Home unexpectedly scrolls: \(scroll.contentSize.height) > \(scroll.bounds.height)")
    }
    if !views.compactMap({ $0 as? UILabel }).contains(where: { $0.text == "by zema" }) { failures.append("Missing author credit") }
    return ["root": String(describing: root.bounds), "safe_area": String(describing: safe), "controls": controls, "left_alignment": alignment, "play_card_gap_points": cardGap, "failures": failures, "pass": failures.isEmpty]
}
