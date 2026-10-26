#!/usr/bin/env python3
"""Start the portable launcher without installing services or copying game data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import threading
import urllib.request
import webbrowser

if sys.version_info < (3,9):raise SystemExit('ZGTA V browser host requires Python 3.9 or newer.')

HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parents[1]
URL='http://127.0.0.1:18887/'
PORT=18887


def verify_package(root):
    manifest=json.loads((root/'portable-manifest.json').read_text())
    if manifest.get('format')!='zgta-portable-v1' or not isinstance(manifest.get('files'),dict):raise ValueError('Invalid launcher manifest.')
    for name,want in manifest['files'].items():
        if not isinstance(name,str) or '\\' in name or name.startswith('/') or any(v in ('','..','.') for v in name.split('/')):raise ValueError('Invalid package path.')
        if not isinstance(want,str) or not re.fullmatch('[0-9a-f]{64}',want):raise ValueError('Invalid package hash.')
        path=root/name
        if not path.is_file() or path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent!=root and root in parent.parents) or not path.resolve().is_relative_to(root.resolve()):raise ValueError('Incomplete package. Extract the entire ZIP first.')
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
        if digest.hexdigest()!=want:raise ValueError('Launcher files changed: '+name)
    for folder in ('native-port/engine-lan','Runtime','Python'):
        base=root/folder
        if base.is_dir():
            for path in base.rglob('*'):
                if path.is_file() and path.name!='.DS_Store' and path.relative_to(root).as_posix() not in manifest['files']:raise ValueError('Unlisted launcher file: '+path.relative_to(root).as_posix())
    return manifest


def validate_mirror(path):
    from serve_browser import INDEX_SHA, BUILD
    root=Path(path).expanduser().resolve(strict=True)
    if not root.is_dir() or not (root/'data/manifest.json').is_file() or not (root/BUILD.lstrip('/')/'game.wasm').is_file():raise ValueError('Choose the game mirror folder containing index.html, data and b, not an IPA or an empty folder.')
    if hashlib.sha256((root/'index.html').read_bytes()).hexdigest()!=INDEX_SHA:raise ValueError('This mirror uses a different game build. Original files were preserved.')
    return root


def choose_windows_folder():
    script="""$ErrorActionPreference='Stop';[Console]::OutputEncoding=[System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
$d=New-Object System.Windows.Forms.FolderBrowserDialog
$d.Description='Choose your existing ZGTA V game mirror (index.html, data, b)'
$d.ShowNewFolderButton=$false
if($d.ShowDialog() -eq 'OK'){[Console]::Write($d.SelectedPath)}
"""
    result=subprocess.run(['powershell.exe','-NoProfile','-STA','-Command',script],capture_output=True,timeout=600,check=True)
    value=result.stdout.decode('utf-8-sig').strip()
    if not value:raise ValueError('No game folder selected. Nothing was changed.')
    return validate_mirror(value)


def data_directory():
    if PACKAGE.parent.name=='desktop-launchers':return PACKAGE.parent.parent
    if os.name=='nt':return Path(os.environ['LOCALAPPDATA'])/'ZGTA V'
    return Path.home()/'.local/share/ZGTA-V'


def load_mirror(data,explicit=None,choose=False):
    if explicit:return validate_mirror(explicit)
    config=data/'launcher.json'
    if not choose and config.exists():
        try:return validate_mirror(json.loads(config.read_text())['mirror'])
        except (OSError,ValueError,KeyError):print('The previous game folder is unavailable. Choose it again; saves are kept.')
    if os.name=='nt':return choose_windows_folder()
    # Android shared storage is used only for the owner's read-only game files.
    for candidate in [Path.home()/'storage/downloads/ZGTA-V/Game',Path.home()/'storage/downloads/ZGTA-V/playgta5.com']:
        try:return validate_mirror(candidate)
        except (OSError,ValueError):pass
    if 'com.termux' not in os.environ.get('PREFIX',''):
        try:value=input('Paste the full path to your prepared game folder (index.html, data, b): ').strip()
        except EOFError:raise ValueError('No game folder was supplied. Start again with --mirror "/full/path/to/game folder". No game files were changed.')
        if not value:raise ValueError('No game folder selected. Nothing was changed.')
        return validate_mirror(Path(value))
    raise ValueError('Put your own game mirror in Downloads/ZGTA-V/Game (index.html, data and b), then start again. In Termux, run termux-setup-storage once and grant its storage request. No game files are supplied or downloaded.')


def existing_launcher():
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        request=urllib.request.Request(URL+'zema-lab/launcher/status',data=b'{}',headers={'Content-Type':'application/json','X-Zema-Lab':'1'})
        with opener.open(request,timeout=1) as r:raw=r.read(4097)
        return len(raw)<=4096 and json.loads(raw).get('service')=='zgta-browser-launcher'
    except (OSError,ValueError,TypeError):return False


def open_browser():
    if 'com.termux' in os.environ.get('PREFIX',''):
        subprocess.run(['termux-open-url',URL],check=False);return
    if os.name=='nt':
        candidates=[Path(os.environ.get(v,''))/'Google/Chrome/Application/chrome.exe' for v in ('PROGRAMFILES','PROGRAMFILES(X86)','LOCALAPPDATA')]
        for chrome in candidates:
            if chrome.is_file():subprocess.Popen([str(chrome),URL]);return
    if sys.platform=='darwin':
        for applications in [Path('/Applications'),Path.home()/'Applications']:
            chrome=applications/'Google Chrome.app'
            if chrome.is_dir():
                subprocess.Popen(['/usr/bin/open','-a',str(chrome),URL]);return
    webbrowser.open(URL)


def setup_desktop(data,manifest,disabled=False):
    if disabled:return
    try:
        from desktop_launcher import install
        entry=install(PACKAGE,data,manifest)
        if entry:print('Desktop launcher ready: '+str(entry),flush=True)
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        # Optional convenience must not prevent an otherwise valid game launch.
        print('Desktop launcher could not be created: '+str(error)+'\nYou can still use the Start script. Check Desktop access and try again.',file=sys.stderr)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mirror',type=Path);p.add_argument('--choose-folder',action='store_true');p.add_argument('--check',action='store_true');p.add_argument('--no-open',action='store_true');p.add_argument('--no-desktop',action='store_true',help='Skip desktop shortcut installation');p.add_argument('--data',type=Path);a=p.parse_args(argv)
    manifest=verify_package(PACKAGE)
    data=(a.data or data_directory()).absolute();new=not data.exists();data.mkdir(parents=True,exist_ok=True,mode=0o700)
    if os.name=='nt':
        from portable_security import windows_private
        windows_private(data,new=new)
    elif data.stat().st_uid!=os.getuid() or data.stat().st_mode & 0o077:raise ValueError('Use an owned private folder for launcher data.')
    if not a.check and existing_launcher():
        setup_desktop(data,manifest,a.no_desktop)
        print('ZGTA V is already running. Opening its Home screen; no server was restarted.')
        if not a.no_open:open_browser()
        return
    mirror=load_mirror(data,a.mirror,a.choose_folder)
    from serve_browser import Content,Handler,ThreadingHTTPServer
    from browser_mods import BrowserMods
    content=Content(mirror,PACKAGE/'Runtime',BrowserMods(data/'mods'))
    if a.check:
        from browser_lobby_host import addresses
        addresses()  # Include the Home status reader in the packaged-startup check.
        content.lobby_host.close();content.lobby_directory.close()
        print(json.dumps({'package':'HASHES_PASS','mirror':'PINNED_INDEX_PASS','helper_initialization':'PASS','gameplay':'NOT_TESTED'}));return
    try:server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
    except OSError:content.lobby_host.close();content.lobby_directory.close();raise ValueError('Port 18887 is in use. Close the other launcher first; no process was stopped.')
    server.content=content;server.daemon_threads=True
    config=data/'launcher.json';temp=data/('launcher-'+secrets.token_hex(8)+'.new.json');fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump({'mirror':str(mirror)},f)
    os.replace(temp,config)
    setup_desktop(data,manifest,a.no_desktop)
    print('ZGTA V is ready at '+URL+'\nKeep this window open. Closing it stops browser-hosted lobbies. Ctrl+C stops cleanly.',flush=True)
    if not a.no_open:threading.Timer(.5,open_browser).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:content.lobby_host.close();content.lobby_directory.close();server.server_close()

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,subprocess.SubprocessError) as e:print('ZGTA V could not start: '+str(e),file=sys.stderr);sys.exit(1)
