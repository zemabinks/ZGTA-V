from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]

class BrowserWorldTools(unittest.TestCase):
    def test_unified_mod_manager_keeps_actions_imports_and_input_boundaries(self):
        result=subprocess.run(['node',str(ROOT/'tests/mod_manager_fixture.cjs'),str(ROOT)],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_actual_queued_world_tools_ownership_cancel_timeout_and_cleanup(self):
        result=subprocess.run(['node',str(ROOT/'tests/browser_world_tools_fixture.cjs'),str(ROOT/'browser-trainer.js')],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('"gameplayVerified":false',result.stdout)
        self.assertIn('"passed":21',result.stdout)

    def test_lan_ui_queues_world_tools_and_keeps_cheat_button_disabled(self):
        result=subprocess.run(['node',str(ROOT/'tests/tools_ui_fixture.cjs'),str(ROOT)],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('KEEPS_CHEATS_DISABLED_PASS',result.stdout)

if __name__=='__main__':unittest.main()
