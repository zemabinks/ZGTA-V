from pathlib import Path
import json
import subprocess
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT.parent / 'app'


class VehicleCatalogTests(unittest.TestCase):
    def test_generated_catalog_is_identical_for_both_platforms(self):
        result = subprocess.run(['python3', '-B', str(APP/'Scripts/generate_vehicle_catalog.py'), '--check'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_browser_search_categories_and_mod_launch_boundaries(self):
        result = subprocess.run(['node', str(ROOT/'tests/vehicle_catalog_fixture.cjs'), str(ROOT)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_native_catalog_rows_and_search_execute(self):
        harness = r'''
import Foundation
import CoreGraphics
let json = try JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))) as! [String: Any]
let reference = json["vehicles"] as! [[String: Any]]
precondition(VehicleCatalog.vehicles.count == reference.count)
for (entry, row) in zip(VehicleCatalog.vehicles, reference) {
    precondition(entry.model == row["model"] as! String && entry.name == row["name"] as! String)
    precondition(entry.category == row["category"] as! String && entry.base == row["base"] as! Bool)
    precondition(entry.kind == row["kind"] as! String)
}
precondition(VehicleCatalog.vehicles.first { $0.model == "buzzard" }!.thumbnailURL!.absoluteString == "https://docs-backend.fivem.net/vehicles/buzzard.webp")
precondition(VehicleCatalog.Entry(model: "sultan", name: "Custom", category: "Installed mods", base: false, kind: "mod").thumbnailURL == nil)
precondition(VehicleCatalog.Entry(model: "../other", name: "Bad", category: "Compacts", base: false, kind: "vehicle").thumbnailURL == nil)
let supra = VehicleCatalog.Entry(model: "casup", name: "casup", category: "Installed mods", base: false, kind: "mod")
precondition(supra.thumbnailURL?.isFileURL == true)
precondition(supra.thumbnailURL?.lastPathComponent == "mod-vehicle-casup.png")
precondition(supra.thumbnailCredit == "Image supplied from the original Supra mod page.")
precondition(VehicleCatalog.Entry(model: "unknownmod", name: "Unknown", category: "Installed mods", base: false, kind: "mod").thumbnailURL == nil)
let collapsed = VehicleCatalog.rows(query: "", expanded: [], includeDLC: true, modModels: [])
precondition(collapsed.count == VehicleCatalog.categories.count + 3)
let result = VehicleCatalog.rows(query: "bmx", expanded: [], includeDLC: true, modModels: [])
precondition(result.contains { if case let .vehicle(v) = $0 { return v.model == "bmx" }; return false })
let base = VehicleCatalog.rows(query: "", expanded: Set(VehicleCatalog.categories.map(\.id)), includeDLC: false, modModels: [])
let baseCount = base.filter { if case .vehicle = $0 { return true }; return false }.count
precondition(baseCount == 298)
let mods = VehicleCatalog.rows(query: "", expanded: ["Installed mods"], includeDLC: false, modModels: ["customcar", "CUSTOMCAR", "bad<script>"])
precondition(mods.filter { if case .vehicle = $0 { return true }; return false }.count == 1)
precondition(VehicleCatalog.vehicles.first { $0.model == "freight" }!.canSpawn == false)
precondition(VehicleCatalog.vehicles.first { $0.model == "buzzard" }!.category == "Helicopters")
precondition(VehicleCatalog.vehicles.first { $0.model == "luxor" }!.category == "Planes")
precondition(VehicleCatalog.vehicles.first { $0.model == "bati" }!.category == "Motorcycles")

func checkChange(_ old: [VehicleCatalog.Row], _ new: [VehicleCatalog.Row]) {
    let before = old.map(\.id), after = new.map(\.id)
    precondition(Set(before).count == before.count && Set(after).count == after.count)
    let change = VehicleCatalog.rowChanges(from: old, to: new)
    var rebuilt = before
    for offset in change.removed.sorted(by: >) { rebuilt.remove(at: offset) }
    for offset in change.inserted.sorted() { rebuilt.insert(after[offset], at: offset) }
    precondition(rebuilt == after, "UITableView row edits must produce the exact next snapshot")
}
for category in VehicleCatalog.categories + [VehicleCatalog.Category(id: "Installed mods", name: "Installed mods", icon: "")] {
    for withDLC in [true, false] {
        let old = VehicleCatalog.rows(query: "", expanded: [], includeDLC: withDLC, modModels: ["customcar"])
        let new = VehicleCatalog.rows(query: "", expanded: [category.id], includeDLC: withDLC, modModels: ["customcar"])
        checkChange(old, new); checkChange(new, old)
        let expansion = VehicleCatalog.rowChanges(from: old, to: new)
        let collapse = VehicleCatalog.rowChanges(from: new, to: old)
        precondition(expansion.removed.isEmpty && collapse.inserted.isEmpty)
        precondition(expansion.inserted.allSatisfy { if case .vehicle = new[$0] { return true }; return false })
        precondition(collapse.removed.allSatisfy { if case .vehicle = new[$0] { return true }; return false })
    }
}
let emptyOpen = VehicleCatalog.rows(query: "", expanded: ["Installed mods"], includeDLC: true, modModels: [])
checkChange(collapsed, emptyOpen); checkChange(emptyOpen, collapsed)
let allOpen = VehicleCatalog.rows(query: "", expanded: Set(VehicleCatalog.categories.map(\.id)), includeDLC: true, modModels: [])
for query in ["", "bmx", "sport", "no-such-vehicle"] {
    let searched = VehicleCatalog.rows(query: query, expanded: [], includeDLC: false, modModels: ["customcar"])
    checkChange(allOpen, searched); checkChange(searched, allOpen)
}
precondition(VehicleCatalog.rowChanges(from: collapsed, to: collapsed).removed.isEmpty)
print("PASS stable row updates for all categories, DLC filter, search, empty mods; category cells retained")

precondition(VehicleCatalog.categories.first { $0.id == "Helicopters" }!.icon == "zgta.helicopter")
precondition(VehicleCatalog.categories.first { $0.id == "Planes" }!.icon == "airplane")
let custom = Set(VehicleCatalog.categories.filter { $0.icon.hasPrefix("zgta.") }.map { String($0.icon.dropFirst(5)) })
precondition(custom == VehicleCategoryArtwork.names)
var drawings = Set<Data>()
for name in custom.sorted() {
    var pixels = [UInt8](repeating: 0, count: 64 * 64 * 4)
    pixels.withUnsafeMutableBytes { buffer in
        let context = CGContext(data: buffer.baseAddress!, width: 64, height: 64, bitsPerComponent: 8, bytesPerRow: 64 * 4, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
        context.scaleBy(x: 2, y: 2)
        context.setStrokeColor(CGColor(gray: 1, alpha: 1))
        VehicleCategoryArtwork.draw(name, in: context)
    }
    precondition(pixels.contains { $0 != 0 }, "Category icon must draw actual pixels")
    precondition(drawings.insert(Data(pixels)).inserted, "Category drawings must be distinct")
}
print("PASS all 10 category pictograms render distinct nonempty artwork, helicopter distinct from plane")


print("PASS native catalog parity, collapsed rows, search, base filter, deduplicated mods and special trains")
'''
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy2(APP/'Resources/mod-vehicle-casup.png',Path(tmp)/'mod-vehicle-casup.png')
            main = Path(tmp)/'main.swift'
            main.write_text(harness)
            exe = Path(tmp)/'catalog-test'
            result = subprocess.run(['xcrun', 'swiftc', '-module-cache-path', str(Path(tmp)/'module-cache'), str(APP/'App/VehicleCatalog.swift'), str(APP/'App/VehicleCatalogData.swift'), str(APP/'App/VehicleCategoryArtwork.swift'), str(main), '-o', str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe), str(APP/'Resources/vehicle-catalog.json')], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
