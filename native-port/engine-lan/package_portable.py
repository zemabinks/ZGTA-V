#!/usr/bin/env python3
"""Package existing pinned browser runtime and helpers; never copy game data.

Windows includes an official pinned CPython embeddable runtime. Android uses
an existing Termux Python and is explicitly an experimental starter, not an APK.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parent
SOURCE_ROOT=ROOT.parents[1]
BROWSER_REVISION='109'
PYTHON_URL='https://www.python.org/ftp/python/3.13.16/python-3.13.16-embed-amd64.zip'
PYTHON_SHA='97dae5274cc54867065e8d5a3226e48c35017ed332a0fdb0e27d5b5821961297'


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def checked_runtime(stage):
    """Verify declared runtime inputs before creating a distributable folder."""
    for name in ('engine-lan-module.json','engine-lan-module.js','browser-stage.json'):
        if (stage/name).is_symlink():raise ValueError('Symlinked runtime metadata refused: '+name)
    metadata=json.loads((stage/'engine-lan-module.json').read_text())
    record=json.loads((stage/'browser-stage.json').read_text())
    if metadata.get('format')!='zema-browser-engine-lan-v1' or record.get('format')!='zema-browser-engine-lan-stage-v1':raise ValueError('Expected reviewed browser stage')
    if metadata.get('features',{}).get('format')!='zema-browser-features-v1':raise ValueError('Expected current browser feature stage')
    expected=dict(record['staged_hashes']);expected['game.engine-lan.wasm']=metadata['patched_sha256']
    for name,want in expected.items():
        if not re.fullmatch(r'[a-zA-Z0-9_.-]+',name) or not isinstance(want,str) or not re.fullmatch(r'[0-9a-f]{64}',want):raise ValueError('Invalid runtime hash declaration')
        path=stage/name
        if path.is_symlink() or not path.is_file() or sha256(path)!=want:raise ValueError('Staged browser bytes changed: '+name)
    helper='globalThis.ZemaEngineLanModule='+json.dumps(metadata)+';\n'
    if (stage/'engine-lan-module.js').read_text()!=helper:raise ValueError('Module helper changed')
    return {'stage_manifest_sha256':sha256(stage/'browser-stage.json'),'module_metadata_sha256':sha256(stage/'engine-lan-module.json'),'staged_hashes':expected}


def source_channel(origin):
    """Only reviewed repository identities may become an advertised update URL."""
    for name, channel in [('ZGTA-V-Private-Development', 'private-development'), ('ZGTA-V', 'public')]:
        url='https://github.com/zemabinks/'+name
        if origin in (url, url+'.git', 'git@github.com:zemabinks/'+name+'.git'):
            return {'source_repository':url,'release_channel':channel}
    return {'source_repository':None,'release_channel':'unspecified'}


def build(stage,output,platform,python_archive=None,revision=None,allow_dirty=False):
    if platform not in ('Windows-x64','Android-Termux','Browser-Mac-Linux'):raise ValueError('Unknown platform')
    revision=BROWSER_REVISION if revision is None else str(revision)
    if not re.fullmatch(r'[1-9][0-9]*(?:\.[0-9]+)?',revision):raise ValueError('Invalid release revision')
    output=Path(output).absolute();stage=Path(stage).resolve(strict=True)
    if output.exists() or output.is_symlink():raise ValueError('Use a new package folder')
    runtime_provenance=checked_runtime(stage)
    icons=json.loads((ROOT/'desktop-assets/provenance.json').read_text())
    if icons.get('source_sha256')!=sha256(ROOT.parent/'app/App/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png'):
        raise ValueError('Desktop icons do not match the current iOS icon source')
    for name in ('zgta-v.icns','zgta-v.ico'):
        if icons.get('files',{}).get(name)!=sha256(ROOT/'desktop-assets'/name):raise ValueError('Desktop icon bytes changed: '+name)
    revision_result=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True)
    source_revision=revision_result.stdout.strip()
    origin=subprocess.run(['git','remote','get-url','origin'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    channel=source_channel(origin)
    dirty=subprocess.run(['git','status','--porcelain=v1'],cwd=ROOT,capture_output=True,text=True,check=True)
    if dirty.stdout and not allow_dirty:raise ValueError('Commit the frozen source before release packaging; dirty source is allowed only with --allow-dirty for disposable checks')
    tracked=set(subprocess.run(['git','ls-files','-z'],cwd=SOURCE_ROOT,capture_output=True,check=True).stdout.decode().split('\0'))
    source_files={}
    output.mkdir(mode=0o700,parents=True);package=output/'ZGTA-V';code=package/'native-port/engine-lan';code.mkdir(parents=True)
    def copy_source(source,target):
        rel=source.relative_to(SOURCE_ROOT).as_posix()
        if rel not in tracked or source.is_symlink():raise ValueError('Untracked or symlinked package source refused: '+rel)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        digest=sha256(target)
        if sha256(source)!=digest:raise ValueError('Package source changed while copying: '+rel)
        source_files[target.relative_to(package).as_posix()]={'source':rel,'sha256':digest}
    for rel in sorted(tracked):
        f=SOURCE_ROOT/rel
        if f.parent==ROOT and f.suffix in ('.py','.js','.html','.css'):copy_source(f,code/f.name)
    for name in ('solo-card.png','friends-card.png','desktop-city.png','los-santos-map.jpg','zplay-gta-green.svg','zplay-gta-green-32.png','zplay-gta-green-180.png','favicon.ico'):
        copy_source(ROOT/name,code/name)
    for name in ('zgta-v.icns','zgta-v.ico','provenance.json'):
        copy_source(ROOT/'desktop-assets'/name,code/'desktop-assets'/name)
    # Portable Bonjour is source-only and works with isolated Windows Python.
    # Preserve licenses/provenance and include no host-specific binary modules.
    for rel in sorted(tracked):
        if rel.startswith('native-port/engine-lan/discovery_vendor/'):
            copy_source(SOURCE_ROOT/rel,code/Path(rel).relative_to('native-port/engine-lan'))
    copy_source(ROOT/'engine-safety-pins.json',code/'engine-safety-pins.json')
    copy_source(ROOT/'render-hooks-pins.json',code/'render-hooks-pins.json')
    copy_source(ROOT/'render-lifetime-pins106.json',code/'render-lifetime-pins106.json')
    readers=code/'relay-service';readers.mkdir()
    copy_source(ROOT/'relay-service/service_runner.py',readers/'service_runner.py')
    runtime=package/'Runtime';runtime.mkdir()
    # Copy only the authenticated runtime set. Proof screenshots, drafts and
    # unrelated build outputs in the staging directory are not distributables.
    for name in sorted(set(runtime_provenance['staged_hashes'])|{'engine-lan-module.js','engine-lan-module.json','browser-stage.json'}):
        shutil.copy2(stage/name,runtime/name)
    icon=package/'native-port/app/App/Assets.xcassets/HomeIcon.imageset';icon.mkdir(parents=True)
    copy_source(ROOT.parent/'app/App/Assets.xcassets/HomeIcon.imageset/HomeIcon.png',icon/'HomeIcon.png')
    # The offline-worker adapter imports the pinned ABI reader through
    # browser_wasm. Keep its sibling layout intact in the portable package.
    for name in ('Scripts/inspect_engine_lan.py','Tests/glue5_engine_lan_contract.json'):
        target=package/'native-port/app'/name;target.parent.mkdir(parents=True,exist_ok=True)
        copy_source(ROOT.parent/'app'/name,target)
    # The renderer's exact map-art overlay is shared with iOS. Without this
    # bounded delta the optional loader would silently retain older symbols.
    for name in ('Resources/vehicle-catalog.json', 'Resources/modern-map-icons.json', 'Resources/ModernBlips/README.txt',
                 'Resources/ModernBlips/catalog.json'):
        target=package/'native-port/app'/name;target.parent.mkdir(parents=True,exist_ok=True)
        copy_source(ROOT.parent/'app'/name,target)
    import mod_previews
    for name in ['mod-vehicle-previews.json']+[row['file'] for row in mod_previews.load().values()]:
        source=mod_previews.RESOURCES/name
        copy_source(source,package/'native-port/app/Resources'/name)
    notices=package/'Notices';notices.mkdir()
    for src,name in [(SOURCE_ROOT/'LICENSE','LICENSE-source.txt'),(ROOT.parent/'LICENSE','LICENSE-native-port.txt'),(ROOT/'THIRD_PARTY_NOTICES.md','THIRD_PARTY_NOTICES.md')]:copy_source(src,notices/name)
    if platform=='Windows-x64':
        if python_archive is None:
            python_archive=output/'python-3.13.16-embed-amd64.zip'
            with urllib.request.urlopen(PYTHON_URL,timeout=30) as r:
                data=r.read(16*1024*1024+1)
            if len(data)>16*1024*1024:raise ValueError('Python download exceeds limit')
            python_archive.write_bytes(data)
        python_archive=Path(python_archive)
        if sha256(python_archive)!=PYTHON_SHA:raise ValueError('Official Python archive checksum mismatch')
        target=package/'Python';target.mkdir()
        with zipfile.ZipFile(python_archive) as z:
            for entry in z.infolist():
                if entry.is_dir() or '/' in entry.filename or '\\' in entry.filename or ':' in entry.filename or entry.file_size>20*1024*1024:raise ValueError('Unexpected Python package layout')
                (target/entry.filename).write_bytes(z.read(entry))
        (target/'python313._pth').write_text('python313.zip\n.\n..\n../native-port/engine-lan\n')
        (package/'Start ZGTA V.cmd').write_bytes(b'@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\n"%~dp0Python\\python.exe" -B "%~dp0native-port\\engine-lan\\portable_launcher.py" %*\r\nif errorlevel 1 pause\r\n')
        (package/'Choose game folder.cmd').write_bytes(b'@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\n"%~dp0Python\\python.exe" -B "%~dp0native-port\\engine-lan\\portable_launcher.py" --choose-folder\r\nif errorlevel 1 pause\r\n')
        instructions='''WINDOWS x64 — TEST CANDIDATE
1. Extract the entire ZIP, then double-click Start ZGTA V.cmd.
2. The first time, choose your OWN game mirror folder containing index.html,
   data and b. No game files are included or downloaded by this launcher.
3. Setup creates a ZGTA V desktop shortcut with the iOS app icon. Next time,
   double-click it to start the local host and open Chrome (or your default browser).
   Keep the launcher window open while playing/hosting. Ctrl+C stops it cleanly.
4. Join with a friend's invite, or Host & Play and share your invite.
   On a Windows Firewall prompt, allow only the private network you use.
   No firewall rules are changed by this package. Remote uses a reachable private VPN address. With an existing WireGuard LAN route, use the host LAN address; Tailscale addresses use Remote.
The launcher is copied into your private ZGTA V application-data folder; the
desktop shortcut works independently of the extracted download folder. Your
game folder stays where you selected it. Do not delete or move those game files.
Your game folder is remembered locally. Use Choose game folder.cmd to change it
with the launcher stopped. Browser characters remain in the same Chrome profile
at http://127.0.0.1:18887/. Do not clear browser storage or uninstall Chrome.
Python 3.13.16 is included, pinned to python.org's checksum. No Python install,
admin access, certificate, registry edit, paid build or security bypass is needed.
Windows execution, firewall and gameplay require a physical Windows test.
'''
    elif platform=='Android-Termux':
        (package/'Start-Android.sh').write_text('''#!/data/data/com.termux/files/usr/bin/bash
set -eu
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if ! command -v python >/dev/null 2>&1; then
  printf 'ZGTA V needs Termux Python. Install it from your configured Termux repository now? [y/N] '
  read -r answer
  case "$answer" in y|Y) pkg install python ;; *) exit 1 ;; esac
fi
exec python -B "$HERE/native-port/engine-lan/portable_launcher.py" "$@"
''')
        instructions='''ANDROID / TERMUX — EXPERIMENTAL STARTER, NOT AN APK
An Android phone is still required for validation. The current renderer needs
WebGPU, WebAssembly memory64, shared memory and BC texture compression. Many
Android GPUs will not provide all of them. Check this GPU in Graphics before
Play; an unsupported BC adapter is refused with your data preserved.
1. Install Termux from its official project/F-Droid. Keep any Termux plugins
   from the SAME source. This package does not install Android apps or change
   Android security/battery settings for you.
2. In Termux run termux-setup-storage once and approve its storage prompt.
3. Extract this ZIP into Downloads so this folder is Downloads/ZGTA-V.
4. Put your own compatible mirror in Downloads/ZGTA-V/Game containing index.html,
   data and b. These game files are not supplied or downloaded.
5. In Termux paste: bash ~/storage/downloads/ZGTA-V/Start-Android.sh
   It asks before installing Python if missing, then opens your browser.
   If the browser does not open, visit http://127.0.0.1:18887/ in Chrome.
Keep Termux/Chrome active while playing or hosting. Android can suspend or kill
background apps; unattended hosting is not promised. Join by invite works without
LAN browsing. Automatic LAN discovery is included; Android may restrict multicast
on some devices/networks. Remote requires a usable private VPN route. With WireGuard to a home LAN, use the reachable host LAN address under Same Wi-Fi / LAN; Tailscale addresses use Remote.
A native one-tap Android launcher and physical gameplay certification are open
follow-ups. This starter is useful for compatibility/setup testing; it does not
claim all Android phones can play or host reliably.
Official Termux: https://github.com/termux/termux-app#installation
'''
    else:
        command=package/'Start ZGTA V.command'
        command.write_text('''#!/bin/sh
set -eu
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  printf 'Python 3.9 or newer is required. Install it from python.org or your OS package manager, then try again.\n'
  exit 1
fi
exec python3 -B "$HERE/native-port/engine-lan/portable_launcher.py" "$@"
''')
        command.chmod(0o755)
        instructions='''MAC / LINUX — BROWSER HOST BETA, NOT A NATIVE GAME APP
1. Install Python 3.9 or newer from python.org or your OS package manager if
   missing. Install a current Chrome/Edge browser with the required GPU features.
2. Extract the complete ZIP. In Terminal, change into the extracted ZGTA-V
   folder, then run: sh "Start ZGTA V.command"
3. Paste the full path to your OWN prepared game folder when asked. It must
   contain index.html, data and b. Paths with spaces are accepted as typed;
   do not add quotes around a pasted path. No game files are provided.
4. On Mac, setup creates ZGTA V.app on your Desktop, using the iOS app icon.
   Double-click it next time: it starts the local host in Terminal and opens Chrome
   if installed, otherwise your default browser. Keep Terminal open while playing.
   Linux continues to use this script. Ctrl+C stops your launcher and owned lobby.
   Open http://127.0.0.1:18887/ if the browser does not open automatically.
Mac keeps a private launcher copy, so the desktop app does not depend on the
extracted download folder. Keep your separate game folder in its selected location.
The script installs no service or dependency and changes no OS security setting.
The game folder is remembered. To change it, stop the launcher and run:
  sh "Start ZGTA V.command" --choose-folder
Or supply a folder explicitly:
  sh "Start ZGTA V.command" --mirror "/full/path/to/game folder"
Characters are stored in your browser profile and launcher origin. Do not clear
browser storage; export a backup before changing browser/profile or address.
This package's host initialization and HTTP routes were checked on macOS;
Linux execution and game/GPU/controller behavior still need community tests.
'''
    if channel['release_channel']=='private-development':
        updates='Private development candidate; owner gameplay acceptance is still pending.\nSource and candidate updates: '+channel['source_repository']
    elif channel['source_repository']:
        updates='Source and updates: '+channel['source_repository']
    else:
        updates='Update channel unspecified; use the source_revision in portable-manifest.json.'
    (package/'START HERE.txt').write_text(instructions+'\n'+updates+'\nPublic worldwide discovery is not enabled. LAN/Tailscale hosts are private.\n')
    files={str(f.relative_to(package)).replace('\\','/'):sha256(f) for f in sorted(package.rglob('*')) if f.is_file()}
    for record in source_files.values():
        if sha256(SOURCE_ROOT/record['source'])!=record['sha256']:raise ValueError('Package source changed during build: '+record['source'])
    final_revision=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    final_dirty=subprocess.run(['git','status','--porcelain=v1'],cwd=ROOT,capture_output=True,text=True,check=True).stdout
    if final_revision!=source_revision or (not allow_dirty and final_dirty):raise ValueError('Frozen source changed during packaging')
    if checked_runtime(runtime)!=runtime_provenance:raise ValueError('Runtime changed while copying')
    manifest={'format':'zgta-portable-v1','build':int(revision.split('.')[0]),'browser_revision':revision,'platform':platform,'source_revision':source_revision,'source_worktree_dirty':bool(dirty.stdout or final_dirty),'source_files':source_files,'runtime_provenance':runtime_provenance,'game_files_included':False,'physical_platform_validation':'PENDING','python_source':PYTHON_URL if platform=='Windows-x64' else ('EXISTING_TERMUX_PYTHON' if platform=='Android-Termux' else 'SYSTEM_PYTHON'),**channel,'python_archive_sha256':PYTHON_SHA if platform=='Windows-x64' else None,'files':files}
    (package/'portable-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    archive=output/('ZGTA-V-Build'+revision+'-'+platform+'.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in sorted(package.rglob('*')):
            if f.is_file():z.write(f,str(f.relative_to(output)))
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise ValueError('Package CRC failure')
    receipt={'platform':platform,'build':revision,'source_revision':source_revision,'source_worktree_dirty':manifest['source_worktree_dirty'],'archive':str(archive),'sha256':sha256(archive),'bytes':archive.stat().st_size,'files':len(files),'game_data_included':False,'archive_crc':'PASS','physical_platform_validation':'PENDING'}
    (output/'package-verification.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--platform',choices=['Windows-x64','Android-Termux','Browser-Mac-Linux'],required=True);p.add_argument('--python-archive',type=Path);p.add_argument('--revision',help='Frozen release number (defaults to current browser revision)');p.add_argument('--allow-dirty',action='store_true',help='Disposable checks only; record unfinished source provenance');a=p.parse_args();print(json.dumps(build(a.stage,a.output,a.platform,a.python_archive,a.revision,a.allow_dirty),indent=2))
