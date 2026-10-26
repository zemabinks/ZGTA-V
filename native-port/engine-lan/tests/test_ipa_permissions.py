"""Regress the unreadable app root missed by TrollStore's child-only chmod."""
from pathlib import Path
import plistlib
import stat
import sys
import tempfile
import unittest
import zipfile

SCRIPTS = Path(__file__).resolve().parents[2] / 'app/Scripts'
sys.path.insert(0, str(SCRIPTS))
from ipa_permissions import normalize_bundle, rewrite_archive


class IPAPermissions(unittest.TestCase):
    def fixture(self, path, extra=None):
        contents = {
            'Payload/': (0o40700, b''),
            'Payload/Test.app/': (0o40700, b''),
            'Payload/Test.app/Info.plist': (0o100600, plistlib.dumps({
                'CFBundleExecutable': 'Game', 'CFBundleIdentifier': 'test.app', 'CFBundleVersion': '29'})),
            'Payload/Test.app/Game': (0o100700, b'\xcf\xfa\xed\xfeSIGNED_BINARY'),
            'Payload/Test.app/_CodeSignature/': (0o40700, b''),
            'Payload/Test.app/_CodeSignature/CodeResources': (0o100600, b'signed resource bytes'),
            'Payload/Test.app/Assets.car': (0o100600, b'pinned assets'),
        }
        if extra:
            contents.update(extra)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, (mode, data) in contents.items():
                info = zipfile.ZipInfo(name); info.create_system = 3; info.external_attr = mode << 16
                z.writestr(info, data)
        return contents

    def test_roundtrip_repairs_root_and_preserves_every_signed_member_byte(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'old.ipa'; target = root / 'new.ipa'
            contents = self.fixture(source); original = source.read_bytes()
            report = rewrite_archive(source, target)
            self.assertEqual(report['members_byte_identical'], len(contents))
            with zipfile.ZipFile(target) as z:
                for name, (_, data) in contents.items():
                    self.assertEqual(z.read(name), data)
                    expected = 0o755 if name.endswith('/') or name.endswith('/Game') else 0o644
                    self.assertEqual(stat.S_IMODE(z.getinfo(name).external_attr >> 16), expected, name)
            self.assertEqual(source.read_bytes(), original)
            with self.assertRaises(ValueError):
                rewrite_archive(source, target)

    def test_new_bundle_copy_includes_root_and_keeps_private_parent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); root.chmod(0o700)
            app = root / 'Game.app'; app.mkdir(mode=0o700)
            data = app / 'data'; data.write_bytes(b'resource'); data.chmod(0o600)
            exe = app / 'Game'; exe.write_bytes(b'\xcf\xfa\xed\xfeCODE'); exe.chmod(0o600)
            normalize_bundle(app)
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(app.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE(exe.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE(data.stat().st_mode), 0o644)
            self.assertEqual(exe.read_bytes(), b'\xcf\xfa\xed\xfeCODE')

    def test_link_and_traversal_archives_rejected_before_output_creation(self):
        for name, mode in [('Payload/Test.app/link', 0o120777), ('Payload/../escape', 0o100600)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); source = root / 'bad.ipa'; target = root / 'new.ipa'
                self.fixture(source, {name: (mode, b'target')})
                with self.assertRaises(ValueError):
                    rewrite_archive(source, target)
                self.assertFalse(target.exists())

    def test_bundle_symlink_rejected_without_changing_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); app = root / 'Game.app'; app.mkdir(mode=0o700)
            private = root / 'private'; private.write_text('preserve'); private.chmod(0o600)
            (app / 'link').symlink_to(private)
            with self.assertRaises(ValueError):
                normalize_bundle(app)
            self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(app.stat().st_mode), 0o700)


if __name__ == '__main__':
    unittest.main()
