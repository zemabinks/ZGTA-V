"""Synthetic-memory C ABI test of the built native virtual-select implementation."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
LIB = Path(os.environ.get('ZEMA_TEST_LAN_LIBRARY', str(ROOT.parent / 'app/Build/EngineLAN/RustHost/debug/libzema_engine_lan.a')))

class NativeVirtualSelectTests(unittest.TestCase):
    def test_real_socket_masks_timeout_queue_and_disconnect(self):
        with tempfile.TemporaryDirectory(prefix='zema-native-select-') as folder:
            binary = Path(folder) / 'select'
            result = subprocess.run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT),str(ROOT/'tests/native_select.c'),str(LIB),'-o',str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('NATIVE_VIRTUAL_SELECT_ACTUAL_READINESS_PASS', result.stdout)

if __name__ == '__main__':
    unittest.main()
