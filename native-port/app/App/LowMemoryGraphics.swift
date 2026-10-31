import Foundation

/// Memory residency policy, independent of graphics presets and display choices.
/// Automatic preserves the standard policy on devices with 3400 MiB or more.
enum MemoryProfile: Int, CaseIterable {
    case automatic, standard, reduced
    var title: String { ["Automatic", "Standard", "Reduced memory"][rawValue] }
}
enum LowMemoryGraphics {
    static func isEnabled(physicalMemoryBytes: UInt64 = ProcessInfo.processInfo.physicalMemory, profile: MemoryProfile = .automatic) -> Bool {
        if profile == .reduced { return true }
        if profile == .standard { return false }
        return physicalMemoryBytes > 0 && physicalMemoryBytes < 3400 * 1_048_576
    }
}
