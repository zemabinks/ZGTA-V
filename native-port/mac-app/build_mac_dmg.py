#!/usr/bin/env python3
"""Package an already checked portable payload in a self-contained Mac app/DMG."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import plistlib
import posixpath
import shutil
import subprocess
import sys
import tarfile
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / 'engine-lan'))
from portable_launcher import verify_package
from package_portable import sha256

def archive_members(archive):
    members = archive.getmembers()
    if len(members) > 20000 or sum(m.size for m in members) > 400 * 1024 * 1024:
        raise ValueError('Python archive exceeds its bounds')
    for member in members:
        name = PurePosixPath(member.name)
        if name.is_absolute() or '..' in name.parts or not name.parts or name.parts[0] != 'python':
            raise ValueError('Unsafe Python archive member')
        if not (member.isfile() or member.isdir() or member.issym()):
            raise ValueError('Unsupported Python archive member type')
        if member.issym():
            target = posixpath.normpath(posixpath.join(posixpath.dirname(member.name), member.linkname))
            if member.linkname.startswith('/') or not target.startswith('python/'):
                raise ValueError('Escaping Python archive symlink')
    return members

def runtime(arch, pin, release, cache, destination):
    archive = cache / pin['file']
    if not archive.exists():
        url = 'https://github.com/astral-sh/python-build-standalone/releases/download/' + release + '/' + urllib.parse.quote(pin['file'])
        with urllib.request.urlopen(url, timeout=90) as source, archive.open('xb') as target:
            shutil.copyfileobj(source, target)
    if archive.stat().st_size != pin['bytes'] or sha256(archive) != pin['sha256']:
        raise ValueError('Pinned runtime archive mismatch: ' + arch)
    temp = destination.parent / (arch + '-extract')
    temp.mkdir()
    with tarfile.open(archive, 'r:gz') as source:
        source.extractall(temp, members=archive_members(source))
    (temp / 'python').rename(destination)
    temp.rmdir()
    for file in destination.rglob('*'):
        if file.is_symlink() and not file.resolve().is_relative_to(destination.resolve()):
            raise ValueError('Runtime link escapes the app')
    licenses = [p for p in destination.rglob('*') if p.is_file() and ('license' in p.name.lower() or 'copyright' in p.name.lower())]
    if not licenses:
        raise ValueError('Runtime license texts absent')
    return {'architecture':arch, **pin, 'license_texts':len(licenses)}

def run(*args):
    subprocess.run(list(map(str,args)), check=True)

def build(payload, output, cache):
    if output.exists() or output.is_symlink():
        raise ValueError('Use a new output folder')
    manifest = verify_package(payload)
    if manifest['build'] != 109 or manifest['source_revision'] != '3648065f50928fb8cd147d04bb17363f4b1e4b05':
        raise ValueError('This Mac wrapper expects the checked Build109 payload')
    if subprocess.check_output(['git','status','--porcelain=v1'],cwd=REPO):
        raise ValueError('Commit wrapper source before candidate packaging')
    revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    output.mkdir(parents=True); cache.mkdir(parents=True,exist_ok=True)
    volume = output / 'Disk Image'; volume.mkdir()
    app = volume / 'ZGTA V.app'; contents = app / 'Contents'; resources = contents / 'Resources'
    resources.mkdir(parents=True); (contents/'MacOS').mkdir()
    shutil.copytree(payload, resources/'Payload', symlinks=True)
    # The app never writes into its verified payload; no external Python is needed.
    shutil.copy2(HERE/'mac_host.py',resources/'mac_host.py')
    shutil.copy2(HERE.parent/'engine-lan/desktop-assets/zgta-v.icns',resources/'ZGTA-V.icns')
    pins = json.loads((HERE/'python-runtimes.json').read_text())
    runtimes = resources/'Python'; runtimes.mkdir()
    provenance = [runtime(arch,pin,pins['release'],cache,runtimes/arch) for arch,pin in pins['architectures'].items()]
    info = {'CFBundleIdentifier':'com.zemabinks.zgtav.mac','CFBundleName':'ZGTA V','CFBundleDisplayName':'ZGTA V',
            'CFBundleExecutable':'ZGTA-V','CFBundlePackageType':'APPL','CFBundleIconFile':'ZGTA-V.icns',
            'CFBundleShortVersionString':'2.0','CFBundleVersion':'109.1','LSMinimumSystemVersion':'13.0',
            'NSHighResolutionCapable':True,'NSLocalNetworkUsageDescription':'Find and join your private ZGTA V lobbies.',
            'NSPrincipalClass':'NSApplication'}
    (contents/'Info.plist').write_bytes(plistlib.dumps(info))
    for arch in ['x86_64','arm64']:
        run('xcrun','swiftc','-O','-module-cache-path',output/'ModuleCache','-target',arch+'-apple-macos13.0','-framework','AppKit',HERE/'ZGTAMac.swift','-o',output/('launcher-'+arch))
    run('xcrun','lipo','-create',output/'launcher-x86_64',output/'launcher-arm64','-output',contents/'MacOS/ZGTA-V')
    (contents/'MacOS/ZGTA-V').chmod(0o755)
    # Seal only new bundled native binaries; the authenticated browser payload stays byte-identical.
    for file in sorted(runtimes.rglob('*')):
        if file.is_file() and not file.is_symlink():
            with file.open('rb') as stream: magic=stream.read(4)
            if magic in [bytes.fromhex(v) for v in ('cffaedfe','feedfacf','cafebabe','bebafeca')]:
                run('codesign','--force','--sign','-',file)
    run('codesign','--force','--sign','-',app)
    run('codesign','--verify','--deep','--strict',app)
    verify_package(resources/'Payload')
    run(contents/'MacOS/ZGTA-V','--verify-payload')
    (volume/'Applications').symlink_to('/Applications',target_is_directory=True)
    (volume/'Install ZGTA V.txt').write_text('Drag ZGTA V.app to Applications, then open it from Applications.\n\nThis private candidate includes its own Python runtime for Intel and Apple Silicon Macs. Chrome and your own prepared game files are still required. Choose the existing game folder on first launch; it is not copied into the app. Keep the app open while playing or hosting. Quit ZGTA V to stop only the helper it started. Existing saves, mods and settings remain outside the app.\n\nAn older launcher is never silently replaced while running. If another version is active, quit it and open this app again.\n\nPrivate test candidate: ad-hoc signed, not Apple Developer ID signed or notarized. No Gatekeeper setting is changed. Public distribution remains gated on owner testing and approval.\n')
    dmg=output/'ZGTA-V-Build109.1-Mac.dmg'
    run('hdiutil','create','-volname','ZGTA V','-srcfolder',volume,'-format','UDZO','-ov',dmg)
    run('hdiutil','verify',dmg)
    receipt={'format':'zgta-mac-dmg-v1','app_build':'109.1','game_payload_build':109,'wrapper_source_revision':revision,
             'game_payload_source_revision':manifest['source_revision'],'payload_manifest_sha256':sha256(payload/'portable-manifest.json'),
             'architectures':['x86_64','arm64'],'runtimes':provenance,'file':dmg.name,'bytes':dmg.stat().st_size,'sha256':sha256(dmg),
             'signature':'AD_HOC_STRICT_DEEP_PASS','notarized':False,'public_promotion_approved':False,
             'physical_gameplay':'PENDING_OWNER','apple_silicon_execution':'NOT_TESTED','intel_runtime_payload_verification':'PASS'}
    (output/'mac-dmg-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--payload',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--cache',type=Path,required=True)
    a=p.parse_args();build(a.payload.resolve(strict=True),a.output.absolute(),a.cache.absolute())
