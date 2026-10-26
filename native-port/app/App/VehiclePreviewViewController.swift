import Foundation
import CoreGraphics

/// Shared by the actual view and host-side layout tests. All rectangles fit the
/// safe area; only the details text can scroll, never the reference picture.
struct VehiclePreviewLayout {
    struct Frames {
        let close: CGRect
        let picture: CGRect
        let details: CGRect
        let action: CGRect
        let sideBySide: Bool
    }
    static func frames(in safe: CGRect, compactHeight: Bool, actionHeight: CGFloat = 56, closeWidth: CGFloat = 108) -> Frames {
        let side = safe.width >= 480 && (compactHeight || safe.width > safe.height)
        let margin: CGFloat = side ? 16 : 20
        let gap: CGFloat = side ? 12 : 14
        let inner = safe.insetBy(dx: margin, dy: side ? 10 : 14)
        let buttonHeight = min(max(48, actionHeight), max(48, inner.height * 0.30))
        let close = CGRect(x: inner.maxX - min(closeWidth, inner.width), y: inner.minY, width: min(closeWidth, inner.width), height: 44)
        let action = CGRect(x: inner.minX, y: inner.maxY - buttonHeight, width: inner.width, height: buttonHeight)
        let body = CGRect(x: inner.minX, y: close.maxY + 10, width: inner.width, height: max(0, action.minY - gap - close.maxY - 10))
        if side {
            let imageWidth = (body.width - gap) * 0.56
            return Frames(close: close, picture: CGRect(x: body.minX, y: body.minY, width: imageWidth, height: body.height),
                          details: CGRect(x: body.minX + imageWidth + gap, y: body.minY, width: body.width - imageWidth - gap, height: body.height),
                          action: action, sideBySide: true)
        }
        let imageHeight = min(body.width * 0.58, body.height * 0.52)
        return Frames(close: close, picture: CGRect(x: body.minX, y: body.minY, width: body.width, height: imageHeight),
                      details: CGRect(x: body.minX, y: body.minY + imageHeight + gap, width: body.width, height: max(0, body.height - imageHeight - gap)),
                      action: action, sideBySide: false)
    }
}

#if canImport(UIKit)
import UIKit
import ImageIO

/// A reference picture is optional. Selection never queues a spawn until Spawn is pressed.
final class VehiclePreviewViewController: UIViewController {
    private let vehicle: VehicleCatalog.Entry
    private let spawn: () -> Void
    private let availability: () -> Int32
    private let availabilityLabel = UILabel()
    private var availabilityTimer: Timer?
    private let picture = UIImageView()
    private let status = UILabel()
    private let details = UIScrollView()
    private let content = UIStackView()
    private var close: UIButton!
    private var action: UIButton!
    private var request: URLSessionDataTask?
    private var generation = 0
    // No persistent thumbnail files: avoid growing the game's already large on-device storage.
    private static let session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.urlCache = URLCache(memoryCapacity: 8 * 1024 * 1024, diskCapacity: 0)
        config.requestCachePolicy = .returnCacheDataElseLoad
        config.timeoutIntervalForRequest = 12
        config.timeoutIntervalForResource = 15
        config.httpMaximumConnectionsPerHost = 1
        return URLSession(configuration: config)
    }()

    init(vehicle: VehicleCatalog.Entry, availability: @escaping () -> Int32 = { -1 }, spawn: @escaping () -> Void) {
        self.vehicle = vehicle
        self.spawn = spawn
        self.availability = availability
        super.init(nibName: nil, bundle: nil)
        modalPresentationStyle = .formSheet
        preferredContentSize = CGSize(width: 480, height: 510)
        overrideUserInterfaceStyle = .dark
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is not used") }
    deinit { request?.cancel(); availabilityTimer?.invalidate() }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = Theme.night
        view.tintColor = Theme.accent
        close = Theme.glassButton("Close", symbol: "xmark")
        close.addAction(UIAction { [weak self] _ in self?.dismiss(animated: true) }, for: .touchUpInside)
        action = Theme.primaryButton("Spawn vehicle", symbol: "plus")
        action.addAction(UIAction { [weak self, weak action] _ in
            guard let self, self.availability() != 0, self.availability() != -2 else { return }
            action?.isEnabled = false
            self.stopRequest()
            self.dismiss(animated: true, completion: self.spawn)
        }, for: .touchUpInside)
        content.axis = .vertical
        content.spacing = 10
        let name = UILabel()
        name.text = vehicle.name
        name.font = UIFontMetrics(forTextStyle: .title2).scaledFont(for: Theme.display(24, .bold))
        name.adjustsFontForContentSizeCategory = true
        name.accessibilityTraits.insert(.header)
        name.numberOfLines = 0
        name.textColor = Theme.text
        let detail = UILabel()
        detail.text = vehicle.detail
        detail.numberOfLines = 0
        detail.font = UIFontMetrics(forTextStyle: .subheadline).scaledFont(for: Theme.body(14))
        detail.adjustsFontForContentSizeCategory = true
        detail.textColor = Theme.secondaryText
        picture.contentMode = .scaleAspectFit
        picture.backgroundColor = UIColor(white: 1, alpha: 0.05)
        picture.layer.cornerRadius = 14
        picture.clipsToBounds = true
        picture.isAccessibilityElement = true
        picture.accessibilityLabel = vehicle.name + " reference picture"
        status.text = vehicle.thumbnailURL == nil ? "No reference picture available for this mod vehicle." : "Loading reference picture…"
        status.font = UIFontMetrics(forTextStyle: .footnote).scaledFont(for: Theme.body(13))
        status.adjustsFontForContentSizeCategory = true
        status.textColor = Theme.secondaryText
        status.numberOfLines = 0
        status.accessibilityTraits = .updatesFrequently
        let attribution = UILabel()
        attribution.text = vehicle.thumbnailCredit
        attribution.font = UIFontMetrics(forTextStyle: .caption2).scaledFont(for: Theme.body(11))
        attribution.adjustsFontForContentSizeCategory = true
        attribution.textColor = Theme.tertiaryText
        attribution.numberOfLines = 0
        availabilityLabel.font = UIFontMetrics(forTextStyle: .footnote).scaledFont(for: Theme.body(13))
        availabilityLabel.numberOfLines = 0
        availabilityLabel.accessibilityTraits = .updatesFrequently
        for child in [name, detail, availabilityLabel, status, attribution] { content.addArrangedSubview(child) }
        for child in [close!, action!, picture, details] { view.addSubview(child) }
        details.addSubview(content)
        details.alwaysBounceVertical = false
        details.contentInsetAdjustmentBehavior = .never
        content.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            content.topAnchor.constraint(equalTo: details.contentLayoutGuide.topAnchor),
            content.leadingAnchor.constraint(equalTo: details.contentLayoutGuide.leadingAnchor),
            content.trailingAnchor.constraint(equalTo: details.contentLayoutGuide.trailingAnchor),
            content.bottomAnchor.constraint(equalTo: details.contentLayoutGuide.bottomAnchor),
            content.widthAnchor.constraint(equalTo: details.frameLayoutGuide.widthAnchor)
        ])
        loadPicture()
        updateAvailability()
        availabilityTimer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in self?.updateAvailability() }
    }
    private func updateAvailability() {
        let state = availability(), unavailable = state == 0 || state == -2
        action.isEnabled = !unavailable
        action.setTitle(state == 0 ? "Files unavailable" : state == -2 ? "Unsupported model" : "Spawn vehicle", for: .normal)
        action.alpha = unavailable ? 0.45 : 1
        availabilityLabel.text = state == 0 ? "×  Required vehicle files are missing or not loaded in this game." : state == -2 ? "×  This model is not supported as a vehicle in this game." : state == 2 ? "Checking game files…" : nil
        availabilityLabel.textColor = unavailable ? UIColor.systemRed.withAlphaComponent(0.8) : Theme.secondaryText
        availabilityLabel.isHidden = availabilityLabel.text == nil
    }
    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        let frames = VehiclePreviewLayout.frames(in: view.safeAreaLayoutGuide.layoutFrame,
            compactHeight: traitCollection.verticalSizeClass == .compact,
            actionHeight: action.intrinsicContentSize.height,
            closeWidth: max(100, close.intrinsicContentSize.width))
        close.frame = frames.close
        action.frame = frames.action
        picture.frame = frames.picture
        details.frame = frames.details
    }
    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        stopRequest(); availabilityTimer?.invalidate(); availabilityTimer = nil
    }
    private func stopRequest() { generation += 1; request?.cancel(); request = nil }
    nonisolated private static func thumbnail(_ source: CGImageSource) -> UIImage? {
        let options: [CFString: Any] = [kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceThumbnailMaxPixelSize: 640, kCGImageSourceCreateThumbnailWithTransform: true]
        guard let cg = CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary) else { return nil }
        return UIImage(cgImage: cg)
    }
    nonisolated private func finishPicture(_ image: UIImage?, token: Int) {
        DispatchQueue.main.async { [weak self] in
            guard let self, self.generation == token else { return }
            self.request = nil
            self.picture.image = image
            self.status.text = image == nil ? "Reference picture unavailable. You can still spawn this model if its game files are installed." : ""
        }
    }
    private func loadPicture() {
        guard let url = vehicle.thumbnailURL else { return }
        generation += 1
        let token = generation
        if url.isFileURL {
            // Bundled, exact-model artwork works offline; retain the same bounded
            // decode and cancellation generation as downloaded reference pictures.
            DispatchQueue.global(qos: .userInitiated).async { [weak self] in
                var image: UIImage?
                if let size = try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize,
                   size <= 4 * 1024 * 1024,
                   let source = CGImageSourceCreateWithURL(url as CFURL, nil) {
                    image = Self.thumbnail(source)
                }
                self?.finishPicture(image, token: token)
            }
            return
        }
        request = Self.session.dataTask(with: url) { [weak self] data, response, _ in
            let http = response as? HTTPURLResponse
            var image: UIImage?
            if http?.statusCode == 200, let final = http?.url, final.scheme == "https", final.host == "docs-backend.fivem.net",
               http?.mimeType?.hasPrefix("image/") == true, let data, data.count <= 2 * 1024 * 1024,
               let source = CGImageSourceCreateWithData(data as CFData, nil) {
                image = Self.thumbnail(source)
            }
            self?.finishPicture(image, token: token)
        }
        request?.resume()
    }
}

#endif
