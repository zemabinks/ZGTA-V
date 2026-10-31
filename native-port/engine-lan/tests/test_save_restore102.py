"""Run the actual iOS SaveStore against temporary on-disk profiles."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class NativeRestore102(unittest.TestCase):
    def test_restore_cannot_create_unexportable_profile_or_alias_targets(self):
        with tempfile.TemporaryDirectory(prefix="zgta-restore102-") as directory:
            path = Path(directory)
            command = ["/usr/bin/swiftc", "-warnings-as-errors", "-module-cache-path", str(path/"cache"),
                       str(ROOT.parent/"app/App/SaveStore.swift"), str(ROOT/"tests/save_restore102.swift"),
                       "-o", str(path/"fixture")]
            result = subprocess.run(command, capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(path/"fixture"), str(path/"data")], capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("NATIVE_RESTORE_UNION_LIMITS_ALIAS_REJECTION_AND_UNCHANGED_FAILURE_PASS", result.stdout)

if __name__ == "__main__":
    unittest.main()
