"""Regression for stale Sileo selections when a newer installer is indexed."""
import importlib.util,tempfile,unittest,shutil,bz2,gzip,lzma
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('indexes',ROOT/'tools/update_installer_indexes.py')
indexes=importlib.util.module_from_spec(spec);spec.loader.exec_module(indexes)
class HistoricalVersions(unittest.TestCase):
 def test_published_versions_survive_idempotent_current_update(self):
  previous=(ROOT/'Packages').read_text().strip().split('\n\n')
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   for name in ['Packages','package-sources','pool']:
    src=ROOT/name;dst=root/name
    if src.is_dir():shutil.copytree(src,dst)
    else:shutil.copy2(src,dst)
   with patch.object(indexes,'ROOT',root):
    indexes.update();first=(root/'Packages').read_bytes();indexes.update()
   self.assertEqual(first,(root/'Packages').read_bytes())
   now=(root/'Packages').read_text().strip().split('\n\n')
   for stanza in previous:self.assertIn(stanza,now)
   for suffix,unpack in [('gz',gzip.decompress),('bz2',bz2.decompress),('xz',lzma.decompress)]:
    self.assertEqual(unpack((root/('Packages.'+suffix)).read_bytes()),first)
if __name__=='__main__':unittest.main()
