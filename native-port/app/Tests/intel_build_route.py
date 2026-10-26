"""Build-gate and free-only packaging regressions with stubbed tools only."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / 'Scripts'))
import check_intel_build as ready


class IntelBuildRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gta-free-build-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.native = self.root / 'native-port'
        self.app = self.native / 'app'
        (self.app / 'App').mkdir(parents=True)
        (self.app / 'App/Free.entitlements').write_bytes(plistlib.dumps({}))
        (self.app / 'App/Info.plist').write_bytes(b'fixture source plist preserved')
        (self.native / 'online-bridge').mkdir()
        (self.native / 'online-bridge/Cargo.lock').write_text('fixture lock')
        self.script = self.native / 'build_ipa.sh'
        self.script.write_bytes((APP.parent / 'build_ipa.sh').read_bytes())
        self.mirror = self.root / 'mirror'
        self.mirror.mkdir()
        self.binary = self.root / 'fixture-bin'
        self.binary.mkdir()
        self.log = self.root / 'commands.log'
        stub = r'''#!/bin/bash
printf '%s %s\n' "${0##*/}" "$*" >> "$FIXTURE_LOG"
case "${0##*/}" in
 python3)
   case "$*" in *check_intel_build.py*) exit "${FIXTURE_PREFLIGHT:-0}" ;;
     *prepare.py*) /bin/mkdir -p "$FIXTURE_NATIVE/app/Resources"; printf '{}' > "$FIXTURE_NATIVE/app/Resources/manifest.json" ;; esac ;;
 cargo) /bin/mkdir -p "$FIXTURE_NATIVE/app/Build/Online/RustTarget/aarch64-apple-ios/release"; printf 'fixture static lib' > "$FIXTURE_NATIVE/app/Build/Online/RustTarget/aarch64-apple-ios/release/libmugoat_online.a" ;;
 xcodebuild)
   while [ "$#" -gt 0 ]; do
     if [ "$1" = -derivedDataPath ]; then shift; /bin/mkdir -p "$1/Build/Products/Release-iphoneos/PlayGTA5Native.app"; break; fi
     shift
   done ;;
 ditto) /bin/cp -R "$1" "$2" ;;
 git) printf '%040d\n' 0 ;;
 zip) /usr/bin/touch "$2" ;;
 codesign) : ;;
esac
'''
        for name in ['python3', 'cargo', 'xcodebuild', 'ditto', 'git', 'zip', 'codesign']:
            p = self.binary / name
            p.write_text(stub)
            p.chmod(0o700)
        self.env = {**os.environ, 'PATH': str(self.binary) + ':/usr/bin:/bin',
                    'PYTHON': str(self.binary / 'python3'), 'FIXTURE_LOG': str(self.log),
                    'FIXTURE_NATIVE': str(self.native), 'PG_REUSE_PREPARED': '0', 'JOBS': '2',
                    'BUNDLE_ID': 'com.fixture.gta.english'}

    def shell(self, extra=None, env=None):
        return subprocess.run(['/bin/bash', str(self.script), '--mirror', str(self.mirror), *(extra or [])],
                              env={**self.env, **(env or {})}, capture_output=True, text=True, timeout=10)

    def commands(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_check_only_never_builds_signs_or_packages(self):
        result = self.shell(['--check-only'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.commands()), 1)
        self.assertFalse((self.app / 'Build').exists())

    def test_failed_preflight_preserves_source_and_stops_before_build_writes(self):
        result = self.shell(env={'FIXTURE_PREFLIGHT': '2'})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(len(self.commands()), 1)
        self.assertFalse((self.app / 'Build').exists())
        self.assertEqual((self.app / 'App/Info.plist').read_bytes(), b'fixture source plist preserved')

    def test_paid_option_unsafe_reuse_and_bad_jobs_are_refused(self):
        for extra, env in [(['--paid'], {}), ([], {'PG_REUSE_PREPARED': '1'}), ([], {'JOBS': '99'})]:
            with self.subTest(extra=extra, env=env):
                self.assertEqual(self.shell(extra, env).returncode, 2)
        self.assertEqual(self.commands(), [])

    def test_reference_identity_and_malformed_identity_are_refused(self):
        for value in ['vn.iosvn.mugoat', 'com..fixture', 'com.fixture;bad', 'com.fixture.']:
            self.assertEqual(self.shell(env={'BUNDLE_ID': value}).returncode, 2)
        self.assertEqual(self.commands(), [])

    def test_remote_asset_fetch_is_not_an_entry_route(self):
        result = subprocess.run(['/bin/bash', str(self.script), 'https://fixture.invalid'],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.commands(), [])

    def test_stubbed_build_is_locked_offline_free_only_and_preserves_prior_outputs(self):
        for _ in range(2):
            result = self.shell()
            self.assertEqual(result.returncode, 0, result.stderr)
        commands = '\n'.join(self.commands())
        self.assertIn('cargo build --offline --locked', commands)
        self.assertIn('CODE_SIGNING_ALLOWED=NO', commands)
        self.assertIn('CODE_SIGN_ENTITLEMENTS=App/Free.entitlements', commands)
        self.assertIn('PRODUCT_BUNDLE_IDENTIFIER=com.fixture.gta.english', commands)
        self.assertNotIn('Full.entitlements', commands)
        self.assertNotIn('allowProvisioningUpdates', commands)
        self.assertEqual(len(list((self.app / 'Build').glob('English-Intel-Free-*/Mugoat-English-Intel-Free.ipa'))), 2)
        self.assertEqual((self.app / 'App/Info.plist').read_bytes(), b'fixture source plist preserved')

    def readiness(self, rust=False, command_failure=None):
        sysroot = self.root / 'sdk'
        sysroot.mkdir(exist_ok=True)
        std = self.root / 'rust-std'
        std.mkdir(exist_ok=True)
        (std / 'libstd-fixture.rlib').write_bytes(b'fixture')
        def which(tool, **_):
            return '/fixture/' + tool if rust or tool == 'xcodegen' else None
        def run(command, **options):
            self.assertEqual(options['env']['CARGO_NET_OFFLINE'], 'true')
            self.assertEqual(options['env']['RUSTUP_AUTO_INSTALL'], '0')
            if 'metadata' in command:
                self.assertIn('--offline', command)
                self.assertIn('--locked', command)
            output = str(sysroot) if '--show-sdk-path' in command else str(std) if 'target-libdir' in command else 'arm64' if '-archs' in command else '{}'
            return subprocess.CompletedProcess(command, 1 if command_failure and command_failure in command else 0,
                                               stdout=output, stderr='')
        with patch.object(ready.platform, 'system', return_value='Darwin'), \
                patch.object(ready.platform, 'machine', return_value='x86_64'), \
                patch.object(ready, 'verify_staged'), patch.object(ready, 'validate_intel_tools'), \
                patch.object(ready, 'validate_selection'), patch.object(ready.shutil, 'which', side_effect=which), \
                patch.object(ready.subprocess, 'run', side_effect=run) as child:
            result = ready.check(self.app, self.mirror)
            return result, [call.args[0] for call in child.call_args_list]

    def test_missing_rust_reports_actual_gap_and_never_invokes_rust_commands(self):
        result, commands = self.readiness()
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['gaps'], ['Required existing tool missing: cargo', 'Required existing tool missing: rustc'])
        self.assertFalse(any('metadata' in c for c in commands))

    def test_all_fake_prerequisites_allow_only_build_attempt_not_runtime_acceptance(self):
        result, commands = self.readiness(rust=True)
        self.assertEqual(result['status'], 'READY_TO_ATTEMPT_BUILD')
        self.assertIn('no app build', result['scope'])
        self.assertTrue(any('metadata' in c for c in commands))

    def test_missing_offline_crate_cache_is_not_silently_downloaded(self):
        result, _ = self.readiness(rust=True, command_failure='metadata')
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertTrue(any('rust_offline_dependencies' in gap for gap in result['gaps']))

    def test_paid_entitlement_data_prevents_build_readiness(self):
        (self.app / 'App/Free.entitlements').write_bytes(plistlib.dumps({'com.apple.developer.kernel.increased-memory-limit': True}))
        result, _ = self.readiness()
        self.assertTrue(any('free-entitlement' in gap for gap in result['gaps']))

    def test_online_lock_uses_the_original_host_lock_anyhow_identity(self):
        import re
        source = (APP.parents[1] / 'Cargo.lock').read_text()
        block = next(b for b in source.split('[[package]]') if '\nname = "anyhow"\n' in '\n' + b)
        lock = (APP.parent / 'online-bridge/Cargo.lock').read_text()
        self.assertIn(block.strip(), lock)
        self.assertIn('name = "mugoat-online"', lock)

    def test_checked_in_free_profile_does_not_request_extra_memory_entitlements(self):
        self.assertEqual(plistlib.loads((APP / 'App/Free.entitlements').read_bytes()), {})


if __name__ == '__main__':
    unittest.main()
