"""Intel cache selection, safe publication and real preparation-entry regressions.

All writes are disposable fixtures. No Xcode, compiler, download or game runs.
"""
import contextlib
import hashlib
import io
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / 'Scripts'))
import prepare_shaders as shaders


class IntelShaderCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='mugoat-intel-cache-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / 'source'
        self.source.mkdir()
        self.data = {'shaders-iphoneos.metallib': b'fixture-metal',
                     'shader-reflection.jsonl': b'fixture-reflection'}
        for name, data in self.data.items():
            (self.source / name).write_bytes(data)
        self.pin = patch.object(shaders, 'PINNED',
                                {name: hashlib.sha256(data).hexdigest() for name, data in self.data.items()})
        self.pin.start()
        self.addCleanup(self.pin.stop)
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.destination = self.root / 'GeneratedResources'

    def snapshot(self, path):
        return {p.relative_to(path).as_posix(): p.read_bytes()
                for p in path.rglob('*') if p.is_file()}

    def test_intel_default_is_existing_local_cache_and_explicit_override_wins(self):
        with patch.object(shaders, 'intel_mac', return_value=True), patch.object(Path, 'home', return_value=self.root):
            self.assertEqual(shaders.cache_path(), self.root / 'Documents/GTA-MP-IntelBuild/upstream/app/GeneratedResources')
            with patch.dict(os.environ, {'GTA_BASELINE_SHADERS': str(self.source)}):
                self.assertEqual(shaders.cache_path(), self.source)
                self.assertEqual(shaders.cache_path(self.root / 'explicit'), self.root / 'explicit')

    def test_arm_default_retains_compile_route_and_empty_override_is_refused(self):
        with patch.object(shaders, 'intel_mac', return_value=False):
            self.assertIsNone(shaders.cache_path())
            with patch.dict(os.environ, {'GTA_BASELINE_SHADERS': ''}):
                with self.assertRaises(shaders.CacheError):
                    shaders.cache_path()

    def test_pinned_pair_is_published_together_and_original_cache_unchanged(self):
        before = self.snapshot(self.source)
        self.assertEqual(shaders.install_pair(self.source, self.destination), 'COPIED')
        self.assertEqual(self.snapshot(self.destination), before)
        self.assertEqual(self.snapshot(self.source), before)
        self.assertEqual(shaders.install_pair(self.source, self.destination), 'REUSED')
        self.assertEqual(list(self.root.glob('.intel-shaders-*')), [])

    def test_existing_empty_directory_is_supported(self):
        self.destination.mkdir()
        self.assertEqual(shaders.install_pair(self.source, self.destination), 'COPIED')
        self.assertEqual(self.snapshot(self.destination), self.data)

    def test_missing_or_corrupt_source_never_creates_destination(self):
        for missing in (False, True):
            p = self.source / 'shader-reflection.jsonl'
            p.write_bytes(b'bad')
            if missing:
                p.unlink()
            with self.assertRaises((shaders.CacheError, OSError)):
                shaders.install_pair(self.source, self.destination)
            self.assertFalse(self.destination.exists())
            self.assertEqual(list(self.root.glob('.intel-shaders-*')), [])

    def test_existing_partial_or_different_resources_are_never_overwritten(self):
        self.destination.mkdir()
        (self.destination / 'shaders-iphoneos.metallib').write_bytes(b'prior-output')
        before = self.snapshot(self.destination)
        with self.assertRaises((shaders.CacheError, OSError)):
            shaders.install_pair(self.source, self.destination)
        self.assertEqual(self.snapshot(self.destination), before)

    def test_source_and_destination_symlinks_are_rejected(self):
        alias = self.root / 'source-alias'
        alias.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(shaders.CacheError):
            shaders.install_pair(alias, self.destination)
        self.destination.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(shaders.CacheError):
            shaders.install_pair(self.source, self.destination)
        (self.source / 'shader-reflection.jsonl').unlink()
        (self.root / 'reflection').write_bytes(self.data['shader-reflection.jsonl'])
        (self.source / 'shader-reflection.jsonl').symlink_to(self.root / 'reflection')
        with self.assertRaises(shaders.CacheError):
            shaders.verify_pair(self.source)

    def test_nonregular_source_and_destination_are_rejected(self):
        p = self.source / 'shader-reflection.jsonl'
        p.unlink()
        p.mkdir()
        with self.assertRaises(shaders.CacheError):
            shaders.verify_pair(self.source)
        p.rmdir()
        p.write_bytes(self.data[p.name])
        self.destination.write_bytes(b'prior-file')
        with self.assertRaises(shaders.CacheError):
            shaders.install_pair(self.source, self.destination)
        self.assertEqual(self.destination.read_bytes(), b'prior-file')

    def test_failed_copy_leaves_no_partial_pair_or_source_change(self):
        before = self.snapshot(self.source)
        original = shaders.shutil.copyfile
        calls = []
        def fail_second(source, destination):
            calls.append(str(source))
            if len(calls) == 2:
                raise OSError('fixture copy failure')
            return original(source, destination)
        with patch.object(shaders.shutil, 'copyfile', side_effect=fail_second):
            with self.assertRaises(OSError):
                shaders.install_pair(self.source, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.snapshot(self.source), before)
        self.assertEqual(list(self.root.glob('.intel-shaders-*')), [])

    def test_corrupt_staged_copy_is_not_published(self):
        def truncate(source, destination):
            Path(destination).write_bytes(b'truncated')
        with patch.object(shaders.shutil, 'copyfile', side_effect=truncate):
            with self.assertRaises(shaders.CacheError):
                shaders.install_pair(self.source, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.root.glob('.intel-shaders-*')), [])

    def test_concurrent_nonempty_destination_is_preserved(self):
        rename = shaders.os.replace
        def competing_writer(source, destination):
            Path(destination).mkdir()
            (Path(destination) / 'prior').write_bytes(b'other-build')
            return rename(source, destination)
        with patch.object(shaders.os, 'replace', side_effect=competing_writer):
            with self.assertRaises(OSError):
                shaders.install_pair(self.source, self.destination)
        self.assertEqual(self.snapshot(self.destination), {'prior': b'other-build'})

    def cli(self, arguments):
        with patch.object(shaders, 'ROOT', self.root), \
                patch.object(shaders, 'intel_mac', return_value=True), \
                patch.object(shaders.subprocess, 'run') as child, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = shaders.main(['--shader-cache', str(self.source), *arguments])
            child.assert_not_called()
            return code

    def test_check_only_is_readonly_and_never_invokes_compiler(self):
        before = self.snapshot(self.root)
        self.assertEqual(self.cli(['--check-only']), 0)
        self.assertEqual(self.snapshot(self.root), before)
        self.assertFalse(self.destination.exists())

    def test_intel_cli_only_installs_pair_without_compiler_or_download(self):
        self.assertEqual(self.cli([]), 0)
        self.assertEqual(self.snapshot(self.destination), self.data)

    def test_cache_failure_and_simulator_request_never_fall_back_to_compiler(self):
        self.assertEqual(self.cli(['--sdk', 'iphonesimulator']), 1)
        (self.source / 'shaders-iphoneos.metallib').write_bytes(b'bad')
        self.assertEqual(self.cli([]), 1)
        self.assertFalse(self.destination.exists())

    def prepare_fixture(self, tools):
        app = self.root / 'app'
        (app / 'Scripts').mkdir(parents=True)
        script = app / 'Scripts/prepare.py'
        script.write_bytes((APP / 'Scripts/prepare.py').read_bytes())
        mirror = self.root / 'mirror'
        engine = mirror / 'b/8b0b5899ed/game.wasm'
        engine.parent.mkdir(parents=True)
        engine.write_bytes(b'fixture-engine')
        (mirror / 'data').mkdir()
        (mirror / 'data/manifest.json').write_text('{}')
        if tools:
            for name in ['Tools/wabt-1.0.42/lib/libwabt.a', 'Tools/c-writer-original.cc',
                         'Tools/WABT-x86_64-build/include/wabt/config.h',
                         'Tools/wasm2c-main.cc', 'Tools/bcdec/bcdec.h',
                         'Tools/wabt-1.0.42/share/wabt/wasm2c/wasm-rt-impl.c']:
                p = app / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('fixture pg_record_trap')
            for name in ['Tools/wabt-1.0.42/include', 'Tools/simde/simde']:
                (app / name).mkdir(parents=True)
        return app, script, mirror

    def run_prepare(self, script, mirror):
        sha256 = hashlib.sha256
        def engine_digest(data=b''):
            if data == b'fixture-engine':
                class Expected:
                    def hexdigest(self):
                        return '11ca8d2c04c5e843d18ff4aea4899d72c86973c6b031df334e67c446b2ae83e0'
                return Expected()
            return sha256(data)
        with patch.object(sys, 'argv', [str(script), '--mirror', str(mirror), '--shader-cache', str(self.source)]), \
                patch.object(shaders, 'intel_mac', return_value=True), \
                patch('platform.system', return_value='Darwin'), \
                patch('hashlib.sha256', side_effect=engine_digest), \
                patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as child:
            runpy.run_path(str(script), run_name='__main__')
            return [list(call.args[0]) for call in child.call_args_list]

    def test_real_prepare_entry_refuses_missing_intel_inputs_before_any_build_write(self):
        app, script, mirror = self.prepare_fixture(False)
        before = self.snapshot(app)
        with self.assertRaisesRegex(SystemExit, 'no ARM download'):
            self.run_prepare(script, mirror)
        self.assertEqual(self.snapshot(app), before)
        self.assertFalse((app / 'Generated').exists())

    def test_real_prepare_entry_selects_cache_without_fetch_unpack_or_shader_compile(self):
        app, script, mirror = self.prepare_fixture(True)
        with patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')):
            commands = self.run_prepare(script, mirror)
        flat = '\n'.join(' '.join(command) for command in commands)
        self.assertNotIn('git clone', flat)
        self.assertNotIn('fetch_shader_tool.py', flat)
        self.assertNotIn('unpack_shaders.py', flat)
        self.assertNotIn('build_metal_shaders.py', flat)
        self.assertIn('Scripts/prepare_online_c.py', flat)
        self.assertIn('Generated/online-game.wasm', flat)
        selected = [c for c in commands if 'Scripts/prepare_shaders.py' in c]
        self.assertEqual(len(selected), 1)
        self.assertIn(str(self.source), selected[0])
        self.assertIn('--sdk', selected[0])
        self.assertTrue((app / 'Generated/native-prepared-v1.txt').is_file())

    def shell_fixture(self, fail=False):
        app = self.root / 'shell-app'
        (app / 'Scripts').mkdir(parents=True)
        script = app / 'Scripts/build_native.sh'
        script.write_bytes((APP / 'Scripts/build_native.sh').read_bytes())
        binary = self.root / 'fixture-bin'
        binary.mkdir()
        log = self.root / 'commands.log'
        stub = '#!/bin/sh\nprintf "%s %s\\n" "$0" "$*" >> "$FIXTURE_LOG"\n'
        for name in ['python3', 'xcodegen', 'xcodebuild']:
            p = binary / name
            text = stub
            if name == 'python3':
                text += 'case "$*" in *--check-only*) [ "$FIXTURE_FAIL" = 0 ] || exit 7 ;; esac\n'
            p.write_text(text)
            p.chmod(0o700)
        env = {**os.environ, 'PATH': str(binary) + ':/usr/bin:/bin',
               'FIXTURE_LOG': str(log), 'FIXTURE_FAIL': str(int(fail))}
        result = subprocess.run(['/bin/sh', str(script)], env=env, capture_output=True)
        return result, log.read_text().splitlines()

    def test_real_rebuild_shell_checks_cache_before_other_preparation(self):
        result, commands = self.shell_fixture(fail=True)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(len(commands), 1)
        self.assertIn('Scripts/prepare_shaders.py --check-only --sdk iphoneos', commands[0])

    def test_real_rebuild_shell_routes_shader_step_through_shared_cache_selector(self):
        result, commands = self.shell_fixture()
        self.assertEqual(result.returncode, 0)
        self.assertIn('--check-only', commands[0])
        selected = [c for c in commands if 'Scripts/prepare_shaders.py' in c]
        self.assertEqual(len(selected), 2)
        self.assertNotIn('--check-only', selected[1])
        self.assertFalse(any('build_metal_shaders.py' in c for c in commands))
        self.assertIn('xcodebuild', commands[-1])
        self.assertIn('CODE_SIGNING_ALLOWED=NO', commands[-1])
        self.assertNotIn('allowProvisioningUpdates', commands[-1])


if __name__ == '__main__':
    unittest.main()
