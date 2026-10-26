"""Lock-free graphics progress snapshots; no GPU, game or device execution."""
from pathlib import Path
import subprocess
import tempfile
import unittest

APP = Path(__file__).resolve().parents[2] / 'app'


class GraphicsProgress(unittest.TestCase):
    def test_current_operation_ring_and_concurrent_gpu_completion_snapshot(self):
        with tempfile.TemporaryDirectory(prefix='zema-graphics-progress-') as temporary:
            binary = Path(temporary) / 'fixture'
            subprocess.run(['/usr/bin/clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-pthread', str(APP / 'Tests/graphics_progress.cpp'), '-o', str(binary)],
                           check=True, capture_output=True, text=True, timeout=40)
            subprocess.run([str(binary)], check=True, capture_output=True, text=True, timeout=10)


if __name__ == '__main__':
    unittest.main()
