import hashlib
from pathlib import Path
from public_test_inputs import game_file
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import browser_features
MIRROR=game_file('b/8b0b5899ed')
class BrowserGpu(unittest.TestCase):
 def test_composed_worker_formats_copy_stencil_and_minimap(self):
  original=(MIRROR/'wgpu_worker.js').read_bytes();patched=browser_features.renderer(original)
  with tempfile.TemporaryDirectory() as tmp:
   worker=Path(tmp)/'gpu.cjs';worker.write_bytes(patched)
   for args in [['node','--check',str(worker)],['node',str(ROOT/'tests/gpu_parity_fixture.cjs'),str(worker)],['node',str(ROOT/'tests/minimap_fixture.cjs'),str(worker),str(MIRROR/'shaders')]]:
    run=subprocess.run(args,capture_output=True,text=True,timeout=30);self.assertEqual(run.returncode,0,run.stderr)
  self.assertEqual(original,(MIRROR/'wgpu_worker.js').read_bytes())
 def test_refuse_unknown_worker_and_only_game_language_changed(self):
  with self.assertRaisesRegex(ValueError,'GPU worker'):browser_features.renderer(b'unknown')
  for mode in ['story','sandbox']:
   data=browser_features.offline_patch('game.js',(MIRROR/'game.js').read_bytes(),mode).decode()
   self.assertIn('7980558:($0,$1)=>{stringToUTF8("en-US",$0,$1)}',data)
   self.assertNotIn('navigator.language',data)
   self.assertNotIn('Object.defineProperty(navigator',data)
if __name__=='__main__':unittest.main()
