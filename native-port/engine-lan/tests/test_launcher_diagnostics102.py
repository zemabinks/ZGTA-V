"""Exercise the actual Support download handler without launching or serving GTA."""
from pathlib import Path
import subprocess
import unittest

class LauncherDiagnostics102(unittest.TestCase):
    def test_actual_support_download_records_bounded_identity(self):
        result=subprocess.run(['node',str(Path(__file__).with_name('launcher_diagnostics102.cjs'))],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

if __name__=='__main__':unittest.main()
