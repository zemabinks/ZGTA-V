"""Check actual iOS group/action mapping and independent saved memory choice."""
from pathlib import Path
import subprocess, tempfile, unittest
APP=Path(__file__).resolve().parents[2]/'app'

class SettingsLayout101(unittest.TestCase):
 def test_group_rows_reach_each_existing_action_once(self):
  source=(APP/'App/SettingsViewController.swift').read_text()
  self.assertIn('selectedSection == .graphics ? UITableView.automaticDimension : 14',source)
  start=source.index('    private func settingsIndex(')
  end=source.index('\n    private func category(',start)
  method=source[start:end].replace('private func settingsIndex','func settingsIndex')
  fixture='''import Foundation
struct IndexPath {var row:Int;var section:Int}
enum Section:Int {case graphics=2,controls=3}
struct Tier {let allowed=Array(0..<6)}
struct Settings {let tier=Tier()}
struct Subject {var selectedSection:Section?;let settings=Settings()
'''+method+'''
}
let graphics=Subject(selectedSection:.graphics)
var visited=Set<Int>()
for (section,rows) in [6,3,2].enumerated() {
 for row in 0..<rows {
  let actual=graphics.settingsIndex(IndexPath(row:row,section:section))
  assert(actual.section==Section.graphics.rawValue)
  assert(visited.insert(actual.row).inserted)
 }
}
assert(visited==Set(0..<11))
assert(graphics.settingsIndex(IndexPath(row:0,section:1)).row==6) // resolution
assert(graphics.settingsIndex(IndexPath(row:2,section:1)).row==9) // FPS
assert(graphics.settingsIndex(IndexPath(row:0,section:2)).row==10) // memory profile
assert(graphics.settingsIndex(IndexPath(row:1,section:2)).row==8) // existing RAM choice
let controls=Subject(selectedSection:.controls)
for row in 0..<12 {assert(controls.settingsIndex(IndexPath(row:row,section:0)).row==row)}
'''
  settings=(APP/'App/GameSettings.swift').read_text()
  memory=settings[settings.index('    var memoryProfile:'):settings.index('    var resolutionScale:')]
  fixture+='''
final class Saved {let defaults:UserDefaults
 init(_ defaults:UserDefaults){self.defaults=defaults}
'''+memory+'''
}
let suite="zgta-memory101-"+UUID().uuidString
let defaults=UserDefaults(suiteName:suite)!
defer{defaults.removePersistentDomain(forName:suite)}
defaults.set(4,forKey:"graphicsPreset");defaults.set(720,forKey:"renderHeight");defaults.set(60,forKey:"frameRateCap")
let saved=Saved(defaults);assert(saved.memoryProfile == .automatic)
for mode in MemoryProfile.allCases {
 saved.memoryProfile=mode;assert(saved.memoryProfile==mode)
 assert(defaults.integer(forKey:"graphicsPreset")==4)
 assert(defaults.integer(forKey:"renderHeight")==720)
 assert(defaults.integer(forKey:"frameRateCap")==60)
}
defaults.set(99,forKey:"memoryProfile");assert(saved.memoryProfile == .automatic)
print("PASS iOS settings group/action mapping and independent persisted memory policy")
'''
  with tempfile.TemporaryDirectory(prefix='zgta-settings101-') as folder:
   p=Path(folder);(p/'main.swift').write_text(fixture)
   built=subprocess.run(['swiftc','-warnings-as-errors','-module-cache-path',str(p/'cache'),str(APP/'App/LowMemoryGraphics.swift'),str(p/'main.swift'),'-o',str(p/'fixture')],capture_output=True,text=True)
   self.assertEqual(built.returncode,0,built.stderr)
   run=subprocess.run([str(p/'fixture')],capture_output=True,text=True,timeout=10)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr)

if __name__=='__main__':unittest.main()
