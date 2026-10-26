"""Offline exact-source worker composition and real-shader reflection checks."""
import hashlib
from pathlib import Path
from public_test_inputs import game_file
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import minimap_gpu

MIRROR = game_file('b/8b0b5899ed')
WORKER_PIN = '9f94832b93b5c4ada84a0cdffb65157a05e71890c1904d298c74b12c00da32e2'


class Minimap(unittest.TestCase):
    def test_exact_worker_and_real_shader_reflection(self):
        before = (MIRROR / 'wgpu_worker.js').read_bytes()
        self.assertEqual(hashlib.sha256(before).hexdigest(), WORKER_PIN)
        after = minimap_gpu.apply(before.decode())
        with tempfile.TemporaryDirectory(prefix='zema-minimap-test-') as tmp:
            target = Path(tmp) / 'worker.cjs'
            target.write_text(after)
            result = subprocess.run(['node', '--check', str(target)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run(['node', str(ROOT / 'tests/minimap_fixture.cjs'), str(target), str(MIRROR / 'shaders')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"minimapReflectionAndSelection":"PASS"', result.stdout)
            self.assertIn('"gameplayVerified":false', result.stdout)
        self.assertEqual((MIRROR / 'wgpu_worker.js').read_bytes(), before)

    def test_repeated_or_shifted_boundaries_rejected(self):
        source = (MIRROR / 'wgpu_worker.js').read_bytes().decode()
        patched = minimap_gpu.apply(source)
        with self.assertRaisesRegex(ValueError, 'already installed'):
            minimap_gpu.apply(patched)
        with self.assertRaisesRegex(ValueError, 'boundary changed'):
            minimap_gpu.apply(source.replace('function shaderProgram(sh) {', 'function changed(sh) {'))


if __name__ == '__main__':
    unittest.main()
