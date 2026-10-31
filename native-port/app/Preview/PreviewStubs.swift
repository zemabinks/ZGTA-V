// Link-only stand-ins for unrelated engine/files/network actions.
// The preview uses the production HomeView, SettingsViewController, GameSettings,
// GraphicsOptions, LowMemoryGraphics and Theme. It never starts the engine.
import UIKit
func PGSetEngineMemoryMB(_ mb: Int32) {}
func PGSetMemoryProfile(_ mode: Int32) {}
func PGSetPresentPacing(_ seconds: Double) {}
func PGConfigureEngine(_ options: UnsafePointer<UnsafePointer<CChar>?>, _ count: UInt32, _ width: Int32, _ height: Int32, _ interval: Int32) {}
func PGWorldToolsMode() -> Int32 { 0 }
func MugoatOnlineEnabled() -> Bool { false }
enum OnlineSettings { static let enabled = false }
enum GyroAimMode: Int, CaseIterable { case off, whileAiming, always; var title: String { ["Off", "While aiming", "Always on foot"][rawValue] } }
enum TiltSteerMode: Int, CaseIterable { case off, assist, full; var title: String { ["Off", "Assist", "Tilt to steer"][rawValue] } }
final class KeyboardMouse { static let shared = KeyboardMouse(); func releaseAll() {} }
final class ModManagerViewController: UIViewController { init(engineRunning: Bool) { super.init(nibName: nil, bundle: nil) }; required init?(coder: NSCoder) { fatalError() } }
final class SendLogViewController: UIViewController { var finished: ((String, String) -> Void)? }
extension Notification.Name { static let assetPreloadChanged = Notification.Name("PreviewAssetPreload") }
final class AssetPreloader {
 static let shared = AssetPreloader()
 enum Phase: Equatable { case unavailable(String), idle, downloading, paused, complete }
 var phase = Phase.idle
 var measured = false, removing = false
 var cachedBytes: UInt64 = 0, totalBytes: UInt64 = 0, missingBytes: UInt64 = 0
 var fraction = 0.0
 var bytesPerSecond: Double? = nil, secondsRemaining: Double? = nil
 var lastError: String? = nil
 func availableBytes() -> UInt64 { 0 }
 func refresh() {}
 func start() -> String? { "Preview only" }
 func pause() {}; func cancel() {}
 func removeDownloads(_ completion: (String?) -> Void) { completion("Preview only") }
 static func format(_ value: UInt64) -> String { "0 MB" }
 static func formatDuration(_ value: Double) -> String { "0s" }
}
enum ControlsLayout { static let isCustomized = false }
