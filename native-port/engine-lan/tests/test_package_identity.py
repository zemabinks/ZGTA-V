from pathlib import Path
import sys,unittest,copy,tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from package_experimental import package_identity,verify_packaged_icons
from prepare_experimental import add_ui,configure_identity
from app_branding import icon_properties
class PackageIdentity(unittest.TestCase):
 def test_declared_identity_keeps_platform_and_bundle_identifier(self):
  original={'CFBundleVersion':'17','CFBundleDisplayName':'GTA V Port','CFBundleIdentifier':'com.zemabinks.gtamp.enginelanlab','DTPlatformName':'iphoneos'}
  spec={'targets':{'PlayGTA5Native':{'info':{'properties':{'CFBundleVersion':'70','CFBundleDisplayName':'ZGTA V'}}}}}
  spec['targets']['PlayGTA5Native']['sources']=[]
  add_ui(spec)
  result=package_identity(original,spec)
  self.assertEqual(result['CFBundleVersion'],'70');self.assertEqual(result['CFBundleDisplayName'],'ZGTA V');self.assertEqual(result['DTPlatformName'],'iphoneos');self.assertEqual(result['CFBundleIdentifier'],original['CFBundleIdentifier']);self.assertEqual(original['CFBundleVersion'],'17')
  spec['targets']['PlayGTA5Native']['info']['properties']['CFBundleVersion']=''
  with self.assertRaises(ValueError):package_identity(original,spec)

 def test_missing_icon_metadata_is_restored_from_declared_project(self):
  original={'CFBundleVersion':'70','CFBundleDisplayName':'ZGTA V'}
  spec={'targets':{'PlayGTA5Native':{'sources':[],'info':{'properties':{}}}}}
  add_ui(spec);configure_identity(spec)
  result=package_identity(original,spec)
  self.assertEqual(result['CFBundleVersion'],spec['targets']['PlayGTA5Native']['info']['properties']['CFBundleVersion'])
  self.assertEqual(result['CFBundleIcons'],icon_properties()['CFBundleIcons'])
  self.assertEqual(result['CFBundleIcons~ipad'],icon_properties()['CFBundleIcons~ipad'])
  self.assertNotIn('CFBundleIcons',original)
  for key in ['CFBundleIcons','CFBundleIcons~ipad']:
   bad=copy.deepcopy(spec);del bad['targets']['PlayGTA5Native']['info']['properties'][key]
   with self.assertRaisesRegex(ValueError,'icon metadata'):package_identity(original,bad)
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'asset differs'):verify_packaged_icons(Path(d),result)
