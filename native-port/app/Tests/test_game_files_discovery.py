"""Exercise actual Foundation discovery/selection without user files or preferences."""
import json,subprocess,tempfile,unittest
from pathlib import Path
APP=Path(__file__).resolve().parents[1]
class Discovery(unittest.TestCase):
 def test_production_discovery_and_selection(self):
  with tempfile.TemporaryDirectory(prefix='zgta-files-discovery-') as folder:
   root=Path(folder)
   support='''import Foundation
   enum Fixture {
    static let root = URL(fileURLWithPath: ROOT_PATH).resolvingSymlinksInPath()
    static let appRoot = root.appendingPathComponent("app-documents")
    static let manifest = root.appendingPathComponent("manifest.json")
    static let defaults = UserDefaults(suiteName: "zgta.discovery." + UUID().uuidString)!
    static let files: [(String, Int)] = [("common/config.xml",2),("common/other.dat",2),("x64/first.dat",2),("x64/second.dat",2)]
   }
   enum EnginePaths { static var manifest: String? { Fixture.manifest.path } }
   '''.replace('ROOT_PATH',json.dumps(str(root)))
   (root/'Support.swift').write_text(support)
   game=(APP/'App/GameFolder.swift').read_text()
   anchor='FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]'
   self.assertEqual(game.count(anchor),1)
   game=game.replace(anchor,'Fixture.appRoot').replace('UserDefaults.standard','Fixture.defaults')
   (root/'GameFolder.swift').write_text(game)
   (root/'main.swift').write_text((APP/'Tests/game_files_discovery.swift').read_text())
   command=['/usr/bin/swiftc','-warnings-as-errors','-module-cache-path',str(root/'cache'),str(root/'Support.swift'),str(APP/'App/GameFiles.swift'),str(root/'GameFolder.swift'),str(root/'main.swift'),'-o',str(root/'discovery')]
   built=subprocess.run(command,capture_output=True,text=True,timeout=90)
   self.assertEqual(built.returncode,0,built.stderr)
   run=subprocess.run([str(root/'discovery')],capture_output=True,text=True,timeout=15)
   self.assertEqual(run.returncode,0,run.stderr)
   self.assertIn('PASS:',run.stdout)
if __name__=='__main__':unittest.main()
