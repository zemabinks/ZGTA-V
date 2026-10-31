"""Actual native profile disk/reload and serialized checkpoint regression tests."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIB = Path(os.environ.get('ZEMA_TEST_LAN_LIBRARY', str(ROOT.parent / 'app/Build/EngineLAN/RustHost/debug/libzema_engine_lan.a')))


class ProfileCheckpoint102(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='zgta-checkpoint102-')
        cls.folder = Path(cls.temp.name).resolve()
        cls.binary = cls.folder / 'fixture'
        result = subprocess.run(['/usr/bin/swiftc', '-warnings-as-errors', '-I', str(ROOT),
            '-module-cache-path', str(cls.folder / 'cache'), str(ROOT / 'EngineLanProfileFile.swift'),
            str(ROOT / 'EngineLanProfileCheckpoint.swift'), str(ROOT / 'tests/profile_checkpoint102.swift'),
            str(LIB), '-o', str(cls.binary)], capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise RuntimeError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def scenario(self, mode, expected):
        directory = self.folder / ('zema-engine-lan-' + mode)
        first = subprocess.run([str(self.binary), mode, str(directory)], capture_output=True, text=True, timeout=20)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertIn('PASS' if mode != 'baseline-gap' else 'REPRODUCED', first.stdout)
        second = subprocess.run([str(self.binary), 'verify', str(directory), str(expected)], capture_output=True, text=True, timeout=10)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn('DISK_RELOAD_STAT_', second.stdout)

    def test_previous_uncommitted_stats_loss_is_reproduced(self): self.scenario('baseline-gap', 0)
    def test_timer_saves_dirty_stats_without_cloud_upload(self): self.scenario('timer', 111)
    def test_periodic_timer_stops_offline_and_can_resume(self): self.scenario('stop', 111)
    def test_failed_write_keeps_dirty_and_preserves_prior_snapshot(self): self.scenario('failure', 111)
    def test_revision_change_during_commit_stays_dirty(self): self.scenario('revision-race', 222)
    def test_pre_admission_rename_uses_same_durable_commit_lane(self): self.scenario('rename', 111)
    def test_concurrent_cloud_commits_are_serialized(self): self.scenario('serialization', 111)
    def test_async_lifecycle_save_does_not_block_caller(self): self.scenario('async', 222)
