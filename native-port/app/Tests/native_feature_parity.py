"""Check display-only native changes and strict TrollStore package boundaries."""
import json
from pathlib import Path
import plistlib
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
REPO = APP.parents[1]
sys.path.insert(0, str(APP / 'Scripts'))
import package_trollstore as package

DATA = json.loads((APP / 'Tests/native_hud_english.json').read_text())


class NativeFeatureParityTests(unittest.TestCase):
    def test_visible_brand_is_zema_and_original_credits_remain(self):
        catalog = json.loads((APP / 'Resources/Localizations.json').read_text())
        for key, entry in catalog.items():
            for value in entry.values():
                self.assertNotIn('iosvn', value.lower(), key)
        for name in ['HomeView.swift', 'SettingsViewController.swift']:
            text = (APP / 'App' / name).read_text()
            self.assertNotIn('iosvn', text.lower())
            self.assertIn('zema', text)
        for value in DATA['translations'].values():
            self.assertNotIn('iosvn', value.lower())
        # English-only is an explicit product change; retain only protocol role aliases.
        self.assertEqual(set(catalog), {'Dân thường', 'Cảnh sát', 'Bác sĩ', 'Băng đảng', 'Tài xế'})
        self.assertTrue(all(set(entry) == {'en'} for entry in catalog.values()))
        for path in ['LICENSE', 'native-port/LICENSE']:
            self.assertEqual((REPO / path).read_bytes(), subprocess.check_output(
                ['git', 'show', DATA['upstream'] + ':' + path], cwd=REPO))
        self.assertIn('https://github.com/iOSVNNews/mugoat', (APP / 'Scripts/package_trollstore.py').read_text())

    def test_native_feature_logic_is_unchanged_outside_display_and_additive_world_commands(self):
        original = subprocess.check_output(['git', 'show', DATA['upstream'] + ':src/mp.rs'], cwd=REPO, text=True)
        expected = original
        for old, new in DATA['translations'].items():
            before, after = (json.dumps(s, ensure_ascii=False) for s in (old, new))
            self.assertIn(before, original)
            expected = expected.replace(before, after)
        sys.path.insert(0, str(REPO / 'native-port/engine-lan'))
        import world_commands
        added = '    // Additive native world tools; existing multiplayer logic is unchanged.\n'
        added += ''.join('    ("' + alias + '", "' + name + '"),\n' for alias, name, *_ in world_commands.COMMANDS)
        current = (REPO / 'src/mp.rs').read_text()
        self.assertEqual(current.count(added), 1)
        self.assertEqual(current.replace(added, ''), expected)

    def test_hud_formats_colors_economy_and_timings_are_preserved(self):
        for old, new in DATA['translations'].items():
            with self.subTest(original=old):
                self.assertEqual(re.findall(r'\{[^{}]*\}', old), re.findall(r'\{[^{}]*\}', new))
                self.assertEqual(re.findall(r'~[A-Za-z0-9_]+~', old), re.findall(r'~[A-Za-z0-9_]+~', new))
                self.assertEqual(re.findall(r'\d+', old), re.findall(r'\d+', new))

    def test_wire_role_prefixes_and_protocol_are_preserved(self):
        text = (REPO / 'src/mp.rs').read_text()
        for wire in ['[Cảnh sát]', '[Bác sĩ]', '[Băng đảng]', '[Tài xế]']:
            self.assertIn('name.starts_with(' + json.dumps(wire, ensure_ascii=False) + ')', text)
            self.assertNotIn(wire, DATA['translations'])
        for path in ['src/proto.rs', 'src/server.rs', 'native-port/online-bridge/src/lib.rs']:
            original = subprocess.check_output(['git', 'show', DATA['upstream'] + ':' + path], cwd=REPO)
            self.assertEqual((REPO / path).read_bytes(), original)

    def test_only_original_memory_requests_and_generic_free_profile_unchanged(self):
        selected = package.profile(APP)
        original = subprocess.check_output(['git', 'show', DATA['upstream'] + ':native-port/app/App/Full.entitlements'], cwd=REPO)
        self.assertEqual(selected.read_bytes(), original)
        self.assertEqual(plistlib.loads((APP / 'App/Free.entitlements').read_bytes()), {})

    def test_extra_privileges_and_changed_generic_profile_refused(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch).resolve(); (root / 'App').mkdir()
            for name in ['Full', 'TrollStore']:
                (root / ('App/' + name + '.entitlements')).write_bytes(plistlib.dumps(package.MEMORY))
            (root / 'App/Free.entitlements').write_bytes(plistlib.dumps({}))
            package.profile(root)
            changed = {**package.MEMORY, 'platform-application': True}
            (root / 'App/TrollStore.entitlements').write_bytes(plistlib.dumps(changed))
            with self.assertRaises(package.CacheError):
                package.profile(root)
            (root / 'App/TrollStore.entitlements').write_bytes(plistlib.dumps(package.MEMORY))
            (root / 'App/Free.entitlements').write_bytes(plistlib.dumps(package.MEMORY))
            with self.assertRaises(package.CacheError):
                package.profile(root)

    def test_existing_output_and_original_folder_inputs_refused(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch).resolve(); build = root / 'Build'; build.mkdir()
            app = build / 'Fixture.app'; app.mkdir(); receipt = build / 'receipt.json'; receipt.write_text('{}')
            out = build / 'Previous'; out.mkdir(); (out / 'keep').write_text('preserve')
            with patch.object(package, 'ROOT', root):
                with self.assertRaises(package.CacheError):
                    package.validate(app, out, receipt, 'fixture')
                with self.assertRaises(package.CacheError):
                    package.validate(root / 'Original.app', build / 'New', receipt, 'fixture')
            self.assertEqual((out / 'keep').read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()
