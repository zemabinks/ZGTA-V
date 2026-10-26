#!/usr/bin/env python3
"""Read-only local build prerequisites; never install, compile or fetch inputs."""
import argparse
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys

from prepare_shaders import cache_path, validate_selection, validate_intel_tools
from stage_intel_dependencies import load_manifest, verify_staged

ROOT = Path(__file__).resolve().parents[1]


def offline_environment():
    toolchain = Path(os.environ.get('GTA_RUST_TOOLCHAIN',
                     str(ROOT.parents[2] / 'gta-intel-toolchain-20261016'))).expanduser().absolute()
    return {**os.environ, 'CARGO_NET_OFFLINE': 'true', 'RUSTUP_AUTO_INSTALL': '0',
            'CARGO_HOME': str(toolchain / 'cargo'), 'RUSTUP_HOME': str(toolchain / 'rustup'),
            'PATH': str(toolchain / 'cargo/bin') + os.pathsep + os.environ.get('PATH', '')}


def check(root, mirror):
    gaps, observations = [], {}
    if platform.system() != 'Darwin' or platform.machine() != 'x86_64':
        gaps.append('This local profile requires an Intel Mac.')
    for label, operation in [
            ('intel_tools', lambda: (verify_staged(root / 'Tools', load_manifest()['files']), validate_intel_tools(root))),
            ('shaders', lambda: validate_selection(cache_path(), ['iphoneos']))]:
        try:
            operation()
            observations[label] = 'VERIFIED_INPUTS_ONLY'
        except (OSError, ValueError, KeyError, TypeError):
            gaps.append(label + ': missing or mismatched pinned inputs; nothing replaced.')
    try:
        entitlements = plistlib.loads((root / 'App/Free.entitlements').read_bytes())
        if entitlements != {}:
            raise ValueError('free entitlement profile changed')
        observations['entitlements'] = 'EMPTY_FREE_PROFILE'
    except (OSError, ValueError):
        gaps.append('The empty free-entitlement profile is unavailable.')
    for tool in ['xcodegen', 'cargo', 'rustc']:
        path = shutil.which(tool, path=offline_environment()['PATH'])
        observations[tool] = path or 'MISSING'
        if path is None:
            gaps.append('Required existing tool missing: ' + tool)
    lock = root.parent / 'online-bridge/Cargo.lock'
    if not lock.is_file():
        gaps.append('The online bridge dependency lock is missing.')
    commands = [
        ('game_inputs', [sys.executable, '-B', str(root / 'Scripts/check_game_files.py'), '--mirror', str(mirror)]),
        ('iphone_sdk', ['/usr/bin/xcrun', '--sdk', 'iphoneos', '--show-sdk-path']),
        ('libarchive_ios', ['/usr/bin/lipo', '-archs', str(root / 'Vendor/libarchive.xcframework/ios-arm64/libarchive.a')]),
    ]
    if observations.get('rustc') != 'MISSING':
        commands.append(('rust_ios_target', [observations['rustc'], '--print', 'target-libdir', '--target', 'aarch64-apple-ios']))
    if observations.get('cargo') != 'MISSING' and lock.is_file():
        commands.append(('rust_offline_dependencies', [observations['cargo'], 'metadata', '--offline', '--locked',
                         '--manifest-path', str(root.parent / 'online-bridge/Cargo.toml'), '--format-version', '1']))
    for label, command in commands:
        try:
            result = subprocess.run(command, cwd=root, env=offline_environment(),
                                    capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise ValueError('prerequisite failed')
            if label == 'rust_ios_target' and not list(Path(result.stdout.strip()).glob('libstd-*.rlib')):
                raise ValueError('iOS std target missing')
            if label == 'iphone_sdk' and not Path(result.stdout.strip()).is_dir():
                raise ValueError('SDK directory missing')
            if label == 'libarchive_ios' and 'arm64' not in result.stdout.split():
                raise ValueError('iOS archive architecture mismatch')
            observations[label] = 'AVAILABLE_NOT_COMPILED'
        except (OSError, ValueError, subprocess.SubprocessError):
            observations[label] = 'UNAVAILABLE'
            gaps.append(label + ': unavailable or incompatible; no download attempted.')
    return {'format': 'gta-intel-build-readiness-v1', 'status': 'READY_TO_ATTEMPT_BUILD' if not gaps else 'BLOCKED',
            'scope': 'Inputs only; no app build, signing, installation or runtime validation.',
            'observations': observations, 'gaps': gaps}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mirror', type=Path, required=True)
    args = parser.parse_args(argv)
    result = check(ROOT, args.mirror)
    print(json.dumps(result, indent=2))
    return 2 if result['gaps'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
