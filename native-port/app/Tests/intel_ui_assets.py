"""Compiled UI reuse: changed sources/input and corrupt prior output must stop."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / 'Scripts'))
import prepare_ui_assets as ui


class DeviceUIAssetsTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        catalog = self.root / 'App/Assets.xcassets'
        catalog.mkdir(parents=True)
        (catalog / 'Contents.json').write_text('{}')
        rows = [{'path': 'Contents.json', 'sha256': hashlib.sha256(b'{}').hexdigest()}]
        digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.stack.enter_context(patch.object(ui, 'ASSET_TREE_SHA', digest))
        self.content = b'fixture compiled UI'
        self.stack.enter_context(patch.object(ui, 'FILES', {'Assets.car': (len(self.content), hashlib.sha256(self.content).hexdigest())}))
        self.ipa = self.root / 'reference.ipa'
        self.write_ipa()

    def write_ipa(self, platform='iphoneos', content=None):
        with zipfile.ZipFile(self.ipa, 'w') as archive:
            archive.writestr(ui.PREFIX + 'Assets.car', self.content if content is None else content)
            archive.writestr(ui.PREFIX + 'iosvn-build-revision.txt', ui.REVISION)
            archive.writestr(ui.PREFIX + 'Info.plist', plistlib.dumps({'DTPlatformName': platform, 'CFBundleIdentifier': 'vn.iosvn.mugoat'}))
        self.stack.enter_context(patch.object(ui, 'IPA_SHA', hashlib.sha256(self.ipa.read_bytes()).hexdigest()))

    def test_valid_independent_staging_and_idempotency(self):
        original = self.ipa.read_bytes()
        self.assertEqual(ui.stage_assets(self.ipa, self.root), 'STAGED')
        result = self.root / 'GeneratedUIAssets/Assets.car'
        inode = result.stat().st_ino
        self.assertEqual(result.read_bytes(), self.content)
        self.assertEqual(ui.stage_assets(self.ipa, self.root), 'REUSED')
        self.assertEqual(result.stat().st_ino, inode)
        self.assertEqual(self.ipa.read_bytes(), original)

    def test_changed_ipa_refused_before_writes(self):
        self.ipa.write_bytes(b'changed')
        with self.assertRaises(ui.CacheError):
            ui.stage_assets(self.ipa, self.root)
        self.assertFalse((self.root / 'GeneratedUIAssets').exists())

    def test_changed_source_refuses_stale_cache(self):
        (self.root / 'App/Assets.xcassets/Contents.json').write_text('changed')
        with self.assertRaises(ui.CacheError):
            ui.stage_assets(self.ipa, self.root)
        self.assertFalse((self.root / 'GeneratedUIAssets').exists())

    def test_wrong_platform_and_corrupt_content_refused(self):
        for platform, content in [('iphonesimulator', None), ('iphoneos', b'x' * len(self.content))]:
            self.write_ipa(platform, content)
            with self.assertRaises(ui.CacheError):
                ui.stage_assets(self.ipa, self.root)
            self.assertFalse((self.root / 'GeneratedUIAssets').exists())

    def test_prior_corruption_is_preserved_not_repaired(self):
        ui.stage_assets(self.ipa, self.root)
        result = self.root / 'GeneratedUIAssets/Assets.car'
        result.write_bytes(b'keep me')
        with self.assertRaises(ui.CacheError):
            ui.stage_assets(self.ipa, self.root)
        self.assertEqual(result.read_bytes(), b'keep me')

    def test_catalog_symlink_refused(self):
        (self.root / 'App/Assets.xcassets/link').symlink_to(self.ipa)
        with self.assertRaises(ui.CacheError):
            ui.stage_assets(self.ipa, self.root)

    def test_generated_spec_keeps_source_and_all_other_resources(self):
        source = (APP / 'project.yml').read_text()
        result = ui.project_spec(source)
        self.assertIn('- Assets.xcassets', result)
        self.assertIn('path: GeneratedUIAssets', result)
        self.assertIn('path: GeneratedResources', result)
        self.assertIn('path: Resources', result)
        self.assertIn('AppIcon76x76', result)
        self.assertNotIn('- Assets.xcassets', source)
        with self.assertRaises(ui.CacheError):
            ui.project_spec('changed spec')


if __name__ == '__main__':
    unittest.main()
