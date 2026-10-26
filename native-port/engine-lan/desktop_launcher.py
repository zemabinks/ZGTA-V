"""Install an owned desktop entry and a verified, per-user launcher copy.

No login item/service, game data, browser profile or existing unrelated shortcut
is changed. Mac uses Terminal so the server has a visible, stoppable lifetime.
"""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile

BUNDLE_ID = 'com.zemabinks.zgtav.desktop'
DESCRIPTION = 'ZGTA V browser launcher'
ASSETS = Path('native-port/engine-lan/desktop-assets')


def private_folder(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('A launcher installation folder is a symbolic link.')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == 'nt':
        from portable_security import windows_private
        windows_private(path)
    elif path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise ValueError('Launcher installation requires an owned private folder.')
    return path


def installed_copy(package, data, manifest):
    from portable_launcher import verify_package
    package = Path(package).resolve(strict=True)
    raw = (package / 'portable-manifest.json').read_bytes()
    if json.loads(raw) != manifest:
        raise ValueError('Package manifest changed before desktop installation.')
    root = private_folder(Path(data) / 'desktop-launchers')
    target = root / hashlib.sha256(raw).hexdigest()[:24]
    if target.exists() or target.is_symlink():
        if target.is_symlink() or (target / 'portable-manifest.json').read_bytes() != raw:
            raise ValueError('An existing launcher copy differs; it was preserved.')
        verify_package(target)
        return target
    stage = Path(tempfile.mkdtemp(prefix='.install-', dir=root))
    try:
        # Only manifest members, never an adjacent Game folder or user saves.
        for name in manifest['files']:
            source = package / name
            dest = stage / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
        (stage / 'portable-manifest.json').write_bytes(raw)
        verify_package(stage)
        stage.rename(target)
    finally:
        if stage.exists():
            shutil.rmtree(stage)  # Only our uncommitted temporary copy.
    return target


def atomic_bytes(path, data, mode=0o644):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('A desktop launcher member is a symbolic link.')
    temp = path.with_name('.' + path.name + '-' + secrets.token_hex(8))
    try:
        fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def mac_entry(installed, data, manifest, desktop=None):
    desktop = Path(desktop) if desktop is not None else Path.home() / 'Desktop'
    if not desktop.is_dir():
        raise ValueError('The Desktop folder is unavailable.')
    target = desktop / 'ZGTA V.app'
    info = {
        'CFBundleIdentifier': BUNDLE_ID, 'CFBundleName': 'ZGTA V',
        'CFBundleDisplayName': 'ZGTA V', 'CFBundlePackageType': 'APPL',
        'CFBundleExecutable': 'ZGTA-V', 'CFBundleIconFile': 'ZGTA-V.icns',
        'CFBundleVersion': str(manifest['build']),
        'CFBundleShortVersionString': '2.0', 'LSMinimumSystemVersion': '10.15',
        'LSUIElement': True, 'ZGTAOwnedLauncher': True,
    }
    contents = target / 'Contents'
    script = ('#!/bin/sh\nexec /usr/bin/open -a Terminal ' +
              shlex.quote(str(installed / 'Start ZGTA V.command')) + '\n').encode()
    icon = (installed / ASSETS / 'zgta-v.icns').read_bytes()
    wanted = {'Info.plist': plistlib.dumps(info), 'MacOS/ZGTA-V': script,
              'Resources/ZGTA-V.icns': icon}
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_dir():
            raise ValueError('Desktop ZGTA V.app already exists and was preserved.')
        try:
            prior = plistlib.loads((contents / 'Info.plist').read_bytes())
        except (OSError, ValueError):
            raise ValueError('Desktop ZGTA V.app is not our launcher; it was preserved.')
        if prior.get('CFBundleIdentifier') != BUNDLE_ID or prior.get('ZGTAOwnedLauncher') is not True:
            raise ValueError('Desktop ZGTA V.app is not our launcher; it was preserved.')
        # Reject redirected members before updating or backing up an owned entry.
        for path in target.rglob('*'):
            if path.is_symlink():
                raise ValueError('Desktop launcher contains a symbolic link; it was preserved.')
        if all((contents / name).is_file() and (contents / name).read_bytes() == raw
               for name, raw in wanted.items()) and (contents / 'MacOS/ZGTA-V').stat().st_mode & 0o111:
            return target
        backup = private_folder(Path(data) / 'desktop-backups') / ('ZGTA-V-' + secrets.token_hex(8) + '.app')
        shutil.copytree(target, backup)
        # Install executable last: it switches to the already verified new copy.
        for name in ['Info.plist', 'Resources/ZGTA-V.icns', 'MacOS/ZGTA-V']:
            atomic_bytes(contents / name, wanted[name], 0o755 if name.startswith('MacOS/') else 0o644)
    else:
        stage = Path(tempfile.mkdtemp(prefix='.ZGTA-V-', dir=desktop))
        try:
            for name, raw in wanted.items():
                dest = stage / 'Contents' / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(raw)
                dest.chmod(0o755 if name.startswith('MacOS/') else 0o644)
            stage.rename(target)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    return target


# Literal script; all paths arrive as environment values, never interpolated code.
WINDOWS_SHORTCUT = r'''$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8
$w=New-Object -ComObject WScript.Shell
$desktop=if($env:ZGTA_DESKTOP){$env:ZGTA_DESKTOP}else{$w.SpecialFolders.Item('Desktop')}
if(-not (Test-Path -LiteralPath $desktop -PathType Container)){throw 'Desktop folder unavailable'}
$target=Join-Path $desktop 'ZGTA V.lnk'
if(Test-Path -LiteralPath $target){
  $old=$w.CreateShortcut($target)
  $base=[IO.Path]::GetFullPath($env:ZGTA_INSTALL_ROOT)+[IO.Path]::DirectorySeparatorChar
  if($old.Description -ne 'ZGTA V browser launcher' -or -not $old.TargetPath.StartsWith($base,[StringComparison]::OrdinalIgnoreCase)){
    throw 'Desktop ZGTA V.lnk already exists and was preserved'
  }
  if($old.TargetPath -eq $env:ZGTA_START -and $old.IconLocation -eq ($env:ZGTA_ICON+',0')){
    @{path=$target}|ConvertTo-Json -Compress;exit 0
  }
  Copy-Item -LiteralPath $target -Destination $env:ZGTA_LINK_BACKUP
}
$temp=Join-Path $desktop ('.ZGTA-V-'+[Guid]::NewGuid().ToString('N')+'.lnk')
try{
  $s=$w.CreateShortcut($temp)
  $s.TargetPath=$env:ZGTA_START
  $s.WorkingDirectory=$env:ZGTA_WORKING
  $s.IconLocation=$env:ZGTA_ICON+',0'
  $s.Description='ZGTA V browser launcher'
  $s.WindowStyle=1
  $s.Save()
  Move-Item -LiteralPath $temp -Destination $target -Force
}finally{if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp}}
@{path=$target}|ConvertTo-Json -Compress
'''


def windows_entry(installed, data, desktop=None):
    backup = private_folder(Path(data) / 'desktop-backups') / ('ZGTA-V-' + secrets.token_hex(8) + '.lnk')
    env = dict(os.environ, ZGTA_START=str(installed / 'Start ZGTA V.cmd'),
               ZGTA_WORKING=str(installed), ZGTA_ICON=str(installed / ASSETS / 'zgta-v.ico'),
               ZGTA_INSTALL_ROOT=str(installed.parent), ZGTA_LINK_BACKUP=str(backup),
               ZGTA_DESKTOP=str(desktop) if desktop is not None else '')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', WINDOWS_SHORTCUT],
                            env=env, capture_output=True, check=True, timeout=20)
    if len(result.stdout) > 16384:
        raise ValueError('Unexpected desktop shortcut response.')
    return Path(json.loads(result.stdout.decode('utf-8-sig'))['path'])


def install(package, data, manifest, system=None, desktop=None):
    system = sys.platform if system is None else system
    if system not in ('darwin', 'win32'):
        return None
    private_folder(data)
    installed = installed_copy(package, data, manifest)
    if system == 'darwin':
        return mac_entry(installed, data, manifest, desktop)
    return windows_entry(installed, data, desktop)
