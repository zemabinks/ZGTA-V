"""Keep the existing direct-restart contract fixture in normal test discovery."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DirectSessionRestart102(unittest.TestCase):
    def test_browser_task_lifetime_tls_guard_and_failure_cases(self):
        result = subprocess.run(['node', str(ROOT / 'tests/session_restart_fixture.cjs')],
            capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('fresh-session completion', result.stdout)

    def test_browser_and_native_builders_share_exact_contract(self):
        import session_restart
        result = subprocess.run(['node', '-e', 'console.log(JSON.stringify(require(process.argv[1]).pin))',
            str(ROOT / 'session-restart.js')], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), session_restart.CONTRACT)
