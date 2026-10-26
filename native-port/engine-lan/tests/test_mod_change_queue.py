"""Run real Foundation file operations in a new temporary directory only."""
from pathlib import Path
import subprocess
import tempfile
import unittest

APP = Path(__file__).resolve().parents[2] / 'app'

class ModChangeQueueTests(unittest.TestCase):
    def test_deferred_changes_preserve_active_files_and_recover_safely(self):
        with tempfile.TemporaryDirectory(prefix='zema-mod-queue-') as directory:
            root = Path(directory)
            command = ['/usr/bin/swiftc', '-warnings-as-errors', '-module-cache-path', str(root / 'modules'),
                       str(APP / 'App/ModFiles.swift'), str(APP / 'App/ModChangeQueue.swift'),
                       str(APP / 'Tests/mod_change_queue.swift'), '-o', str(root / 'test')]
            built = subprocess.run(command, capture_output=True, text=True, timeout=90)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            tested = subprocess.run([str(root / 'test')], capture_output=True, text=True, timeout=30)
            self.assertEqual(tested.returncode, 0, tested.stdout + tested.stderr)
            self.assertIn('MOD_CHANGE_QUEUE_DEFER_CANCEL_CONFLICT_SYMLINK_CORRUPTION_AND_RETRY_PASS', tested.stdout)

if __name__ == '__main__':
    unittest.main()
