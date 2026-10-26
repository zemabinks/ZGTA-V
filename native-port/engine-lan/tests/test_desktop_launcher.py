"""Desktop installation/lifetime contracts; Windows COM needs a Windows test."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import desktop_launcher as desktop
import portable_launcher as launcher


class DesktopLauncher(unittest.TestCase):
    def fixture(self, root, build=93):
        package = root / "download with spaces & 'quote'"
        package.mkdir()
        members = {
            'Start ZGTA V.command': b'#!/bin/sh\nexit 0\n',
            'Start ZGTA V.cmd': b'@echo off\r\n',
            'Runtime/engine.wasm': b'checked fixture',
            str(desktop.ASSETS / 'zgta-v.icns'): (ROOT / 'desktop-assets/zgta-v.icns').read_bytes(),
            str(desktop.ASSETS / 'zgta-v.ico'): (ROOT / 'desktop-assets/zgta-v.ico').read_bytes(),
        }
        for rel, raw in members.items():
            p = package / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(raw)
        (package / 'Start ZGTA V.command').chmod(0o755)
        manifest = {'format': 'zgta-portable-v1', 'build': build,
                    'files': {k: hashlib.sha256(v).hexdigest() for k, v in members.items()}}
        (package / 'portable-manifest.json').write_text(json.dumps(manifest))
        game = package / 'Game/personal-save'
        game.parent.mkdir(); game.write_bytes(b'never copy or touch')
        data = root / 'private data'
        data.mkdir(mode=0o700)
        target = root / 'Desktop'
        target.mkdir()
        return package, data, target, manifest, game

    def test_mac_app_reuses_ios_icon_and_survives_removing_download(self):
        with tempfile.TemporaryDirectory() as folder:
            package, data, target, manifest, game = self.fixture(Path(folder))
            entry = desktop.install(package, data, manifest, 'darwin', target)
            info = plistlib.loads((entry / 'Contents/Info.plist').read_bytes())
            self.assertEqual(info['CFBundleIconFile'], 'ZGTA-V.icns')
            self.assertEqual(info['CFBundleIdentifier'], desktop.BUNDLE_ID)
            self.assertTrue(os.access(entry / 'Contents/MacOS/ZGTA-V', os.X_OK))
            copies = list((data / 'desktop-launchers').iterdir())
            self.assertEqual(len(copies), 1)
            installed = copies[0]
            script = (entry / 'Contents/MacOS/ZGTA-V').read_text()
            self.assertIn(shlex.quote(str(installed / 'Start ZGTA V.command')), script)
            subprocess.run(['/bin/sh', '-n', str(entry / 'Contents/MacOS/ZGTA-V')], check=True)
            self.assertFalse((installed / 'Game').exists())
            self.assertEqual(game.read_bytes(), b'never copy or touch')
            before = (entry / 'Contents/MacOS/ZGTA-V').stat().st_mtime_ns
            self.assertEqual(desktop.install(package, data, manifest, 'darwin', target), entry)
            self.assertEqual(before, (entry / 'Contents/MacOS/ZGTA-V').stat().st_mtime_ns)
            # Remove only this temporary fixture download, then check installed copy.
            shutil.rmtree(package)
            launcher.verify_package(installed)
            self.assertTrue((installed / 'Start ZGTA V.command').is_file())
            with patch.object(launcher, 'PACKAGE', installed):
                self.assertEqual(launcher.data_directory(), data)

    def test_update_preserves_prior_launcher_and_desktop_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            package, data, target, manifest, _ = self.fixture(Path(folder))
            entry = desktop.install(package, data, manifest, 'darwin', target)
            old = (entry / 'Contents/MacOS/ZGTA-V').read_bytes()
            manifest['build'] = 94
            (package / 'portable-manifest.json').write_text(json.dumps(manifest))
            desktop.install(package, data, manifest, 'darwin', target)
            self.assertEqual(len(list((data / 'desktop-launchers').iterdir())), 2)
            backup = next((data / 'desktop-backups').glob('*.app'))
            self.assertEqual((backup / 'Contents/MacOS/ZGTA-V').read_bytes(), old)
            self.assertNotEqual((entry / 'Contents/MacOS/ZGTA-V').read_bytes(), old)

    def test_unrelated_desktop_app_and_corrupt_installed_copy_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            package, data, target, manifest, _ = self.fixture(Path(folder))
            entry = target / 'ZGTA V.app'
            entry.mkdir(); (entry / 'personal').write_text('keep')
            with self.assertRaisesRegex(ValueError, 'preserved'):
                desktop.install(package, data, manifest, 'darwin', target)
            self.assertEqual((entry / 'personal').read_text(), 'keep')
            installed = next((data / 'desktop-launchers').iterdir())
            (installed / 'Runtime/engine.wasm').write_bytes(b'changed fixture')
            with self.assertRaisesRegex(ValueError, 'changed'):
                desktop.installed_copy(package, data, manifest)
            self.assertEqual((installed / 'Runtime/engine.wasm').read_bytes(), b'changed fixture')

    def test_symlinked_desktop_members_are_not_followed(self):
        with tempfile.TemporaryDirectory() as folder:
            package, data, target, manifest, _ = self.fixture(Path(folder))
            entry = desktop.install(package, data, manifest, 'darwin', target)
            member = entry / 'Contents/MacOS/ZGTA-V'
            outside = Path(folder) / 'keep'; outside.write_text('keep')
            member.unlink(); member.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, 'symbolic link'):
                desktop.install(package, data, manifest, 'darwin', target)
            self.assertEqual(outside.read_text(), 'keep')

    def test_windows_shortcut_uses_known_desktop_and_literal_environment_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            package, data, target, manifest, _ = self.fixture(Path(folder))
            run = Mock(return_value=Mock(stdout=json.dumps({'path': str(target / 'ZGTA V.lnk')}).encode()))
            with patch.object(desktop.subprocess, 'run', run):
                result = desktop.install(package, data, manifest, 'win32', target)
            self.assertEqual(result, target / 'ZGTA V.lnk')
            args = run.call_args.args[0]; env = run.call_args.kwargs['env']
            self.assertNotIn('-ExecutionPolicy', args)
            self.assertEqual(args[-1], desktop.WINDOWS_SHORTCUT)
            self.assertNotIn(str(data), args[-1])
            self.assertEqual(env['ZGTA_DESKTOP'], str(target))
            self.assertTrue(env['ZGTA_START'].endswith('Start ZGTA V.cmd'))
            self.assertTrue(env['ZGTA_ICON'].endswith('zgta-v.ico'))
            self.assertIn("SpecialFolders.Item('Desktop')", args[-1])
            self.assertIn('already exists and was preserved', args[-1])

    def test_repeat_launch_reopens_browser_without_restarting_or_reading_game(self):
        with tempfile.TemporaryDirectory() as folder:
            package, data, target, manifest, _ = self.fixture(Path(folder))
            with patch.object(launcher, 'PACKAGE', package), patch.object(launcher, 'verify_package', return_value=manifest), patch.object(launcher, 'existing_launcher', return_value=True), patch.object(launcher, 'load_mirror') as load, patch.object(launcher, 'open_browser') as browser, patch.object(desktop, 'install', return_value=target / 'ZGTA V.app') as install, contextlib.redirect_stdout(io.StringIO()):
                launcher.main(['--data', str(data)])
            browser.assert_called_once(); load.assert_not_called()
            install.assert_called_once_with(package, data, manifest)

    def test_desktop_permission_error_keeps_existing_host_usable_and_opt_out_works(self):
        with tempfile.TemporaryDirectory() as folder:
            package, data, target, manifest, _ = self.fixture(Path(folder))
            with patch.object(launcher, 'PACKAGE', package), patch.object(launcher, 'verify_package', return_value=manifest), patch.object(launcher, 'existing_launcher', return_value=True), patch.object(launcher, 'open_browser') as browser, patch.object(desktop, 'install', side_effect=PermissionError('Desktop denied')) as install, contextlib.redirect_stderr(io.StringIO()) as errors, contextlib.redirect_stdout(io.StringIO()):
                launcher.main(['--data', str(data)])
                self.assertIn('Desktop denied', errors.getvalue())
                launcher.main(['--data', str(data), '--no-desktop'])
            self.assertEqual(browser.call_count, 2)
            install.assert_called_once()

    def test_mac_prefers_existing_chrome_without_changing_browser_profile(self):
        with patch.object(launcher.sys, 'platform', 'darwin'), patch.object(Path, 'is_dir', return_value=True), patch.object(launcher.subprocess, 'Popen') as run, patch.object(launcher.webbrowser, 'open') as fallback:
            launcher.open_browser()
        self.assertEqual(run.call_args.args[0], ['/usr/bin/open', '-a', '/Applications/Google Chrome.app', launcher.URL])
        fallback.assert_not_called()

    def test_desktop_icons_have_exact_ios_master_and_valid_ico_directory(self):
        source = (ROOT.parent / 'app/App/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png').read_bytes()
        raw = (ROOT / 'desktop-assets/zgta-v.icns').read_bytes()
        self.assertEqual(raw[:4], b'icns'); self.assertEqual(struct.unpack('>I', raw[4:8])[0], len(raw))
        pos = 8; master = None
        while pos < len(raw):
            tag, size = raw[pos:pos+4], struct.unpack('>I', raw[pos+4:pos+8])[0]
            self.assertGreater(size, 8)
            if tag == b'ic10': master = raw[pos+8:pos+size]
            pos += size
        self.assertEqual(pos, len(raw)); self.assertEqual(master, source)
        ico = (ROOT / 'desktop-assets/zgta-v.ico').read_bytes()
        self.assertEqual(struct.unpack('<HHH', ico[:6]), (0, 1, 6))
        for n in range(6):
            size, start = struct.unpack_from('<II', ico, 6 + n * 16 + 8)
            self.assertEqual(ico[start:start+8], b'\x89PNG\r\n\x1a\n')
            self.assertLessEqual(start+size, len(ico))


if __name__ == '__main__': unittest.main()
