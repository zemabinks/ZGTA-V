import UIKit
import CoreImage

/// Pure Black tokens shared by every app-owned launcher screen.
enum Theme {
    /// The app's version as players should quote it in reports, e.g. "v1.3 (6)".
    static let appVersion: String = {
        let info = Bundle.main.infoDictionary
        return "v\(info?["CFBundleShortVersionString"] as? String ?? "?") (\(info?["CFBundleVersion"] as? String ?? "?"))"
    }()
    static let accent = UIColor(red: 120/255, green: 184/255, blue: 67/255, alpha: 1)
    static let accentDeep = UIColor(red: 91/255, green: 148/255, blue: 51/255, alpha: 1)
    static let onAccent = UIColor(red: 16/255, green: 32/255, blue: 22/255, alpha: 1)
    static let ok = accent
    static let warning = UIColor(red: 241/255, green: 198/255, blue: 108/255, alpha: 1)
    static let problem = UIColor(red: 1, green: 128/255, blue: 122/255, alpha: 1)
    static let text = UIColor.white
    static let secondaryText = UIColor(red: 184/255, green: 191/255, blue: 184/255, alpha: 1)
    static let tertiaryText = UIColor(red: 141/255, green: 151/255, blue: 141/255, alpha: 1)
    static let night = UIColor(red: 5/255, green: 6/255, blue: 5/255, alpha: 1)
    static let surface = UIColor(red: 16/255, green: 19/255, blue: 16/255, alpha: 1)
    static let raised = UIColor(red: 25/255, green: 30/255, blue: 25/255, alpha: 1)
    static let panelStroke = UIColor(red: 75/255, green: 85/255, blue: 75/255, alpha: 1)

    static func display(_ size: CGFloat, _ weight: UIFont.Weight = .heavy) -> UIFont {
        UIFont.systemFont(ofSize: size, weight: weight)
    }
    static func body(_ size: CGFloat = 15, _ weight: UIFont.Weight = .regular) -> UIFont { .systemFont(ofSize: size, weight: weight) }

    /// Opaque graphite keeps rows readable even when Reduce Transparency is enabled.
    static func panel(cornerRadius: CGFloat = 18) -> UIVisualEffectView {
        let panel = UIVisualEffectView(effect: nil)
        panel.backgroundColor = surface
        panel.layer.cornerRadius = cornerRadius
        panel.layer.cornerCurve = .continuous
        panel.clipsToBounds = true
        panel.layer.borderWidth = 1
        panel.layer.borderColor = panelStroke.cgColor
        return panel
    }

    /// Only Home uses the real map reference. Other screens use solid Pure Black.
    static func backdrop(image name: String, darken: CGFloat = 0.55) -> UIView {
        let view = UIView()
        view.backgroundColor = night
        if name == "LosSantosMap", let image = UIImage(named: name) {
            // Desaturate the real source map without redrawing any street geometry.
            let input = CIImage(image: image)
            let gray = input?.applyingFilter("CIColorControls", parameters: [kCIInputSaturationKey: 0])
                .applyingFilter("CIColorMatrix", parameters: [
                    "inputRVector": CIVector(x: 3, y: 0, z: 0, w: 0),
                    "inputGVector": CIVector(x: 0, y: 3, z: 0, w: 0),
                    "inputBVector": CIVector(x: 0, y: 0, z: 3, w: 0),
                    "inputBiasVector": CIVector(x: -2, y: -2, z: -2, w: 0)
                ])
            let rendered = gray.flatMap { CIContext().createCGImage($0, from: $0.extent) }
            let map = UIImageView(image: rendered.map { UIImage(cgImage: $0) } ?? image)
            map.contentMode = .scaleAspectFit
            map.alpha = 0.46
            map.translatesAutoresizingMaskIntoConstraints = false
            view.addSubview(map)
            NSLayoutConstraint.activate([
                map.trailingAnchor.constraint(equalTo: view.trailingAnchor),
                map.topAnchor.constraint(equalTo: view.topAnchor),
                map.bottomAnchor.constraint(equalTo: view.bottomAnchor),
                map.widthAnchor.constraint(equalTo: view.widthAnchor, multiplier: 0.60)
            ])
            let shade = GradientView(colors: [night, night.withAlphaComponent(0.96), night.withAlphaComponent(0.30)],
                                     locations: [0, 0.52, 1], horizontal: true)
            shade.frame = view.bounds
            shade.autoresizingMask = [.flexibleWidth, .flexibleHeight]
            view.addSubview(shade)
        }
        view.isUserInteractionEnabled = false
        return view
    }

    /// The background art behind Settings: evenly darkened so every row stays readable.
    static func dimmedBackdrop(image name: String) -> UIView {
        let view = UIView()
        view.backgroundColor = night
        return view
    }
    static let rowBackground = surface
    static let rowSelected = raised

    /// The big main-action button (Play, Install): warm gradient, rounded, bold.
    static func primaryButton(_ title: String, symbol: String? = nil) -> UIButton {
        var config = UIButton.Configuration.filled()
        config.title = title
        config.image = symbol.map { UIImage(systemName: $0, withConfiguration: UIImage.SymbolConfiguration(weight: .heavy)) } ?? nil
        config.imagePadding = 10
        config.cornerStyle = .medium
        config.baseForegroundColor = onAccent
        config.background.backgroundColor = accent
        config.contentInsets = NSDirectionalEdgeInsets(top: 14, leading: 30, bottom: 14, trailing: 30)
        config.titleTextAttributesTransformer = UIConfigurationTextAttributesTransformer { attributes in
            var attributes = attributes; attributes.font = display(20, .heavy); return attributes
        }
        let button = UIButton(configuration: config)
        button.configurationUpdateHandler = { button in
            button.configuration?.background.backgroundColor = button.isEnabled ? (button.isHighlighted ? accentDeep : accent) : UIColor(white: 1, alpha: 0.16)
            button.configuration?.baseForegroundColor = button.isEnabled ? onAccent : secondaryText
        }
        button.layer.shadowColor = accent.cgColor
        button.layer.shadowOpacity = 0.12
        button.layer.shadowRadius = 8
        button.layer.shadowOffset = .zero
        return button
    }

    /// A quieter glass button (Settings, Controls layout, secondary actions).
    static func glassButton(_ title: String, symbol: String) -> UIButton {
        var config = UIButton.Configuration.gray()
        config.title = title
        config.image = UIImage(systemName: symbol)
        config.imagePadding = 8
        config.cornerStyle = .medium
        config.baseForegroundColor = text
        config.background.backgroundColor = raised
        config.background.strokeColor = panelStroke
        config.background.strokeWidth = 1
        config.contentInsets = NSDirectionalEdgeInsets(top: 10, leading: 16, bottom: 10, trailing: 16)
        config.titleTextAttributesTransformer = UIConfigurationTextAttributesTransformer { attributes in
            var attributes = attributes; attributes.font = body(15, .semibold); return attributes
        }
        return UIButton(configuration: config)
    }

    /// Navigation bars and tables in Settings and the game files screens.
    static func styleNavigation(_ navigation: UINavigationController) {
        let appearance = UINavigationBarAppearance()
        appearance.configureWithOpaqueBackground()
        appearance.backgroundColor = night
        appearance.titleTextAttributes = [.foregroundColor: text, .font: display(18, .bold)]
        appearance.largeTitleTextAttributes = [.foregroundColor: text, .font: display(32, .heavy)]
        navigation.navigationBar.standardAppearance = appearance
        navigation.navigationBar.scrollEdgeAppearance = appearance
        navigation.navigationBar.compactAppearance = appearance
        navigation.navigationBar.tintColor = accent
        navigation.overrideUserInterfaceStyle = .dark
        navigation.view.tintColor = accent
    }
}

/// A view that draws a linear gradient (backdrop shading).
final class GradientView: UIView {
    override class var layerClass: AnyClass { CAGradientLayer.self }
    init(colors: [UIColor], locations: [NSNumber], horizontal: Bool) {
        super.init(frame: .zero)
        let gradient = layer as! CAGradientLayer
        gradient.colors = colors.map(\.cgColor)
        gradient.locations = locations
        gradient.startPoint = horizontal ? CGPoint(x: 0, y: 0.5) : CGPoint(x: 0.5, y: 0)
        gradient.endPoint = horizontal ? CGPoint(x: 1, y: 0.5) : CGPoint(x: 0.5, y: 1)
        isUserInteractionEnabled = false
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is not used") }
}
