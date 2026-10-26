import Foundation
#if canImport(FoundationXML)
import FoundationXML
#endif

struct ModError: LocalizedError {
    let message: String
    private let template: String
    private let arguments: [CVarArg]
    var errorDescription: String? { localizedMessage(language: L10n.language, catalog: L10n.translations) }
    func localizedMessage(language: String, catalog: [String: [String: String]]) -> String {
        let translated = L10n.text(template, language: language, catalog: catalog)
        return arguments.isEmpty ? translated : String(format: translated, arguments: arguments)
    }
    init(_ message: String, _ arguments: CVarArg...) {
        self.template = message; self.arguments = arguments
        // Preserve original diagnostic text for ModRuntime's existing classification.
        self.message = arguments.isEmpty ? message : String(format: message, arguments: arguments)
    }
}

/// Reads the open RPF7 table and XML metadata; geometry stays in the original archive.
/// Format reference: dexyfex/CodeWalker, RpfFile.cs (binary/resource entry layouts).
struct RPFArchive {
    struct Entry {
        let path: String
        let offset: Int
        let size: Int
        let unpacked: Int
        let encrypted: Bool
        let compressed: Bool
        let resourceVersion: Int?
    }
    let bytes: Data
    let entries: [Entry]

    init(url: URL) throws { try self.init(bytes: Data(contentsOf: url, options: .mappedIfSafe)) }
    init(bytes: Data) throws {
        self.bytes = bytes
        func word(_ at: Int) throws -> UInt32 {
            guard at >= 0, at <= bytes.count - 4 else { throw ModError("RPF data is truncated.") }
            return bytes[at..<(at + 4)].enumerated().reduce(UInt32(0)) { $0 | UInt32($1.element) << (8 * $1.offset) }
        }
        guard try word(0) == 0x52504637 else { throw ModError("This is not a GTA V Legacy RPF7 archive.") }
        let count = Int(try word(4)), namesSize = Int(try word(8))
        guard count > 0, count <= 100_000, namesSize > 0, namesSize <= 8 * 1024 * 1024,
              16 + count * 16 + namesSize <= bytes.count else { throw ModError("The RPF file table is corrupt.") }
        guard try word(12) == 0x4e45504f else { throw ModError("The RPF table is encrypted. Export an open archive using OpenIV before importing.") }
        let namesStart = 16 + count * 16
        func name(_ offset: Int) throws -> String {
            guard offset >= 0, offset < namesSize else { throw ModError("Invalid RPF filename.") }
            let tail = bytes[(namesStart + offset)..<(namesStart + namesSize)]
            guard let zero = tail.firstIndex(of: 0), let text = String(data: bytes[(namesStart + offset)..<zero], encoding: .utf8),
                  text.utf8.count <= 255, !text.contains("/"), !text.contains("\\"), text != ".", text != ".." else { throw ModError("Invalid path in RPF archive.") }
            return text.lowercased()
        }
        var output: [Entry] = [], visited = Set<Int>()
        func walk(_ index: Int, parent: String, depth: Int) throws {
            guard depth < 32, index >= 0, index < count, visited.insert(index).inserted else { throw ModError("The RPF directory structure is corrupt or cyclic.") }
            let at = 16 + index * 16, first = try word(at), second = try word(at + 4)
            let directory = second == 0x7fffff00
            let text = try name(Int(directory ? first : first & 0xffff))
            guard index == 0 || !text.isEmpty else { throw ModError("An RPF entry has no name.") }
            let path = parent.isEmpty ? text : parent + "/" + text
            if directory {
                let start = Int(try word(at + 8)), length = Int(try word(at + 12))
                guard start <= count, length <= count - start else { throw ModError("RPF directory exceeds bounds.") }
                for child in start..<(start + length) { try walk(child, parent: path, depth: depth + 1) }
            } else {
                let resource = second & 0x80000000 != 0
                let packed = UInt64(first) | UInt64(second) << 32
                var size = Int(packed >> 16 & 0xffffff)
                let compressed = size != 0
                let offset = Int(packed >> 40 & (resource ? 0x7fffff : 0xffffff)) * 512
                let unpacked = Int(try word(at + 8)), flags = try word(at + 12)
                if resource && size == 0xffffff {
                    guard offset <= bytes.count - 16 else { throw ModError("RPF resource is truncated.") }
                    size = Int(bytes[offset + 7]) | Int(bytes[offset + 14]) << 8 | Int(bytes[offset + 5]) << 16 | Int(bytes[offset + 2]) << 24
                }
                if !resource && size == 0 { size = unpacked }
                guard offset >= namesStart + namesSize, size >= 0, offset <= bytes.count, size <= bytes.count - offset else { throw ModError("RPF file data exceeds bounds.") }
                output.append(Entry(path: path, offset: offset, size: size, unpacked: unpacked,
                                    encrypted: !resource && flags != 0, compressed: compressed,
                                    resourceVersion: resource ? Int(((UInt32(unpacked) >> 28) << 4) | (flags >> 28)) : nil))
            }
        }
        try walk(0, parent: "", depth: 0)
        guard visited.count == count, Set(output.map(\.path)).count == output.count else { throw ModError("The RPF table contains orphaned or duplicate entries.") }
        entries = output
    }

    func metadata(_ entry: Entry) throws -> Data {
        guard entry.resourceVersion == nil, !entry.encrypted, entry.unpacked > 0,
              entry.unpacked <= 8 * 1024 * 1024 else { throw ModError("Mod metadata is encrypted or too large: %@", entry.path) }
        let data = bytes.subdata(in: entry.offset..<(entry.offset + entry.size))
        if !entry.compressed { return data }
        var result = Data(count: entry.unpacked)
        let valid = result.withUnsafeMutableBytes { out in data.withUnsafeBytes { input in
            gi_inflate_raw(input.baseAddress, UInt32(data.count), out.baseAddress, UInt32(entry.unpacked))
        } }
        guard valid == 1 else { throw ModError("Could not decompress metadata: %@", entry.path) }
        return result
    }

    func nested(_ entry: Entry) throws -> RPFArchive {
        guard !entry.encrypted, entry.resourceVersion == nil, !entry.compressed else { throw ModError("Nested RPF is encrypted or compressed: %@", entry.path) }
        return try RPFArchive(bytes: bytes.subdata(in: entry.offset..<(entry.offset + entry.size)))
    }
}

final class ModXML: NSObject, XMLParserDelegate {
    private var current = "", text = ""
    private(set) var values: [String: [String]] = [:]
    static func read(_ data: Data) throws -> ModXML {
        let delegate = ModXML(), parser = XMLParser(data: data)
        parser.shouldResolveExternalEntities = false; parser.delegate = delegate
        guard parser.parse() else { throw ModError("Invalid mod XML.") }
        return delegate
    }
    func parser(_ parser: XMLParser, didStartElement name: String, namespaceURI: String?, qualifiedName: String?, attributes: [String: String]) { current = name; text = "" }
    func parser(_ parser: XMLParser, foundCharacters string: String) { text += string }
    func parser(_ parser: XMLParser, didEndElement name: String, namespaceURI: String?, qualifiedName: String?) {
        if name == current { let value = text.trimmingCharacters(in: .whitespacesAndNewlines); if !value.isEmpty { values[name, default: []].append(value) } }
        current = ""; text = ""
    }
}

struct ModPack {
    let name: String
    let url: URL
    /// Every name the pack defines (vehicles, peds, texture and model files): used to detect clashes.
    let models: [String]
    /// Only the <modelName> entries of its vehicles.meta: the names that can be spawned as vehicles.
    let vehicleModels: [String]
    let archive: RPFArchive
    static func validName(_ name: String) -> Bool {
        !name.isEmpty && name.utf8.count <= 63 && name.utf8.allSatisfy { (97...122).contains($0) || (48...57).contains($0) || $0 == 95 }
    }
    init(url: URL) throws {
        let archive = try RPFArchive(url: url)
        guard let setup = archive.entries.first(where: { $0.path == "setup2.xml" }),
              archive.entries.contains(where: { $0.path == "content.xml" }) else { throw ModError("DLC package is missing setup2.xml or content.xml.") }
        let xml = try ModXML.read(archive.metadata(setup))
        guard let device = xml.values["deviceName"]?.first?.lowercased(), device.hasPrefix("dlc_"), Self.validName(String(device.dropFirst(4))) else { throw ModError("DLC package has no valid deviceName.") }
        name = String(device.dropFirst(4)); self.url = url; self.archive = archive
        var models = Set<String>()
        for entry in archive.entries where entry.path.hasSuffix("vehicles.meta") {
            for model in (try? ModXML.read(archive.metadata(entry)).values["modelName"]) ?? [] {
                let model = model.lowercased(); guard Self.validName(model) else { throw ModError("Invalid model name: %@", model) }; models.insert(model)
            }
        }
        // Texture dictionaries (…_mods, vehshare…) and ped names are not vehicles: listing them in the
        // spawner made most "Xe Mod" rows fail while NPCs drove the real model.
        self.vehicleModels = models.sorted()
        for entry in archive.entries where entry.path.hasSuffix("peds.meta") {
            let meta = try? ModXML.read(archive.metadata(entry))
            for model in (meta?.values["ModelName"] ?? []) + (meta?.values["Name"] ?? []) {
                let model = model.lowercased(); if Self.validName(model) { models.insert(model) }
            }
        }
        for entry in archive.entries where entry.path.hasSuffix(".rpf") {
            let nested = try archive.nested(entry)
            for resource in nested.entries where resource.path.hasSuffix(".yft") || resource.path.hasSuffix(".ytd") || resource.path.hasSuffix(".ydd") {
                let expected = resource.path.hasSuffix(".yft") ? 162 : resource.path.hasSuffix(".ytd") ? 13 : 165
                guard resource.resourceVersion == expected else { throw ModError("Package %@ uses incompatible Enhanced assets. Use Legacy assets.", name) }
                let base = (resource.path as NSString).lastPathComponent.components(separatedBy: ".").first?.lowercased() ?? ""
                if !base.isEmpty && Self.validName(base) && !base.hasSuffix("_hi") {
                    models.insert(base)
                }
            }
        }
        guard !models.isEmpty else { throw ModError("DLC contains no valid vehicle or character models.") }
        self.models = models.sorted()
    }
}
