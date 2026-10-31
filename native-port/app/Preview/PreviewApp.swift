import UIKit

// Screen-only harness: production UIKit views, no game engine or network calls.
@main
final class PreviewApp: UIResponder, UIApplicationDelegate {
    var window: UIWindow?
    func application(_ application: UIApplication, didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        let window = UIWindow(frame: UIScreen.main.bounds)
        if ProcessInfo.processInfo.arguments.contains("--preview-graphics") {
            let reduced = ProcessInfo.processInfo.arguments.contains("--reduced-memory")
            GameSettings.shared.tier = DeviceTier(processAllowanceMB: reduced ? 2048 : 6144, physicalMemoryMB: reduced ? 3072 : 8192, model: reduced ? "iPhone SE 2020 (UI fixture)" : "iPhone 15 Pro (UI fixture)", supportsBCTextures: !reduced)
            GameSettings.shared.graphicsPreset = reduced ? .battery : .performance
            GameSettings.shared.memoryProfile = reduced ? .reduced : .automatic
            let settings = SettingsViewController(engineRunning: false, sectionRaw: 2)
            let navigation = UINavigationController(rootViewController: settings)
            Theme.styleNavigation(navigation); window.rootViewController = navigation
        } else { window.rootViewController = PreviewController() }
        window.makeKeyAndVisible(); self.window = window
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
            guard let controller = window.rootViewController else { return }
            func capture(_ name: String) {
                controller.view.layoutIfNeeded()
                let image = UIGraphicsImageRenderer(bounds: controller.view.bounds).image { _ in
                    controller.view.drawHierarchy(in: controller.view.bounds, afterScreenUpdates: true)
                }
                let path = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent(name + ".png")
                try! image.pngData()!.write(to: path)
            }
            capture("screen")
            if let nav = controller as? UINavigationController, let settings = nav.topViewController as? SettingsViewController {
                settings.tableView.scrollToRow(at: IndexPath(row: 0, section: 2), at: .bottom, animated: false)
                DispatchQueue.main.asyncAfter(deadline: .now() + 1) { capture("memory") }
            }
        }
        return true
    }
}
final class PreviewController: UIViewController {
    override var supportedInterfaceOrientations: UIInterfaceOrientationMask { .landscape }
    override var prefersStatusBarHidden: Bool { true }
    override func viewDidLoad() {
        super.viewDidLoad()
        let log = UITextView(); log.isHidden = true
        let home = HomeView(modes: [("Story mode", "book.closed.fill"), ("Free roam", "map.fill")], log: log)
        home.frame = view.bounds; home.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        home.setFiles(.ready, title: "GTA V", detail: "Game files ready")
        home.setMode(1, detail: "Explore Los Santos at your pace.", enabled: true)
        home.controllerLabel.text = "Touch controls ready"
        home.configureMultiplayerActions()
        view.addSubview(home)
        if ProcessInfo.processInfo.arguments.contains("--preview-friends") { home.showMultiplayerSetupHint() }
    }
    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        DispatchQueue.main.asyncAfter(deadline: .now() + 1) { [weak self] in
            guard let self else { return }
            self.view.layoutIfNeeded()
            var records: [[String: Any]] = []
            func inspect(_ v: UIView) {
                if let id = v.accessibilityIdentifier, id.hasPrefix("mode.symbol."), let image = v as? UIImageView {
                    let f = image.convert(image.bounds, to: self.view)
                    records.append(["id": id, "width": f.width, "height": f.height,
                                    "aspectFit": image.contentMode == .scaleAspectFit,
                                    "imageWidth": image.image?.size.width ?? 0, "imageHeight": image.image?.size.height ?? 0])
                }
                v.subviews.forEach(inspect)
            }
            inspect(self.view)
            let data = try! JSONSerialization.data(withJSONObject: ["screenWidth": self.view.bounds.width,
                "screenHeight": self.view.bounds.height, "symbols": records], options: [.prettyPrinted, .sortedKeys])
            let snapshot = UIGraphicsImageRenderer(bounds: self.view.bounds).image { _ in
                self.view.drawHierarchy(in: self.view.bounds, afterScreenUpdates: true)
            }
            try! snapshot.pngData()!.write(to: FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("friends.png"))
            try! data.write(to: FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("layout.json"))
        }
    }
}
