"""Public bundle permissions, including the root omitted by TrollStore's walk.

The private package/output directory stays private. Only the Payload tree is
made readable/traversable by iOS. Archive repair preserves every member byte,
including the executable, entitlements and code signature.
"""
import copy
import hashlib
from pathlib import Path, PurePosixPath
import plistlib
import stat
import zipfile

MACHO = {b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf',
         b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xce',
         b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca'}


def file_mode(prefix, old_mode):
    return 0o755 if prefix in MACHO or old_mode & 0o111 else 0o644


def normalize_bundle(app):
    """Call on a new package copy, never on an original build or user folder."""
    app = Path(app)
    entries = [app, *app.rglob('*')]
    # Validate the complete tree before changing any permissions.
    for path in entries:
        mode = path.lstat().st_mode
        if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise ValueError('Bundle contains a symlink or special file: ' + str(path))
    for path in entries:
        if path.is_dir():
            path.chmod(0o755)
        else:
            with path.open('rb') as source:
                prefix = source.read(4)
            path.chmod(file_mode(prefix, path.stat().st_mode))


def rewrite_archive(source, destination):
    """Repair ZIP permissions without extracting, executing or changing bytes."""
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise ValueError('Preserve existing IPA outputs')
    with zipfile.ZipFile(source) as old:
        entries = old.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)) or old.testzip() is not None:
            raise ValueError('Invalid CRC or duplicate archive members')
        roots = set()
        for entry in entries:
            name = entry.filename
            parts = PurePosixPath(name).parts
            if ('\\' in name or '\x00' in name or not parts
                    or name.startswith('/') or '..' in parts
                    or str(PurePosixPath(name)) != name.rstrip('/')
                    or parts[0] != 'Payload'):
                raise ValueError('Unexpected archive member: ' + name)
            if len(parts) > 1:
                roots.add(parts[1])
            kind = stat.S_IFMT(entry.external_attr >> 16)
            if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError('Symlink or special archive member: ' + name)
            if kind == stat.S_IFDIR and not entry.is_dir():
                raise ValueError('Inconsistent directory entry: ' + name)
        if len(roots) != 1 or not next(iter(roots)).endswith('.app'):
            raise ValueError('Expected one Payload app')
        app = 'Payload/' + next(iter(roots)) + '/'
        if app not in names or 'Payload/' not in names:
            raise ValueError('Explicit Payload and app root entries required')
        info = plistlib.loads(old.read(app + 'Info.plist'))
        executable = info['CFBundleExecutable']
        if not executable or '/' in executable or '\\' in executable:
            raise ValueError('Invalid bundle executable name')
        if app + executable not in names:
            raise ValueError('Missing bundle executable')
        changed = []
        digests = {}
        with destination.open('xb') as output, zipfile.ZipFile(output, 'w') as new:
            new.comment = old.comment
            for entry in entries:
                clone = copy.copy(entry)
                mode = entry.external_attr >> 16
                with old.open(entry) as content:
                    prefix = content.read(4)
                    permissions = 0o755 if entry.is_dir() else file_mode(prefix, mode)
                    if entry.filename == app + executable:
                        permissions = 0o755
                    kind = stat.S_IFDIR if entry.is_dir() else stat.S_IFREG
                    clone.create_system = 3
                    clone.external_attr = ((kind | permissions) << 16) | (0x10 if entry.is_dir() else 0)
                    if stat.S_IMODE(mode) != permissions:
                        changed.append({'path': entry.filename, 'before': oct(stat.S_IMODE(mode)),
                                        'after': oct(permissions)})
                    digest = hashlib.sha256(prefix)
                    with new.open(clone, 'w') as target:
                        target.write(prefix)
                        while chunk := content.read(1024 * 1024):
                            target.write(chunk)
                            digest.update(chunk)
                    digests[entry.filename] = digest.hexdigest()
        with zipfile.ZipFile(destination) as new:
            if new.namelist() != names or new.testzip() is not None:
                raise ValueError('Repaired archive integrity failed')
            for name, expected in digests.items():
                digest = hashlib.sha256()
                with new.open(name) as content:
                    while chunk := content.read(1024 * 1024):
                        digest.update(chunk)
                if digest.hexdigest() != expected:
                    raise ValueError('Archive member bytes changed: ' + name)
    return {'bundle_identifier': info['CFBundleIdentifier'], 'build': info['CFBundleVersion'],
            'app_path': app.rstrip('/'), 'members_byte_identical': len(digests),
            'changed_permissions': changed, 'archive': 'CRC_PASS'}
