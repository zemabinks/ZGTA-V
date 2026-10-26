#!/usr/bin/env python3
"""Reuse reviewed device UI assets without installing a simulator or running an IPA."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import stat
import subprocess
import tempfile
import zipfile

from prepare_shaders import CacheError, digest_file, no_symlinks

ROOT = Path(__file__).resolve().parents[1]
IPA_SHA = 'dfd36919dfe36986b15eaf43129a063ce7e655638479f344bb312b0971618bda'
ASSET_TREE_SHA = '04691ebbdc71106bcabc32eda8fc55b6d5270b9cc43c460b58aead3443273531'
REVISION = '6f061d12c58c23dbf99da7d4225996a6d586ab89'
PREFIX = 'Payload/PlayGTA5Native.app/'
FILES = {
    'Assets.car': (3498543, '7cd5191127544e3c139e582a802b133f0a53f0c365533ed8e974a7adc92304b7'),
    'AppIcon60x60@2x.png': (11130, '74b88431652fb4e7fa6583a919c3935fd68a672d79b3ece083fe224beccbf35c'),
    'AppIcon76x76@2x~ipad.png': (17355, '331da949954f2bda6c83c809ddec0b8de2b4284af5b9f0e1c9e170652fb54713'),
}


def validate_catalog(root):
    catalog = no_symlinks(root / 'App/Assets.xcassets')
    rows = []
    for path in sorted(catalog.rglob('*')):
        no_symlinks(path)
        if path.is_file():
            rows.append({'path': path.relative_to(catalog).as_posix(), 'sha256': digest_file(path)})
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if digest != ASSET_TREE_SHA:
        raise CacheError('UI sources changed; do not reuse this compiled catalog.')


def read_assets(ipa, root):
    validate_catalog(root)
    if digest_file(ipa) != IPA_SHA:
        raise CacheError('Reference IPA differs from the reviewed local input.')
    result = {}
    with zipfile.ZipFile(ipa) as archive:
        for name, (size, digest) in FILES.items():
            entries = [i for i in archive.infolist() if i.filename == PREFIX + name]
            if (len(entries) != 1 or entries[0].file_size != size
                    or stat.S_ISLNK(entries[0].external_attr >> 16)):
                raise CacheError('Invalid compiled UI entry: ' + name)
            data = archive.read(entries[0])
            if hashlib.sha256(data).hexdigest() != digest:
                raise CacheError('Compiled UI asset checksum mismatch: ' + name)
            result[name] = data
        if archive.read(PREFIX + 'iosvn-build-revision.txt').decode().strip() != REVISION:
            raise CacheError('Reference revision mismatch.')
        info = plistlib.loads(archive.read(PREFIX + 'Info.plist'))
        if info.get('DTPlatformName') != 'iphoneos' or info.get('CFBundleIdentifier') != 'vn.iosvn.mugoat':
            raise CacheError('Reference is not the reviewed iPhone application.')
    return result


def stage_assets(ipa, root):
    root = no_symlinks(root)
    data = read_assets(ipa, root)
    destination = no_symlinks(root / 'GeneratedUIAssets')
    if destination.exists():
        if set(p.name for p in destination.iterdir()) != set(FILES):
            raise CacheError('Existing UI staging differs; preserve it.')
        for name, (_, digest) in FILES.items():
            if digest_file(destination / name) != digest or (destination / name).stat().st_nlink != 1:
                raise CacheError('Existing UI staging differs; preserve it.')
        return 'REUSED'
    temp = Path(tempfile.mkdtemp(prefix='.device-ui-', dir=root))
    try:
        for name, content in data.items():
            (temp / name).write_bytes(content)
        os.rename(temp, destination)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return 'STAGED'


def project_spec(text):
    anchor = '        excludes:\n          - Info.plist\n'
    resources = '      - path: GeneratedResources\n'
    icons = '        CFBundleDisplayName: Mugoat\n'
    if any(text.count(value) != 1 for value in (anchor, resources, icons)):
        raise CacheError('Project spec changed; review UI asset integration.')
    text = text.replace(anchor, anchor + '          - Assets.xcassets\n')
    text = text.replace(resources, '      - path: GeneratedUIAssets\n        buildPhase: resources\n' + resources)
    return text.replace(icons, icons + '''        CFBundleIcons:
          CFBundlePrimaryIcon:
            CFBundleIconFiles: [AppIcon60x60]
            CFBundleIconName: AppIcon
        CFBundleIcons~ipad:
          CFBundlePrimaryIcon:
            CFBundleIconFiles: [AppIcon60x60, AppIcon76x76]
            CFBundleIconName: AppIcon
''')


def generate_project(root):
    # Put the temporary spec next to the real spec so all relative paths stay local.
    text = project_spec((root / 'project.yml').read_text())
    descriptor, name = tempfile.mkstemp(prefix='.intel-ui-', suffix='.yml', dir=root)
    try:
        with os.fdopen(descriptor, 'w') as output:
            output.write(text)
        subprocess.run(['xcodegen', 'generate', '--spec', name], cwd=root, check=True)
    finally:
        Path(name).unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-ipa', type=Path, required=True)
    parser.add_argument('--generate-project', action='store_true')
    args = parser.parse_args()
    try:
        result = stage_assets(args.reference_ipa, ROOT)
        if args.generate_project:
            generate_project(ROOT)
        print('DEVICE_UI_ASSETS=' + result + '; no IPA executable loaded or run')
    except (CacheError, OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
