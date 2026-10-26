#!/usr/bin/env python3
"""New permissions-only IPA from an exact existing package; no build or install."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

APP = Path(__file__).resolve().parent.parent / 'app'
sys.path.insert(0, str(APP / 'Scripts'))
from ipa_permissions import rewrite_archive
from package_trollstore import MEMORY
from prepare_shaders import digest_file, no_symlinks, verify_pair


def repair(source, output, expected_sha256):
    source, output = no_symlinks(source), no_symlinks(output)
    build = APP.absolute() / 'Build'
    if not source.is_relative_to(build) or not output.is_relative_to(build):
        raise ValueError('Use only isolated Build inputs and a new output directory')
    if output.exists() or output in source.parents:
        raise ValueError('Preserve existing package and build folders')
    if digest_file(source) != expected_sha256:
        raise ValueError('Source IPA differs from the reviewed package')
    output.mkdir(mode=0o700)
    ipa = output / 'zema-EngineLAN-Build29-TrollStoreFix.ipa'
    report = rewrite_archive(source, ipa)
    if report['bundle_identifier'] != 'com.zemabinks.gtamp.enginelanlab' or str(report['build']) != '29':
        raise ValueError('Expected the reviewed Build 29 lab app')
    verified = output / 'VerifiedPayload'
    subprocess.run(['/usr/bin/ditto', '-x', '-k', str(ipa), str(verified)], check=True)
    app = verified / report['app_path']
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    entitlements = subprocess.run(['/usr/bin/codesign', '-d', '--entitlements', ':-', str(app)],
                                 capture_output=True, check=True).stdout
    if plistlib.loads(entitlements) != MEMORY:
        raise ValueError('Preserved signature has unexpected entitlements')
    verify_pair(app)
    if app.stat().st_mode & 0o777 != 0o755:
        raise ValueError('Extracted app root is not readable/traversable by iOS')
    if digest_file(source) != expected_sha256:
        raise ValueError('Original package changed during repair')
    report.update(source_ipa=str(source), source_sha256=expected_sha256, ipa=str(ipa),
                  sha256=digest_file(ipa), bytes=ipa.stat().st_size,
                  signature='ORIGINAL_AD_HOC_STRICT_PASS', entitlements='UNCHANGED',
                  shader_inputs='PINNED_INTEL_PAIR_REUSED', game_binary='BYTE_IDENTICAL',
                  source_preserved=digest_file(source) == expected_sha256,
                  installed=False, device_registration_verified=False, gameplay_verified=False)
    (output / 'package-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    (output / (ipa.name + '.sha256')).write_text(report['sha256'] + '  ' + ipa.name + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ipa', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    print(json.dumps(repair(args.ipa.absolute(), args.output.absolute(), args.sha256), indent=2))
