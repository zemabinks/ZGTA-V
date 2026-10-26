#!/usr/bin/env python3
"""Stage exact local Intel inputs as independent files; no installs or builds."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tempfile

from prepare_shaders import CacheError, digest_file, no_symlinks

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'IntelInputs/tools-v1.json'
MANIFEST_SHA = 'dfc7faa45a4927efb7a032da96c4a8947a08704b168f5967f72fdce21852b7e2'
RECEIPT = 'intel-staged-v1.json'
BUILD_OUTPUTS = {'c-writer-patched.cc', 'sha256_shim.o', 'wasm2c-native'}


def relative(value):
    if (not isinstance(value, str) or not value or any(ord(c) < 32 for c in value)
            or '\\' in value or PurePosixPath(value).is_absolute()
            or PurePosixPath(value).as_posix() != value
            or any(p in ('.', '..') or p.startswith('.') for p in value.split('/'))):
        raise CacheError('Invalid dependency path.')
    return value


def validate_rows(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 2000:
        raise CacheError('Invalid dependency inventory.')
    seen = set()
    total = 0
    for row in rows:
        if set(row) != {'path', 'source', 'bytes', 'sha256', 'executable'}:
            raise CacheError('Invalid dependency record.')
        path = relative(row['path'])
        relative(row['source'])
        if path in seen or path == RECEIPT:
            raise CacheError('Duplicate/reserved dependency path.')
        seen.add(path)
        if (type(row['bytes']) is not int or not 0 < row['bytes'] <= 32 * 1024 * 1024
                or type(row['executable']) is not bool
                or not isinstance(row['sha256'], str) or len(row['sha256']) != 64
                or any(c not in '0123456789abcdef' for c in row['sha256'])):
            raise CacheError('Invalid dependency digest/size/mode.')
        total += row['bytes']
    if total > 64 * 1024 * 1024:
        raise CacheError('Dependency inventory exceeds reviewed size.')
    return rows


def load_manifest():
    if digest_file(MANIFEST) != MANIFEST_SHA:
        raise CacheError('Intel input manifest does not match the reviewed bytes.')
    data = json.loads(MANIFEST.read_text())
    if data.get('format') != 'gta-intel-tool-inputs-v1':
        raise CacheError('Unsupported dependency manifest.')
    validate_rows(data['files'])
    return data


def verify_files(root, rows, source=False, exact=False):
    root = no_symlinks(root)
    if not root.is_dir():
        raise CacheError('Dependency directory is missing.')
    validate_rows(rows)
    for row in rows:
        path = root / row['source' if source else 'path']
        if digest_file(path) != row['sha256'] or path.stat().st_size != row['bytes']:
            raise CacheError('Dependency SHA-256/size mismatch: ' + row['path'])
        if not source and path.stat().st_nlink != 1:
            raise CacheError('Staged dependencies must be independent copies.')
        if not source and bool(path.stat().st_mode & 0o111) != row['executable']:
            raise CacheError('Staged dependency executable mode mismatch.')
    if exact:
        found = set()
        for path in root.rglob('*'):
            no_symlinks(path)
            if path.is_file():
                found.add(path.relative_to(root).as_posix())
        expected = {r['path'] for r in rows} | {RECEIPT}
        if not expected <= found or found - expected - BUILD_OUTPUTS:
            raise CacheError('Existing Tools has additional or missing files; preserve it.')
        for name in found & BUILD_OUTPUTS:
            info = (root / name).lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise CacheError('Generated tools must not alias original inputs.')


def verify_staged(root, rows):
    verify_files(root, rows, exact=True)
    receipt = root / RECEIPT
    if (stat.S_IMODE(receipt.stat().st_mode) != 0o600
            or json.loads(receipt.read_text()) !=
            {'format': 'gta-intel-staged-v1', 'manifest_sha256': MANIFEST_SHA}):
        raise CacheError('Staged dependency receipt mismatch.')


def stage(source, app, rows):
    source, app = no_symlinks(source), no_symlinks(app)
    if (app == source or source in app.parents or app in source.parents
            or not app.is_dir()):
        raise CacheError('Dependency destination must be a separate existing app tree.')
    # The actual source is inside the old Intel app; never stage back into it.
    original_app = source.parent
    if app == original_app or original_app in app.parents:
        raise CacheError('Original Intel app is read-only.')
    verify_files(source, rows, source=True)
    destination = no_symlinks(app / 'Tools')
    if destination.exists():
        verify_staged(destination, rows)
        return 'REUSED'
    temporary = Path(tempfile.mkdtemp(prefix='.intel-tools-', dir=app))
    try:
        for row in rows:
            target = temporary / row['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / row['source'], target)
            target.chmod(0o755 if row['executable'] else 0o644)
        receipt = temporary / RECEIPT
        receipt.write_text(json.dumps({'format': 'gta-intel-staged-v1', 'manifest_sha256': MANIFEST_SHA}, sort_keys=True) + '\n')
        receipt.chmod(0o600)
        verify_files(temporary, rows, exact=True)
        os.rename(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return 'STAGED'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--app-root', type=Path, default=ROOT)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest()
        source = args.source or Path(manifest['source_root'])
        if args.verify_only:
            verify_staged(args.app_root / 'Tools', manifest['files'])
            result = 'VERIFIED'
        else:
            result = stage(source, args.app_root, manifest['files'])
        print('INTEL_DEPENDENCIES=' + result + ' files=' + str(len(manifest['files'])))
        return 0
    except (CacheError, OSError, ValueError, KeyError, TypeError) as error:
        print('INTEL_DEPENDENCIES_BLOCKED: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
