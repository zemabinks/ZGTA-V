"""Actual queued native world-tool state and command-ABI tests; no game/device."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT.parent/'app'

class NativeWorldTools(unittest.TestCase):
    def test_queued_native_state_calls_ownership_ground_and_cleanup(self):
        with tempfile.TemporaryDirectory(prefix='zema-native-world-tools-') as folder:
            exe=Path(folder)/'fixture'
            result=subprocess.run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-I',str(APP/'Source'),str(APP/'Tests/world_tools.c'),'-o',str(exe)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('QUEUED_WORLD_TOOLS_LOCAL_OWNERSHIP_GROUND_TIMEOUT_CLEANUP_PASS',result.stdout)

    def test_engine_control_update_owns_both_queues_and_legacy_guard_stays(self):
        source=(APP/'Source/EngineHost.c').read_text()
        self.assertIn('int PGWorldToolsMode(void) { return MugoatOnlineEnabled() ? 0 : 1; }',source)
        control=source[source.index('void pg_virtual_pad_apply('):]
        self.assertEqual(control.count('pg_process_vehicle_spawn(instance);'),1)
        self.assertEqual(control.count('pg_process_waypoint_teleport(instance);'),1)
        self.assertIn('if (pad == 12840656)',control)
        self.assertIn('if (MugoatOnlineEnabled()) return;',source)

if __name__=='__main__':unittest.main()
