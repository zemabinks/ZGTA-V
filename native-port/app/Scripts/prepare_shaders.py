#!/usr/bin/env python3
"""Reuse the verified iPhone shader pair on Intel; never mutate its source.

Importing this module performs no IO. --check-only performs read-only validation;
an invalid selected cache never falls back to downloads or shader compilation.
"""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PINNED = {
    'shaders-iphoneos.metallib': '26af7e628dea528ab2803c39c32e50dd47075be3c3a5efe7d142bba55db3dd3c',
    'shader-reflection.jsonl': 'b1119c7e9d6c7f00f407492b21d28847ce9ba9da29a041e25ff54a2e76a2b4db',
}


class CacheError(ValueError):
    pass


def intel_mac():
    return platform.system() == 'Darwin' and platform.machine() == 'x86_64'


def cache_path(explicit=None):
    value = explicit if explicit is not None else os.environ.get('GTA_BASELINE_SHADERS')
    if value is not None:
        if not str(value).strip():
            raise CacheError('Selected shader cache path is empty.')
        return Path(value).expanduser().absolute()
    if intel_mac():
        return Path.home() / 'Documents/GTA-MP-IntelBuild/upstream/app/GeneratedResources'
    return None


def no_symlinks(path):
    path = Path(path).absolute()
    for component in (path, *path.parents):
        if component.is_symlink():
            raise CacheError('Shader resource paths must not contain symlinks.')
    return path


def digest_file(path):
    no_symlinks(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise CacheError('Shader resources must be regular files.')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_pair(source):
    source = no_symlinks(source)
    if not source.is_dir():
        raise CacheError('Verified Intel shader cache directory is missing.')
    for name, expected in PINNED.items():
        if digest_file(source / name) != expected:
            raise CacheError('Pinned Intel shader SHA-256 mismatch: ' + name)
    return source


def install_pair(source, destination):
    source = verify_pair(source)  # Validate both inputs before any write.
    destination = no_symlinks(destination)
    if destination.exists():
        if not destination.is_dir():
            raise CacheError('GeneratedResources must be a directory.')
        if any(destination.iterdir()):
            # Preserve existing generated data rather than repairing/replacing it.
            verify_pair(destination)
            return 'REUSED'
    if not destination.parent.is_dir():
        raise CacheError('Shader destination parent is missing.')
    staging = Path(tempfile.mkdtemp(prefix='.intel-shaders-', dir=destination.parent))
    try:
        for name in PINNED:
            shutil.copyfile(source / name, staging / name)
        verify_pair(staging)  # Detect input changes or a failed/truncated copy.
        # Publish the verified pair together, never one file at a time.
        # A nonempty destination appearing concurrently makes rename fail.
        os.replace(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return 'COPIED'


def validate_selection(source, sdks):
    if source is not None:
        if set(sdks) != {'iphoneos'}:
            raise CacheError('The verified cache is iPhone-only; simulator shaders are not available.')
        verify_pair(source)
    elif intel_mac():
        raise CacheError('Intel requires the verified precompiled iPhone shader cache.')


def validate_intel_tools(root):
    """Require separately staged local inputs before prepare can mutate/build.

    Do not copy from or patch the original Intel workspace automatically. These
    are prerequisites, not an architecture/provenance attestation of binaries.
    """
    files = ['Tools/wabt-1.0.42/lib/libwabt.a',
             'Tools/WABT-x86_64-build/include/wabt/config.h',
             'Tools/wabt-1.0.42/share/wabt/wasm2c/wasm-rt-impl.c',
             'Tools/c-writer-original.cc', 'Tools/wasm2c-main.cc',
             'Tools/bcdec/bcdec.h']
    directories = ['Tools/wabt-1.0.42/include', 'Tools/simde/simde']
    missing = [name for name in files if not (root / name).is_file()]
    missing += [name for name in directories if not (root / name).is_dir()]
    if missing:
        raise CacheError('Intel preparation needs separately verified local tool inputs; '
                         'no ARM download or installation attempted. Missing: ' + ', '.join(missing))
    for name in files + directories:
        no_symlinks(root / name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shader-cache', type=Path,
                        help='Verified Build10 resource pair; defaults to GTA_BASELINE_SHADERS or the existing Intel folder')
    parser.add_argument('--sdk', action='append', choices=['iphoneos', 'iphonesimulator'])
    parser.add_argument('--shaders', type=Path, default=ROOT / 'Build/Inputs/shaders')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args(argv)
    try:
        source = cache_path(args.shader_cache)
        sdks = args.sdk or ['iphoneos']
        validate_selection(source, sdks)
        if args.check_only:
            print('SHADERS=VERIFIED_CACHE' if source else 'SHADERS=COMPILATION_REQUIRED')
        elif source is not None:
            result = install_pair(source, ROOT / 'GeneratedResources')
            print('INTEL_SHADER_REUSE=PASS ' + result + ' (two pinned iPhone Build10 resources)')
        else:
            if platform.system() != 'Darwin':
                raise CacheError('Shader compilation requires an existing compatible Mac toolchain.')
            command = [sys.executable, '-B', str(ROOT / 'Scripts/build_metal_shaders.py'), str(args.shaders)]
            for sdk in sdks:
                command += ['--sdk', sdk]
            subprocess.run(command, check=True, cwd=ROOT)
        return 0
    except (CacheError, OSError, subprocess.SubprocessError) as error:
        print('SHADER_PREPARATION_BLOCKED: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
