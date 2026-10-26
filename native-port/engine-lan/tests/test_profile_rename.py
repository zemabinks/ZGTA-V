"""Real Rust profile + Swift private storage, only disposable fixture directories."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
LIB=Path(os.environ.get('ZEMA_TEST_LAN_LIBRARY',str(ROOT.parent/'app/Build/EngineLAN/RustHost/debug/libzema_engine_lan.a')))
class ProfileRename(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='zgta-name-fixture-')
        cls.directory=Path(cls.temp.name).resolve();cls.binary=cls.directory/'fixture'
        result=subprocess.run(['/usr/bin/swiftc','-warnings-as-errors','-I',str(ROOT),'-module-cache-path',str(cls.directory/'cache'),str(ROOT/'EngineLanProfileFile.swift'),str(ROOT/'tests/profile_rename.swift'),str(LIB),'-o',str(cls.binary)],capture_output=True,text=True,timeout=90)
        if result.returncode:raise RuntimeError(result.stderr)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def run_case(self,mode):
        folder=self.directory/('zema-engine-lan-'+mode);folder.mkdir(mode=0o700)
        result=subprocess.run([str(self.binary),str(folder),mode],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        return folder,result.stdout
    def test_browser_name_transaction_and_async_input(self):
        result=subprocess.run(['node',str(ROOT/'tests/profile_rename.cjs')],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('ASYNC_EDIT_PASS',result.stdout)
    def test_rename_preserves_profile_and_reloads(self):
        folder,output=self.run_case('success');self.assertIn('ROUNDTRIP_PASS',output)
        result=subprocess.run([str(self.binary),str(folder),'reload'],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertIn('DURABLE_RELOAD_PASS',result.stdout)
    def test_directory_sync_failure_rolls_back(self):self.assertIn('ROLLBACK_OR_EXTERNAL_GUARD_PASS',self.run_case('sync-failure')[1])
    def test_unsafe_backup_rolls_back(self):self.run_case('unsafe-backup')
    def test_external_writer_before_rename_is_not_erased(self):self.run_case('external-before')
    def test_same_name_still_rejects_changed_storage(self):self.run_case('external-before-same')
    def test_external_writer_during_failed_sync_is_not_erased(self):self.run_case('external-during-sync')
    def test_admitted_name_cannot_change_even_when_disconnected(self):self.assertIn('RENAME_REFUSED_PASS',self.run_case('post-admission')[1])
if __name__=='__main__':unittest.main()
