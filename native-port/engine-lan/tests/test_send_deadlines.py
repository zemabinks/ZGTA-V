"""Exercise the actual Swift transport with only socket/clock boundaries doubled."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeSendDeadlines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='zema-send-deadlines-')
        directory = Path(cls.temp.name)
        # Foundation's URLSession names are shadowed by the boundary doubles.
        source = (ROOT / 'tests/session_send_deadlines.swift').read_text()
        source += '\n' + (ROOT / 'EngineLanSession.swift').read_text()
        (directory / 'fixture.swift').write_text(source)
        cls.binary = directory / 'fixture'
        result = subprocess.run(['/usr/bin/swiftc', '-parse-as-library', '-warnings-as-errors',
            '-module-cache-path', str(directory / 'cache'), str(directory / 'fixture.swift'),
            '-o', str(cls.binary)], capture_output=True, text=True, timeout=90)
        if result.returncode:
            cls.temp.cleanup()
            raise AssertionError(result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def check(self, scenario, marker):
        result = subprocess.run([str(self.binary), scenario], capture_output=True, text=True, timeout=12)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(marker, result.stdout)

    def test_oldest_send_cannot_be_hidden_by_newer_completions(self):
        self.check('send-age', 'NATIVE_OLDEST_SEND_DEADLINE_CAPACITY_OUT_OF_ORDER_AND_STALE_GENERATION_PASS')

    def test_first_connection_failure_does_not_claim_a_resume(self):
        self.check('initial-error', 'NATIVE_INITIAL_FAILURE_EXPLAINS_RELAY_WITHOUT_RESUME_PASS')

    def test_failed_resume_keeps_identity_and_recovery_advice(self):
        self.check('resume-error', 'NATIVE_FAILED_RESUME_RETAINS_TOKEN_AND_EXPLAINS_RECOVERY_PASS')
