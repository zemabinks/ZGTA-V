import UIKit

/// A quiet, noninteractive message. New feedback owns both text and dismissal.
final class GameActionToast: UIView {
    private let label = UILabel()
    private var dismissal: DispatchWorkItem?
    private var generation: UInt64 = 0

    init() {
        super.init(frame: .zero)
        isUserInteractionEnabled = false
        isAccessibilityElement = true
        backgroundColor = UIColor(white: 0.06, alpha: 0.30)
        layer.cornerRadius = 12
        layer.borderWidth = 0.5
        layer.borderColor = UIColor.white.withAlphaComponent(0.12).cgColor
        label.font = .systemFont(ofSize: 14, weight: .medium)
        label.textColor = .white
        label.textAlignment = .center
        label.numberOfLines = 3
        label.isAccessibilityElement = false
        label.lineBreakMode = .byTruncatingTail
        label.shadowColor = UIColor.black.withAlphaComponent(0.35)
        label.shadowOffset = CGSize(width: 0, height: 1)
        addSubview(label)
        alpha = 0
        accessibilityTraits = .staticText
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) is not used") }

    override func layoutSubviews() {
        super.layoutSubviews()
        label.frame = bounds.insetBy(dx: 16, dy: 10)
    }

    func show(_ message: String, in host: UIView) {
        generation &+= 1
        let current = generation
        dismissal?.cancel()
        layer.removeAllAnimations()
        label.text = message
        accessibilityLabel = message
        let safe = host.safeAreaInsets
        let maxWidth = max(1, min(460, host.bounds.width - safe.left - safe.right - 32))
        let size = label.sizeThatFits(CGSize(width: max(1, maxWidth - 32), height: 72))
        let width = min(maxWidth, size.width + 32)
        frame = CGRect(x: (host.bounds.width - width) / 2,
                       y: max(safe.top, 12) + 12, width: width, height: min(72, size.height) + 20)
        if superview !== host { host.addSubview(self) }
        host.bringSubviewToFront(self)
        setNeedsLayout()
        let duration = UIAccessibility.isReduceMotionEnabled ? 0 : 0.16
        UIView.animate(withDuration: duration, delay: 0, options: [.beginFromCurrentState, .allowUserInteraction, .curveEaseOut]) { self.alpha = 1 }
        let work = DispatchWorkItem { [weak self] in
            guard let self, self.generation == current else { return }
            UIView.animate(withDuration: duration, delay: 0, options: [.beginFromCurrentState, .allowUserInteraction, .curveEaseOut]) { self.alpha = 0 }
        }
        dismissal = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 3, execute: work)
    }
}
