"""Actual browser restore against an isolated asynchronous transaction fixture."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]

class SaveRestore(unittest.TestCase):
    def test_merged_restore_stays_exportable_and_atomic(self):
        result=subprocess.run(['node',str(ROOT/'tests/save_restore.cjs')],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

if __name__=='__main__':unittest.main()
