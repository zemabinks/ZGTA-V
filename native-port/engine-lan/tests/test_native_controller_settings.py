"""Actual production physical-pad mapping with the framework's virtual controller.

No game, phone, Bluetooth discovery or saved user preferences are accessed.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT.parent / 'app'


class NativeControllerSettings(unittest.TestCase):
    def test_actual_character_and_multiplayer_player_list_visibility(self):
        controller = (APP / 'App/NativePortViewController.swift').read_text()
        gate = next(line.strip() for line in controller.splitlines()
                    if 'touchControls.characterSwitchEnabled =' in line)
        touch = (APP / 'App/TouchControlsView.swift').read_text()
        visibility = next(line.strip() for line in touch.splitlines()
                          if 'if characterSwitchEnabled, playing' in line)
        fixture = r'''
enum Mode { case story, sandbox }
enum Context: CaseIterable { case onFoot, car, bike, boat, plane, helicopter, submarine, menu }
struct Controls { var characterSwitchEnabled = false }
var worldToolsMode: Int32 = 1
func PGWorldToolsMode() -> Int32 { worldToolsMode }
func visible(_ bootedMode: Mode?, _ arguments: [String], _ context: Context, _ playing: Bool) -> Bool {
 var touchControls = Controls()
 ''' + gate + r'''
 let characterSwitchEnabled = touchControls.characterSwitchEnabled
 let switcher = 1
 var list: [Int] = []
 ''' + visibility + r'''
 return list.contains(switcher)
}
for mode: Mode? in [.story, .sandbox, nil] {
 for preview in [false, true] {
  let arguments = preview ? ["--preview-switch"] : []
  for context in Context.allCases {
   worldToolsMode = 2
   assert(visible(mode, arguments, context, context != .menu) == (context != .menu), "LAN keeps D-pad down for the player list in every gameplay context")
   assert(!visible(mode, arguments, context, false))
   for backend: Int32 in [0, 1] {
    worldToolsMode = backend
    let expected = (mode == .story || preview) && context != .menu
    assert(visible(mode, arguments, context, context != .menu) == expected)
    assert(!visible(mode, arguments, context, false))
   }
  }
 }
}
print("NATIVE_LAN_PLAYER_LIST_AND_STORY_CHARACTER_VISIBILITY_PASS")
'''
        with tempfile.TemporaryDirectory(prefix='zema-character-wheel-') as folder:
            work = Path(folder)
            (work / 'main.swift').write_text(fixture)
            built = subprocess.run(['/usr/bin/swiftc', '-warnings-as-errors', '-module-cache-path',
                                    str(work / 'cache'), str(work / 'main.swift'), '-o', str(work / 'fixture')],
                                   capture_output=True, text=True, timeout=90)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(work / 'fixture')], capture_output=True, text=True, timeout=10)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn('NATIVE_LAN_PLAYER_LIST_AND_STORY_CHARACTER_VISIBILITY_PASS', ran.stdout)

    def test_aircraft_player_list_does_not_overlap_flight_actions(self):
        touch = (APP / 'App/TouchControlsView.swift').read_text()
        placement = next(line.strip() for line in touch.splitlines() if 'place(switcher,' in line)
        fixture = r"""
import Foundation
import CoreGraphics
struct Context { var flying = true }
let context = Context(), switcher = 0
for safe in [CGRect(x:0,y:0,width:667,height:375), CGRect(x:0,y:0,width:825,height:340), CGRect(x:0,y:0,width:1120,height:900)] {
 let scale = max(0.8, min(1.25, min(safe.width / 832, safe.height / 407)))
 var frame = CGRect.zero
 func place(_ id: Int, _ x: CGFloat, _ y: CGFloat, _ size: CGFloat) {
  let d = max(44, size * scale)
  frame = CGRect(x:x*safe.width-d/2,y:y*safe.height-d/2,width:d,height:d)
 }
 """ + placement + r"""
 for (x,y,size): (CGFloat,CGFloat,CGFloat) in [(0.80,0.30,62),(0.935,0.26,54),(0.955,0.42,54),(0.655,0.24,46)] {
  let d = max(44,size*scale), other = CGRect(x:x*safe.width-d/2,y:y*safe.height-d/2,width:d,height:d)
  assert(!frame.intersects(other), "Player-list button overlaps a flight action")
 }
}
print("AIRCRAFT_PLAYER_LIST_LAYOUT_PASS")
"""
        with tempfile.TemporaryDirectory(prefix='zema-player-list-layout-') as folder:
            work = Path(folder); (work/'main.swift').write_text(fixture)
            built = subprocess.run(['/usr/bin/swiftc','-warnings-as-errors','-module-cache-path',str(work/'cache'),str(work/'main.swift'),'-o',str(work/'fixture')],capture_output=True,text=True,timeout=90)
            self.assertEqual(built.returncode,0,built.stderr)
            ran = subprocess.run([str(work/'fixture')],capture_output=True,text=True,timeout=10)
            self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr)
            self.assertIn('AIRCRAFT_PLAYER_LIST_LAYOUT_PASS',ran.stdout)

    def test_camera_settings_buttons_analog_triggers_and_touch_merge(self):
        with tempfile.TemporaryDirectory(prefix='zema-pad-settings-') as folder:
            work = Path(folder)
            built = subprocess.run([
                '/usr/bin/swiftc', '-warnings-as-errors', '-module-cache-path', str(work / 'cache'),
                str(APP / 'App/VirtualPad.swift'), str(ROOT / 'tests/native_controller.swift'),
                '-o', str(work / 'fixture')], capture_output=True, text=True, timeout=90)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(work / 'fixture')], capture_output=True, text=True, timeout=20)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn('NATIVE_CONTROLLER_CAMERA_SETTINGS_AND_TOUCH_MERGE_PASS', ran.stdout)
            self.assertIn('NATIVE_CONTROLLER_BUTTONS_ANALOG_TRIGGERS_AND_MERGE_PASS', ran.stdout)


if __name__ == '__main__':
    unittest.main()
