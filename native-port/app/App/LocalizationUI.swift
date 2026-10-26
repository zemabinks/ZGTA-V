import UIKit

enum LocalizedUI {
    static func apply(to view: UIView) {
        if let label = view.accessibilityLabel { view.accessibilityLabel = L10n.text(label) }
        if let label = view as? UILabel, let text = label.text { label.text = L10n.text(text) }
        if let button = view as? UIButton {
            if var config = button.configuration {
                if let title = config.title { config.title = L10n.text(title) }
                if let subtitle = config.subtitle { config.subtitle = L10n.text(subtitle) }
                button.configuration = config
            } else if let title = button.title(for: .normal) { button.setTitle(L10n.text(title), for: .normal) }
        }
        if let field = view as? UITextField, let placeholder = field.placeholder { field.placeholder = L10n.text(placeholder) }
        for child in view.subviews { apply(to: child) }
    }
}
