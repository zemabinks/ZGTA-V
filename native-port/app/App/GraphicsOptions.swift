import Foundation
import Metal
import UIKit
import os

/// Graphics presets. The engine reads quality settings once at boot; only the
/// resolution can change while it runs.
enum GraphicsPreset: Int, CaseIterable {
    case battery, performance, balanced, quality, ultra, max

    var title: String { [L10n.text("Battery"), L10n.text("Performance"), L10n.text("Balanced"), L10n.text("Quality"), L10n.text("High"), L10n.text("Maximum (4K)")][rawValue] }
    /// Render height in pixels; width follows the screen's shape.
    var height: Int { [432, 540, 720, 900, 1080, 2160][rawValue] }
    var detail: String {
        [L10n.text("432p · lowest memory and battery use"), L10n.text("540p · reduced heavy effects"), L10n.text("720p · balance clarity and speed"),
         L10n.text("900p · more detail and draw distance"), L10n.text("1080p · higher shadows and reflections"),
         L10n.text("2160p (4K) · maximum graphics detail (Native 4K)")][rawValue]
    }

    /// Engine command-line options. Shader quality never goes below 1 (the
    /// low shader set is mostly missing), and must not exceed 1 (Quality 2 shaders
    /// are not compiled for Metal). Tessellation, MSAA and depth of field stay off.
    var engineOptions: [String] {
        switch self {
        case .battery, .performance:
            return ["-shaderQuality=1", "-textureQuality=0", "-shadowQuality=-1", "-reflectionQuality=0", "-particleQuality=0",
                    "-grassQuality=0", "-cityDensity=0", "-lodScale=0", "-pedLodBias=0", "-vehicleLodBias=0", "-pedVariety=0", "-vehicleVariety=0"]
        case .balanced:
            return ["-shaderQuality=1", "-textureQuality=0", "-shadowQuality=0", "-reflectionQuality=0", "-particleQuality=0",
                    "-grassQuality=0", "-cityDensity=0.2", "-lodScale=0.2", "-pedLodBias=0", "-vehicleLodBias=0", "-pedVariety=0.2", "-vehicleVariety=0.2"]
        case .quality:
            return ["-shaderQuality=1", "-textureQuality=1", "-shadowQuality=0", "-reflectionQuality=1", "-particleQuality=1",
                    "-grassQuality=1", "-cityDensity=0.4", "-lodScale=0.4", "-pedLodBias=0.2", "-vehicleLodBias=0.2", "-pedVariety=0.4", "-vehicleVariety=0.4"]
        case .ultra:
            return ["-shaderQuality=1", "-textureQuality=1", "-shadowQuality=1", "-reflectionQuality=1", "-particleQuality=1",
                    "-grassQuality=1", "-cityDensity=0.6", "-lodScale=0.6", "-pedLodBias=0.4", "-vehicleLodBias=0.4", "-pedVariety=0.6", "-vehicleVariety=0.6"]
        case .max:
            return ["-shaderQuality=1", "-textureQuality=1", "-shadowQuality=1", "-reflectionQuality=2", "-particleQuality=1",
                    "-grassQuality=1", "-cityDensity=0.8", "-lodScale=0.8", "-pedLodBias=0.5", "-vehicleLodBias=0.5", "-pedVariety=0.8", "-vehicleVariety=0.8"]
        }
    }
}

/// What this device can afford, measured before the engine starts.
struct DeviceTier {
    /// Measured OS process allowance for diagnostics; never an allocation cap.
    let processAllowanceMB: Int
    let physicalMemoryMB: Int
    let model: String
    let supportsBCTextures: Bool

    static func probe() -> DeviceTier {
        var info = utsname(); uname(&info)
        let model = withUnsafeBytes(of: &info.machine) { String(decoding: $0.prefix { $0 != 0 }, as: UTF8.self) }
        let device = MTLCreateSystemDefaultDevice()
        let supportsBC: Bool
        if #available(iOS 16.4, *) { supportsBC = device?.supportsBCTextureCompression ?? false }
        else { supportsBC = false }
        return DeviceTier(processAllowanceMB: Self.measureProcessAllowanceMB(),
                          physicalMemoryMB: Int(ProcessInfo.processInfo.physicalMemory / 1_048_576),
                          model: model,
                          supportsBCTextures: supportsBC)
    }

    /// Jetsam limit = memory still available + what the app already uses.
    private static func measureProcessAllowanceMB() -> Int {
        var vm = task_vm_info_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<integer_t>.size)
        let result = withUnsafeMutablePointer(to: &vm) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) { task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &count) }
        }
        let footprint = result == KERN_SUCCESS ? Int(vm.phys_footprint) : 0
        return (Int(os_proc_available_memory()) + footprint) / 1_048_576
    }

    /// Recommend from the device's actual RAM; all presets remain selectable.
    var recommended: GraphicsPreset {
        physicalMemoryMB < 3400 ? .battery : physicalMemoryMB < 4600 ? .performance : physicalMemoryMB < 6000 ? .balanced : physicalMemoryMB < 8000 ? .quality : physicalMemoryMB < 12000 ? .ultra : .max
    }
    /// Every preset can be chosen; those above the recommended one show a warning.
    var allowed: [GraphicsPreset] { GraphicsPreset.allCases }
    /// Presets shown with a warning because they may run out of memory or heat up.
    func risky(_ preset: GraphicsPreset) -> Bool { preset.rawValue > recommended.rawValue }
    var summary: String { "\(model) · \(String(format: "%.1f", Double(physicalMemoryMB) / 1024)) GB RAM\(supportsBCTextures ? " · BC textures" : "")" }
}

enum GraphicsConfiguration {
    /// The screen's height in pixels (the "Native" resolution).
    static var nativeHeight: Int {
        let screen = UIScreen.main
        let raw = Int(min(screen.nativeBounds.width, screen.nativeBounds.height))
        return raw > 0 ? raw : 720
    }
    /// Resolutions offered in Settings, besides "Auto" (the detail preset's own).
    static var resolutionChoices: [Int] {
        let standard = [432, 540, 720, 900, 1080, 1290, 1440, 1620, 2160]
        var list = standard
        if !list.contains(nativeHeight) && nativeHeight >= 540 {
            list.append(nativeHeight)
        }
        list.sort()
        return list
    }
    /// Width/height to render at: the chosen height (or the preset's), shaped like the screen so the
    /// picture is not stretched.
    static func size(for preset: GraphicsPreset, renderHeight: Int, screen: CGSize, matchScreenShape: Bool, renderScale: Double = 1) -> (Int, Int) {
        let aspect = matchScreenShape && screen.height > 0 ? max(screen.width, screen.height) / min(screen.width, screen.height) : 16.0 / 9.0
        var height = Double(renderHeight > 0 ? renderHeight : preset.height)
        if renderScale.isFinite && renderScale > 0 && renderScale <= 1 { height *= renderScale }
        height = min(max(height, 360), 2160.0)
        let width = min(height * aspect, 3840.0)
        func even(_ value: Double) -> Int { Int(value.rounded()) & ~1 }
        return (max(even(width), 320), max(even(height), 240))
    }

    /// Pass the chosen settings to the engine. Call before PGStartEngine.
    static func apply(_ settings: GameSettings, screen: CGSize, renderScale: Double = 1, frameIntervalOverride: Int32? = nil) -> String {
        PGSetEngineMemoryMB(Int32(settings.engineMemoryMB))
        PGSetMemoryProfile(Int32(settings.memoryProfile.rawValue))
        let preset = settings.graphicsPreset
        let (width, height) = size(for: preset, renderHeight: settings.renderHeight, screen: screen, matchScreenShape: settings.matchScreenShape, renderScale: renderScale)
        let effectiveCap = settings.frameRateCap
        let chosenInterval: Int32 = effectiveCap == 0 ? 0 : effectiveCap == 60 ? 1 : 2
        let requestedInterval = frameIntervalOverride.flatMap { (0...4).contains($0) ? $0 : nil } ?? chosenInterval
        let interval = requestedInterval
        let options = preset.engineOptions
        var pointers = options.map { strdup($0) }
        defer { pointers.forEach { free($0) } }
        pointers.withUnsafeMutableBufferPointer { buffer in
            buffer.baseAddress!.withMemoryRebound(to: UnsafePointer<CChar>?.self, capacity: buffer.count) {
                PGConfigureEngine($0, UInt32(buffer.count), Int32(width), Int32(height), interval)
            }
        }
        // Even frame pacing when the cap is below the screen's refresh rate (30 on 60 Hz, 30/60 on 120 Hz).
        let cap = interval == 0 ? 0 : 60 / Int(interval)
        PGSetPresentPacing(cap > 0 && cap < UIScreen.main.maximumFramesPerSecond ? 1.0 / Double(cap) : 0)
        return "\(preset.title) \(width)×\(height) at \(GameSettings.frameRateTitle(effectiveCap))"
    }
}
