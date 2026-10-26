#!/usr/bin/env python3
"""Run the local suite against current transport source, preserving old build caches.

Uses only the existing offline Intel toolchain, temporary build outputs, Xcode
and the pinned local game fixtures. No tool install, device or hosted CI run.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    tool = ROOT.parents[2] / 'gta-intel-toolchain-20261016'
    cargo = tool / 'cargo/bin/cargo'
    if not cargo.is_file() or not (tool / 'rustup').is_dir():
        raise ValueError('The existing offline Intel toolchain is unavailable. No installation was attempted.')
    env = dict(os.environ, CARGO_HOME=str(tool / 'cargo'), RUSTUP_HOME=str(tool / 'rustup'),
               CARGO_NET_OFFLINE='true', RUSTUP_AUTO_INSTALL='0', PYTHONDONTWRITEBYTECODE='1')
    with tempfile.TemporaryDirectory(prefix='zgta-current-regressions-') as temporary:
        target = Path(temporary) / 'rust'
        common = [str(cargo), '--offline', '--locked', '--manifest-path', str(ROOT / 'Cargo.toml'), '--target-dir', str(target)]
        for operation in ['test', 'build']:
            result = subprocess.run([common[0], operation, *common[1:]], cwd=ROOT, env=env)
            if result.returncode:
                return result.returncode
        library = target / 'debug/libzema_engine_lan.a'
        if not library.is_file():
            raise ValueError('Current host transport library was not produced.')
        env['ZEMA_TEST_LAN_LIBRARY'] = str(library)
        print(json.dumps({'transport': 'CURRENT_SOURCE_OFFLINE_BUILD', 'original_cached_library_changed': False}), flush=True)
        return subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'), '-p', 'test_*.py'], cwd=ROOT.parents[1], env=env).returncode


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
