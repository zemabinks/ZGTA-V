"""Reproduce Foundation's /var alias using disposable app-Documents fixtures.

Only the OS Documents anchor is canonicalized. Profile symlinks, unsafe modes,
missing roots and corruption must remain refused without altering user data.
"""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIB=Path(os.environ.get('ZEMA_TEST_LAN_LIBRARY',str(ROOT.parent/'app/Build/EngineLAN/RustHost/debug/libzema_engine_lan.a')))


class ProfileDirectory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='zema-profile-directory-')
        cls.alias = Path(cls.temporary.name)
        cls.directory = cls.alias.resolve()
        cls.binary = cls.directory / 'fixture'
        result = subprocess.run(['/usr/bin/swiftc', '-warnings-as-errors', '-I', str(ROOT),
            '-module-cache-path', str(cls.directory / 'cache'), str(ROOT / 'EngineLanProfileFile.swift'),
            str(ROOT / 'tests/profile_directory.swift'), str(LIB), '-o', str(cls.binary)],
            capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise RuntimeError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def execute(self, folder, mode='seed'):
        return subprocess.run([str(self.binary), str(folder), mode], capture_output=True, text=True, timeout=15)

    def documents(self, name):
        folder = self.alias / name
        folder.mkdir(mode=0o700)
        return folder

    def test_system_alias_resolves_to_same_profile_without_touching_story(self):
        folder = self.documents('documents-roundtrip')
        story = folder / 'Story.save'; story.write_bytes(b'keep-story-unchanged')
        old = self.execute(folder, 'legacy')
        self.assertEqual(old.returncode, 0, old.stdout + old.stderr)
        self.assertIn('LEGACY_SYSTEM_ALIAS_REFUSAL_REPRODUCED', old.stdout)
        created = self.execute(folder)
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        self.assertIn('CANONICAL_APP_DOCUMENTS_PROFILE_SAVE_PASS', created.stdout)
        profile = folder / 'zema-engine-lan-profile-v1'
        current = profile / 'profile.zemapf'; before = current.read_bytes()
        self.assertEqual(profile.stat().st_mode & 0o777, 0o700)
        self.assertEqual(current.stat().st_mode & 0o777, 0o600)
        resumed = self.execute(folder, 'resume')
        self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
        self.assertIn('CANONICAL_APP_DOCUMENTS_PROFILE_RESUME_PASS', resumed.stdout)
        self.assertEqual(current.read_bytes(), before)
        self.assertEqual(story.read_bytes(), b'keep-story-unchanged')

    def test_profile_child_symlink_is_not_canonicalized_or_followed(self):
        folder = self.documents('documents-directory-link')
        outside = self.directory / 'outside-profile'; outside.mkdir(mode=0o700)
        sentinel = outside / 'keep'; sentinel.write_bytes(b'preserve')
        (folder / 'zema-engine-lan-profile-v1').symlink_to(outside)
        result = self.execute(folder)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('symlink', result.stdout)
        self.assertEqual([p.name for p in outside.iterdir()], ['keep'])
        self.assertEqual(sentinel.read_bytes(), b'preserve')

    def test_profile_file_symlink_remains_refused(self):
        folder = self.documents('documents-file-link')
        profile = folder / 'zema-engine-lan-profile-v1'; profile.mkdir(mode=0o700)
        outside = self.directory / 'outside-current'; outside.write_bytes(b'preserve-current')
        (profile / 'profile.zemapf').symlink_to(outside)
        self.assertNotEqual(self.execute(folder).returncode, 0)
        self.assertEqual(outside.read_bytes(), b'preserve-current')
        self.assertTrue((profile / 'profile.zemapf').is_symlink())

    def test_existing_nonprivate_profile_is_not_repaired_or_overwritten(self):
        folder = self.documents('documents-nonprivate')
        profile = folder / 'zema-engine-lan-profile-v1'; profile.mkdir(mode=0o755)
        result = self.execute(folder)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unsafeDirectory', result.stdout)
        self.assertEqual(profile.stat().st_mode & 0o777, 0o755)
        self.assertEqual(list(profile.iterdir()), [])

    def test_missing_and_nonfile_documents_fail_without_creation(self):
        missing = self.alias / 'missing-documents'
        self.assertNotEqual(self.execute(missing).returncode, 0)
        self.assertFalse(missing.exists())
        result = self.execute(self.alias, 'nonfile')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unsafePath', result.stdout)


if __name__ == '__main__':
    unittest.main()
