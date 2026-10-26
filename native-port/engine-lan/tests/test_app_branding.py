"""Real source icon validation and final bundle staging; no game execution."""
from pathlib import Path
import shutil,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app_branding import ICON_ROOT,verify_source,stage_icons,verify_icons,icon_properties
class AppBranding(unittest.TestCase):
 def test_original_and_all_phone_ipad_sizes_are_opaque(self):
  data=verify_source();self.assertEqual(len(data['files']),14)
  for value in icon_properties().values():self.assertNotIn('CFBundleIconName',value['CFBundlePrimaryIcon'])
 def test_staged_bundle_uses_exact_provided_family_and_rejects_corruption(self):
  with tempfile.TemporaryDirectory() as d:
   app=Path(d);data=stage_icons(app);self.assertEqual(verify_icons(app),data)
   (app/'ZGTAIcon60x60@3x.png').write_bytes(b'bad')
   with self.assertRaisesRegex(ValueError,'asset differs'):verify_icons(app)
 def test_incomplete_source_family_fails_closed(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'icons';shutil.copytree(ICON_ROOT,root);(root/'ZGTAIcon83.5x83.5@2x.png').unlink()
   with self.assertRaises(FileNotFoundError):verify_source(root)
