"""Actual profile-owner lifecycle checkpoint acknowledgements; no browser storage."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProfileLifecycle102(unittest.TestCase):
    def test_worker_serializes_lifecycle_flush_and_acknowledges_actual_commit(self):
        result = subprocess.run(['node', str(ROOT / 'tests/profile_lifecycle102.cjs')], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('ACTUAL_COMMIT_ACK_SERIALIZATION_DIRTY_FAILURE_RETRY_PASS', result.stdout)
