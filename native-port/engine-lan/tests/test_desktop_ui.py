"""Desktop lobby interaction contract; never starts a relay or accesses real saves."""
import subprocess
from pathlib import Path
import unittest

class DesktopUI(unittest.TestCase):
    def test_real_inline_lobby_controller(self):
        result=subprocess.run(['node',str(Path(__file__).with_name('desktop_lobby_setup.cjs'))],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

if __name__=='__main__':unittest.main()
