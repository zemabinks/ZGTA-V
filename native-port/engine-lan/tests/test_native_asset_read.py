from pathlib import Path
import subprocess
import tempfile
import unittest

APP = Path(__file__).resolve().parents[2] / 'app'

class NativeAssetReadTests(unittest.TestCase):
    def test_interrupted_partial_reads_eof_errors_and_offset_bounds(self):
        with tempfile.TemporaryDirectory(prefix='zema-asset-read-') as directory:
            binary = Path(directory) / 'test'
            built = subprocess.run(['/usr/bin/clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-I', str(APP / 'Source'), str(APP / 'Tests/asset_read.c'), '-o', str(binary)],
                           capture_output=True, text=True, timeout=30)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            subprocess.run([str(binary)], capture_output=True, text=True, check=True, timeout=10)

if __name__ == '__main__':
    unittest.main()
