// Separate native preview fixture: resolve actual UIKit touch targets across
// every part of each card, rather than sending actions straight to the card.
import UIKit
func homeCardHitTestEvidence(_ home: HomeView, in root: UIView) -> [String: Any] {
    func all(_ v: UIView) -> [UIView] { [v] + v.subviews.flatMap(all) }
    let views = all(home)
    var cards = [[String: Any]](), total = 0, failures = 0
    for id in ["home.solo", "home.friends"] {
        guard let card = views.first(where: { $0.accessibilityIdentifier == id }) as? UIControl else {
            return ["pass": false, "error": "Missing \(id)"]
        }
        var missed = [[String: Any]](), tested = 0
        for x in [0.01, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 0.99] {
            for y in [0.01, 0.167, 0.333, 0.5, 0.667, 0.833, 0.99] {
                let point = CGPoint(x: card.bounds.width*x, y: card.bounds.height*y)
                let hit = root.hitTest(card.convert(point, to: root), with: nil)
                tested += 1
                if hit !== card {
                    missed.append(["x": x, "y": y, "receiver": hit.map { String(describing: type(of: $0)) } ?? "nil"])
                }
            }
        }
        total += tested; failures += missed.count
        cards.append(["id": id, "points": tested, "failures": missed, "pass": missed.isEmpty])
    }
    if let a = views.first(where: { $0.accessibilityIdentifier == "home.solo" }),
       let b = views.first(where: { $0.accessibilityIdentifier == "home.friends" }) {
        let left = a.convert(a.bounds, to: root), right = b.convert(b.bounds, to: root)
        let hit = root.hitTest(CGPoint(x: (left.maxX + right.minX)/2, y: left.midY), with: nil)
        if hit === a || hit === b { failures += 1 }
    }
    return ["pass": failures == 0, "root": String(describing: root.bounds), "points": total, "failure_count": failures, "cards": cards]
}
