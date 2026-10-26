from pathlib import Path
import subprocess
import json
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT.parent/'app'

class WaypointFeedback(unittest.TestCase):
    def test_feedback_does_not_confuse_queued_failure_and_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'main.swift').write_text('''
for status: Int32 in [-9,-8,-7,-6,-5,-4,-3,-2,-1,1,2] {
    guard let message = WaypointTeleportFeedback.message(status: status) else { fatalError("Missing status") }
    precondition(message.contains("Moved to waypoint") == (status == 2))
}
precondition(WaypointTeleportFeedback.message(status: 0) == nil)
precondition(WaypointTeleportFeedback.message(status: -1)!.contains("No waypoint"))
precondition(WaypointTeleportFeedback.message(status: -5)!.contains("preserved"))
''')
            subprocess.run(['/usr/bin/swiftc','-warnings-as-errors','-module-cache-path',str(p/'cache'),str(APP/'App/WaypointTeleportFeedback.swift'),str(p/'main.swift'),'-o',str(p/'test')],check=True,capture_output=True,text=True)
            subprocess.run([str(p/'test')],check=True)

    def test_both_mod_manager_routes_use_queued_handler_and_other_cheats_remain_guarded(self):
        text=(APP/'App/NativePortViewController.swift').read_text()
        self.assertEqual(text.count('.teleportHandler = { [weak self] in self?.teleportToWaypoint() }'),2)
        mod=(APP/'App/ModManagerViewController.swift').read_text()
        self.assertIn('case 2:\n            requestWaypointTeleport()',mod)
        self.assertIn('case .custom:\n                promptCustomVehicleSpawn()',mod)
        self.assertIn('guard !MugoatOnlineEnabled() && (bootedMode',text)
        self.assertIn('if MugoatOnlineEnabled()', (APP/'App/CheatMenu.swift').read_text())
        self.assertIn('VehicleCatalog.rows(',mod)
        catalog={v['model'] for v in json.loads((APP/'Resources/vehicle-catalog.json').read_text())['vehicles']}
        for name in ['sultan','buzzard','oppressor2','adder','bati']:
            self.assertIn(name,catalog)

if __name__=='__main__':unittest.main()
