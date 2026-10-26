#!/usr/bin/env python3
"""Package an already built local ARM64 app with the original memory requests.

No builds, downloads, Apple account/provisioning, installation or device access.
The generic Free.entitlements and earlier packages are left unchanged.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import struct
import subprocess
import zipfile

from prepare_shaders import CacheError, digest_file, no_symlinks, verify_pair
from ipa_permissions import normalize_bundle

ROOT = Path(__file__).resolve().parents[1]
MEMORY = {'com.apple.developer.kernel.increased-memory-limit': True,
          'com.apple.developer.kernel.extended-virtual-addressing': True}
IDENTITY = 'com.zemabinks.gtamp.englishlab'
UI_SHA = '7cd5191127544e3c139e582a802b133f0a53f0c365533ed8e974a7adc92304b7'


def profile(root):
    selected = no_symlinks(root / 'App/TrollStore.entitlements')
    if plistlib.loads(selected.read_bytes()) != MEMORY:
        raise CacheError('TrollStore profile must contain only the two reviewed memory requests.')
    if selected.read_bytes() != (root / 'App/Full.entitlements').read_bytes():
        raise CacheError('TrollStore profile differs from the preserved upstream memory profile.')
    if plistlib.loads((root / 'App/Free.entitlements').read_bytes()) != {}:
        raise CacheError('Preserve the empty generic free signing profile.')
    return selected


def validate(app, output, receipt, head):
    app, output, receipt = (no_symlinks(p) for p in (app, output, receipt))
    build = ROOT / 'Build'
    if not all(p.is_relative_to(build) for p in (app, output, receipt)):
        raise CacheError('Use only the isolated app Build directory.')
    if output.exists() or output in app.parents or app in output.parents:
        raise CacheError('Preserve existing outputs and use a new separate package directory.')
    info = plistlib.loads((app / 'Info.plist').read_bytes())
    if info.get('CFBundleIdentifier') != IDENTITY or info.get('DTPlatformName') != 'iphoneos':
        raise CacheError('Only the separate English-lab iPhone app may be packaged.')
    executable = app / info['CFBundleExecutable']
    with executable.open('rb') as source:
        if struct.unpack('<II', source.read(8)) != (0xfeedfacf, 0x100000c):
            raise CacheError('Expected a thin ARM64 Mach-O executable.')
    record = json.loads(receipt.read_text())
    if (record.get('exit_code') != 0 or record.get('tool_head') != head
            or record.get('app_executable_sha256') != digest_file(executable)):
        raise CacheError('Build receipt does not identify this exact successful app/source revision.')
    verify_pair(app)
    if digest_file(app / 'Assets.car') != UI_SHA:
        raise CacheError('Compiled device UI catalog mismatch.')
    return info


def package(app, output, receipt):
    root = ROOT
    selected = profile(root)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    info = validate(app, output, receipt, head)
    output.mkdir(mode=0o700)
    payload = output / 'Payload'
    payload.mkdir()
    target = payload / 'PlayGTA5Native.app'
    subprocess.run(['/usr/bin/ditto', str(app), str(target)], check=True)
    (target / 'zema-build-revision.txt').write_text(head + '\n')
    for source, name in [(root.parents[1] / 'LICENSE', 'LICENSE-mugoat.txt'),
                         (root.parent / 'LICENSE', 'LICENSE-native-port.txt'),
                         (root / 'Vendor/LICENSE-libarchive.txt', 'LICENSE-libarchive.txt'),
                         (root / 'Tools/bcdec/LICENSE', 'LICENSE-bcdec.txt'),
                         (root / 'Tools/simde/COPYING', 'LICENSE-simde.txt'),
                         (root / 'Tools/wabt-1.0.42/LICENSE', 'LICENSE-wabt.txt')]:
        (target / name).write_bytes(source.read_bytes())
    report = {'format': 'gta-trollstore-package-v1', 'source_revision': head,
              'upstream_repository': 'https://github.com/iOSVNNews/mugoat',
              'upstream_revision': '6f061d12c58c23dbf99da7d4225996a6d586ab89',
              'port_brand': 'zema', 'bundle_identifier': IDENTITY, 'profile': 'TROLLSTORE_EXISTING_UPSTREAM_MEMORY_REQUESTS',
              'entitlements': MEMORY, 'cost': 'No paid service or account used',
              'installation_method': 'User-reported existing TrollStore',
              'device_runtime': 'UNVERIFIED', 'multiplayer_runtime': 'UNVERIFIED',
              'memory_grant': 'REQUESTED_NOT_DEVICE_VERIFIED', 'app_installed': False}
    (target / 'local-build-info.json').write_text(json.dumps(report, indent=2) + '\n')
    payload.chmod(0o755)
    normalize_bundle(target)
    subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-', '--entitlements', str(selected),
                    '--generate-entitlement-der', str(target)], check=True)
    normalize_bundle(target)  # Include any newly created signature directory.
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(target)], check=True)
    ent = subprocess.run(['/usr/bin/codesign', '-d', '--entitlements', ':-', str(target)],
                         capture_output=True, check=True)
    (output / 'signed-entitlements.plist').write_bytes(ent.stdout)
    if plistlib.loads(ent.stdout) != MEMORY:
        raise CacheError('Actual signed memory profile differs from the reviewed requests.')
    ipa = output / 'Mugoat-zema-English-Intel-TrollStore.ipa'
    subprocess.run(['/usr/bin/zip', '-qry', str(ipa), 'Payload'], cwd=output, check=True)
    with zipfile.ZipFile(ipa) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(set(archive.namelist())):
            raise CacheError('Package CRC or duplicate-path failure.')
    report.update(ipa=str(ipa), bytes=ipa.stat().st_size, sha256=digest_file(ipa),
                  signature='AD_HOC_VERIFIED', archive='CRC_PASS',
                  shaders='PINNED_PAIR_PASS', ui_assets='PINNED_CATALOG_PASS')
    (output / 'package-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    (output / 'Mugoat-zema-English-Intel-TrollStore.ipa.sha256').write_text(report['sha256'] + '  ' + ipa.name + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--build-receipt', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        print(json.dumps(package(args.app.absolute(), args.output.absolute(), args.build_receipt.absolute()), indent=2))
    except (CacheError, OSError, ValueError, KeyError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
