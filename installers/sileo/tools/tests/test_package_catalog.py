import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('builder',ROOT/'tools/build_trollstore_package.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
class CatalogPins(unittest.TestCase):
 def test_current_catalog_is_rendered_exactly(self):
  with tempfile.TemporaryDirectory() as t:
   dest=Path(t)/'stage';catalog=builder.stage(dest)
   script=(dest/'DEBIAN/postinst').read_text()
   for key in ['download_url','sha256']:self.assertIn(catalog[key],script)
   self.assertIn(str(catalog['bytes']),script)
 def test_invalid_or_unowned_download_cannot_stage(self):
  catalog=json.loads((ROOT/'downloads/zgta-v.json').read_text())
  for changes in [{'build':True},{'bytes':0},{'bytes':2**31},{'file':'../../bad.ipa'},{'download_url':'https://example.com/app.ipa'},{'release_url':'https://github.com/other/repo/releases/tag/test'},{'sha256':'bad'}]:
   with self.subTest(changes=changes),tempfile.TemporaryDirectory() as t:
    root=Path(t);(root/'downloads').mkdir();(root/'downloads/zgta-v.json').write_text(json.dumps({**catalog,**changes}))
    with patch.object(builder,'ROOT',root),self.assertRaises(AssertionError):builder.stage(root/'stage')
if __name__=='__main__':unittest.main()
