"""Cross-language save transfer without touching production browser/app data."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class SaveTransfer(unittest.TestCase):
    def run_checked(self, args):
        result = subprocess.run(args, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_archive_validation(self):
        self.run_checked(['node', str(ROOT/'tests/save_transfer.cjs')])

    def test_unmodified_iphone_store_roundtrip(self):
        if not shutil.which('swiftc'):
            self.skipTest('Existing Swift compiler unavailable; no install attempted.')
        with tempfile.TemporaryDirectory(prefix='zgta-save-transfer-') as temp:
            folder=Path(temp)
            self.run_checked(['node',str(ROOT/'tests/save_transfer.cjs'),'emit',str(folder/'browser.mugoatsave')])
            self.run_checked(['swiftc','-module-cache-path',str(folder/'module-cache'),
                              str(ROOT.parent/'app/App/SaveStore.swift'),str(ROOT/'tests/save_transfer.swift'),
                              '-o',str(folder/'save-transfer')])
            self.run_checked([str(folder/'save-transfer'),str(folder)])
            self.run_checked(['node',str(ROOT/'tests/save_transfer.cjs'),'verify-native',str(folder/'iphone.mugoatsave')])

if __name__=='__main__':unittest.main()
