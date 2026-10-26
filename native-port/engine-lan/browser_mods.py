"""Private, data-only Legacy DLC imports and immutable browser launch overlays.

No code is loaded from an import. Mirrors, source archives and existing launches
are never edited. Format handling follows App/RPFArchive.swift/ModRuntime.swift.
"""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import threading
from types import MappingProxyType
import xml.etree.ElementTree as ET
import zipfile
import zlib

MAX_ARCHIVE = 128 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
MAX_IMPORT = MAX_TOTAL
MAX_METADATA = 8 * 1024 * 1024
MAX_PACKS = 16
CODE = {'.asi', '.dll', '.exe', '.dylib', '.so', '.lua', '.cs', '.js', '.wasm', '.sh', '.py', '.ysc', '.scc'}
NAME = re.compile(r'^[a-z0-9_]{1,63}$')


class ModError(ValueError):
    pass


def _json(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':')).encode()


def _path(name):
    if (not isinstance(name, str) or not name or '\\' in name or '\x00' in name
            or any(ord(c) < 32 for c in name) or name.startswith('/')
            or ':' in name or any(p in ('', '.', '..') for p in name.split('/'))):
        raise ModError('Unsafe archive path.')
    return name.lower()


def _xml(data):
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ModError('DLC XML must use UTF-8 encoding.') from exc
    if len(data) > MAX_METADATA or '\x00' in text or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ModError('XML entities, document types or oversized metadata are unsupported.')
    try:
        return ET.fromstring(text)
    except ET.ParseError as exc:
        raise ModError('Invalid DLC XML metadata.') from exc


class RPF:
    def __init__(self, data):
        self.data = data
        self.entries = {}
        def word(at):
            if at < 0 or at + 4 > len(data):
                raise ModError('Truncated RPF table.')
            return struct.unpack_from('<I', data, at)[0]
        if word(0) != 0x52504637:
            raise ModError('Only GTA V Legacy RPF7 DLC archives are supported.')
        count, names_size = word(4), word(8)
        names_start = 16 + count * 16
        table_end = names_start + names_size
        if not 0 < count <= 100000 or not 0 < names_size <= MAX_METADATA or table_end > len(data):
            raise ModError('Invalid RPF table bounds.')
        if word(12) != 0x4e45504f:
            raise ModError('Encrypted RPF tables are unsupported; import an open Legacy DLC pack.')
        visited, spans = set(), []
        def name(offset):
            if offset >= names_size:
                raise ModError('Invalid RPF name offset.')
            end = data.find(b'\0', names_start + offset, table_end)
            if end < 0 or end - names_start - offset > 255:
                raise ModError('Invalid RPF filename.')
            try:
                value = data[names_start + offset:end].decode('utf-8').lower()
            except UnicodeDecodeError as exc:
                raise ModError('Invalid RPF filename encoding.') from exc
            if value and (_path(value) != value or '/' in value):
                raise ModError('Invalid RPF filename.')
            return value
        def walk(index, parent, depth):
            if depth >= 32 or index >= count or index in visited:
                raise ModError('Cyclic or invalid RPF directory table.')
            visited.add(index)
            first, second, third, fourth = struct.unpack_from('<4I', data, 16 + 16 * index)
            directory = second == 0x7fffff00
            label = name(first if directory else first & 0xffff)
            if index != 0 and not label:
                raise ModError('Missing RPF filename.')
            path = parent + '/' + label if parent else label
            if directory:
                if third > count or fourth > count - third:
                    raise ModError('RPF directory exceeds the table.')
                for child in range(third, third + fourth):
                    walk(child, path, depth + 1)
            else:
                _path(path)
                if PurePosixPath(path).suffix in CODE:
                    raise ModError('Executable and script mod plugins are unsupported.')
                resource = bool(second & 0x80000000)
                packed = first | second << 32
                size = packed >> 16 & 0xffffff
                compressed = size != 0
                offset = (packed >> 40 & (0x7fffff if resource else 0xffffff)) * 512
                if resource and size == 0xffffff:
                    if offset + 16 > len(data):
                        raise ModError('Truncated RPF resource.')
                    size = data[offset + 7] | data[offset + 14] << 8 | data[offset + 5] << 16 | data[offset + 2] << 24
                if not resource and size == 0:
                    size = third
                if offset < table_end or offset > len(data) or size > len(data) - offset:
                    raise ModError('RPF file data exceeds archive bounds.')
                if path in self.entries:
                    raise ModError('Duplicate RPF filename.')
                if not resource and fourth != 0:
                    raise ModError('Encrypted RPF file entries are unsupported.')
                version = ((third >> 28) << 4 | fourth >> 28) if resource else None
                expected = {'.yft': 162, '.ytd': 13, '.ydd': 165}.get(PurePosixPath(path).suffix)
                if expected is not None and version != expected:
                    raise ModError('Enhanced resources are unsupported; use a Legacy DLC pack.')
                self.entries[path] = (offset, size, third, compressed, version)
                if size:
                    spans.append((offset, offset + size))
        walk(0, '', 0)
        if len(visited) != count:
            raise ModError('RPF contains unreachable entries.')
        spans.sort()
        if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
            raise ModError('Overlapping RPF file data is unsupported.')

    def metadata(self, path):
        if path not in self.entries:
            raise ModError('DLC is missing ' + path + '.')
        offset, size, unpacked, compressed, version = self.entries[path]
        if version is not None or not 0 < unpacked <= MAX_METADATA:
            raise ModError('Invalid or oversized DLC XML metadata.')
        data = self.data[offset:offset + size]
        if compressed:
            try:
                decoder = zlib.decompressobj(-15)
                result = decoder.decompress(data, unpacked + 1)
                if len(result) != unpacked or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                    raise ModError('Invalid compressed DLC metadata size.')
                return result
            except zlib.error as exc:
                raise ModError('Invalid compressed DLC metadata.') from exc
        if len(data) != unpacked:
            raise ModError('Invalid DLC metadata size.')
        return data


def parse_pack(data):
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_ARCHIVE:
        raise ModError('DLC pack exceeds the 128 MiB import limit or is empty.')
    archive = RPF(data)
    setup = archive.metadata('setup2.xml')
    content = archive.metadata('content.xml')
    metadata_bytes = len(setup) + len(content)
    root = _xml(setup)
    _xml(content)
    devices = [e.text.strip().lower() for e in root.iter() if e.tag == 'deviceName' and e.text]
    if len(devices) != 1 or not devices[0].startswith('dlc_') or not NAME.fullmatch(devices[0][4:]):
        raise ModError('DLC needs exactly one valid dlc_ deviceName.')
    models, vehicles = set(), set()
    for path in archive.entries:
        if path.endswith(('vehicles.meta', 'peds.meta')):
            metadata = archive.metadata(path)
            metadata_bytes += len(metadata)
            if metadata_bytes > 16 * 1024 * 1024:
                raise ModError('DLC metadata exceeds the 16 MiB decoded total limit.')
            xml = _xml(metadata)
            tags = ('modelName',) if path.endswith('vehicles.meta') else ('ModelName', 'Name')
            for item in xml.iter():
                if item.tag in tags and item.text:
                    model = item.text.strip().lower()
                    if not NAME.fullmatch(model):
                        raise ModError('Invalid DLC model name.')
                    models.add(model)
                    if path.endswith('vehicles.meta'):
                        vehicles.add(model)
        if path.endswith('.rpf'):
            offset, size, _, compressed, version = archive.entries[path]
            if compressed or version is not None:
                raise ModError('Compressed or resource-type nested RPF archives are unsupported.')
            nested = RPF(data[offset:offset + size])
            for resource, entry in nested.entries.items():
                if resource.endswith('.rpf'):
                    raise ModError('Deeply nested DLC archives are unsupported.')
                suffix = PurePosixPath(resource).suffix
                expected = {'.yft': 162, '.ytd': 13, '.ydd': 165}.get(suffix)
                if expected is not None:
                    if entry[4] != expected:
                        raise ModError('Enhanced resources are unsupported; use a Legacy DLC pack.')
                    model = PurePosixPath(resource).stem
                    if NAME.fullmatch(model) and not model.endswith('_hi'):
                        models.add(model)
    if not models:
        raise ModError('DLC has no supported vehicle or character models.')
    return {'name': devices[0][4:], 'models': sorted(models), 'vehicleModels': sorted(vehicles),
            'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data),
            'setup': setup, 'content': content, '_data': data}


class Snapshot:
    def __init__(self, manifest, overrides, catalog):
        self.manifest_bytes = _json(manifest)
        self.version = str(manifest['version'])
        self.fingerprint = self.version[len('zema-mods-'):]
        self.catalog = catalog
        self._overrides = MappingProxyType(dict(overrides))

    def resolve(self, path):
        return self._overrides.get(_path(path))


class BrowserMods:
    """Call only with a newly approved private folder beneath the task Build root."""
    def __init__(self, root):
        self.root = Path(root).absolute()
        self._lock = threading.RLock()
        for path in reversed((self.root.parent,) + tuple(self.root.parents)):
            if path.exists() and (path.is_symlink() or getattr(path, 'is_junction', lambda: False)()):
                raise ModError('Mod storage may not contain symlink path components.')
        new = not self.root.exists()
        if new:
            self.root.mkdir(mode=0o700)
        if os.name == "nt":
            from portable_security import windows_private
            windows_private(self.root, new=new)
        info = self.root.lstat()
        if not stat.S_ISDIR(info.st_mode) or (os.name != 'nt' and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700)):
            raise ModError('Mod storage must be an owned private 0700 directory.')
        self._state = []
        state_file = self.root / 'catalog.json'
        if state_file.exists() or state_file.is_symlink():
            try:
                state = json.loads(self._read('catalog.json', MAX_METADATA))
                if not isinstance(state, list) or len(state) > MAX_PACKS:
                    raise ValueError()
                seen = set()
                for record in state:
                    if (set(record) != {'id', 'name', 'enabled', 'filename'} or not isinstance(record['enabled'], bool)
                            or not re.fullmatch('[a-f0-9]{64}', record['id']) or record['id'] in seen
                            or not isinstance(record['filename'], str) or len(record['filename']) > 255):
                        raise ValueError()
                    pack = parse_pack(self._read(record['id'] + '.rpf', MAX_ARCHIVE))
                    if pack['sha256'] != record['id'] or pack['name'] != record['name']:
                        raise ValueError()
                    seen.add(record['id'])
                self._state = state
            except (ValueError, KeyError, TypeError, OSError) as exc:
                raise ModError('Mod catalog is invalid; existing data was preserved.') from exc

    def _read(self, name, limit):
        fd = os.open(self.root / name, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or (os.name != 'nt' and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600)) or info.st_size > limit or (self.root / name).is_symlink() or getattr(self.root / name, 'is_junction', lambda: False)():
                raise ModError('Unsafe or oversized private mod data.')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                data = stream.read(limit + 1)
            if len(data) > limit:
                raise ModError('Private mod data exceeds its size limit.')
            return data
        finally:
            os.close(fd)

    def _write(self, name, data):
        temporary = '.pending-' + os.urandom(12).hex()
        fd = os.open(self.root / temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(self.root / temporary, self.root / name)
            # Windows does not expose directory fsync through the CRT. The file
            # is flushed before atomic replace; POSIX retains its durability check.
            if os.name != 'nt':
                directory = os.open(self.root, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            try:
                (self.root / temporary).unlink()
            except FileNotFoundError:
                pass

    def _packs(self):
        result = []
        for record in self._state:
            pack = parse_pack(self._read(record['id'] + '.rpf', MAX_ARCHIVE))
            if pack['sha256'] != record['id'] or pack['name'] != record['name']:
                raise ModError('Imported archive changed unexpectedly; existing data was preserved.')
            result.append((record, pack))
        return result

    def _commit_state(self, state):
        """Keep memory consistent even if a directory fsync fails after replace."""
        data = _json(state)
        try:
            self._write('catalog.json', data)
        except OSError:
            try:
                if self._read('catalog.json', MAX_METADATA) == data:
                    # Replacement committed, but durability is uncertain. Preserve
                    # referenced archives rather than deleting valid catalog data.
                    self._state = state
            except (OSError, ModError):
                pass
            raise
        self._state = state

    def _rollback_import(self, written):
        """Remove only bytes this failed operation created, never older imports."""
        failed = False
        for name, digest in written:
            try:
                data = self._read(name, MAX_ARCHIVE)
                if hashlib.sha256(data).hexdigest() != digest:
                    failed = True
                    continue
                (self.root / name).unlink()
            except FileNotFoundError:
                pass
            except (OSError, ModError):
                failed = True
        return not failed

    def catalog(self):
        with self._lock:
            return {'packs': [dict(record, size=pack['size'], models=pack['models'], vehicleModels=pack['vehicleModels'])
                              for record, pack in self._packs()],
                    'limits': {'packBytes': MAX_ARCHIVE, 'totalBytes': MAX_TOTAL, 'packs': MAX_PACKS},
                    'supported': 'Open GTA V Legacy vehicle/character DLC RPF7 packs, directly or inside ZIP.',
                    'unsupported': 'Encrypted/Enhanced packs, code plugins, loose-file replacements and non-ZIP archives.',
                    'launchNote': 'Changes apply to the next Story or Free Roam launch. LAN uses original assets; cross-device mod parity is unverified.'}

    def import_bytes(self, filename, data):
        with self._lock:
            if not isinstance(data, bytes) or len(data) > MAX_TOTAL or not isinstance(filename, str):
                raise ModError('Import exceeds the 256 MiB upload limit.')
            filename = filename.replace('\\', '/').split('/')[-1]
            if not filename or len(filename) > 255 or any(ord(c) < 32 for c in filename):
                raise ModError('Invalid import filename.')
            candidates = []
            if filename.lower().endswith('.rpf'):
                candidates.append((filename, data))
            elif filename.lower().endswith('.zip'):
                try:
                    with zipfile.ZipFile(io.BytesIO(data)) as archive:
                        infos = archive.infolist()
                        if len(infos) > 128:
                            raise ModError('ZIP has too many entries (maximum 128).')
                        seen, total = set(), 0
                        for entry in infos:
                            path = _path(entry.filename.rstrip('/') if entry.is_dir() else entry.filename)
                            mode = entry.external_attr >> 16
                            if path in seen or entry.flag_bits & 1 or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFDIR, stat.S_IFREG)):
                                raise ModError('ZIP contains duplicate, encrypted, linked or special entries.')
                            seen.add(path)
                            if entry.is_dir():
                                continue
                            total += entry.file_size
                            if total > MAX_TOTAL or entry.file_size > MAX_ARCHIVE or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                                raise ModError('ZIP expands beyond safe limits or uses unsupported compression.')
                            suffix = PurePosixPath(path).suffix
                            if suffix == '.rpf':
                                candidates.append((PurePosixPath(path).name, archive.read(entry)))
                            elif suffix not in ('.txt', '.md', '.pdf'):
                                raise ModError('ZIP must contain DLC RPF packs and documentation only; code/loose files are unsupported.')
                except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
                    raise ModError('Invalid or unsupported ZIP archive.') from exc
            else:
                raise ModError('Choose an open Legacy DLC .rpf or .zip containing DLC packs.')
            if not candidates:
                raise ModError('No DLC RPF packs were found.')
            existing = self._packs()
            names = {p['name'] for _, p in existing}
            models = {m for _, p in existing for m in p['models']}
            total = sum(p['size'] for _, p in existing)
            prepared = []
            for label, blob in candidates:
                pack = parse_pack(blob)
                if pack['name'] in names or not models.isdisjoint(pack['models']):
                    raise ModError('Duplicate DLC name or model conflicts with an imported pack.')
                names.add(pack['name']); models.update(pack['models']); total += len(blob)
                prepared.append((label, blob, pack))
            if len(existing) + len(prepared) > MAX_PACKS or total > MAX_TOTAL:
                raise ModError('Private mod storage limit reached (16 packs / 256 MiB).')
            state = list(self._state)
            written = []
            try:
                for label, blob, pack in prepared:
                    name = pack['sha256'] + '.rpf'
                    target = self.root / name
                    if target.exists() or target.is_symlink():
                        if self._read(name, MAX_ARCHIVE) != blob:
                            raise ModError('Existing private import differs; it was preserved.')
                    else:
                        written.append((name, pack['sha256']))
                        self._write(name, blob)
                    state.append({'id': pack['sha256'], 'name': pack['name'], 'filename': label, 'enabled': True})
                self._commit_state(state)
            except (OSError, ModError) as exc:
                if self._state is not state and not self._rollback_import(written):
                    raise ModError('Import failed. Prior catalog is preserved; private incomplete files need cleanup.') from exc
                raise
            return self.catalog()

    def set_enabled(self, identifier, enabled):
        with self._lock:
            if not isinstance(enabled, bool):
                raise ModError('enabled must be a boolean.')
            if identifier not in {r['id'] for r in self._state}:
                raise ModError('Unknown mod pack.')
            state = [dict(r, enabled=enabled) if r['id'] == identifier else dict(r) for r in self._state]
            self._commit_state(state)
            return self.catalog()

    def remove(self, identifier):
        with self._lock:
            if identifier not in {r['id'] for r in self._state}:
                raise ModError('Unknown mod pack.')
            state = [dict(r) for r in self._state if r['id'] != identifier]
            self._commit_state(state)
            # Running snapshots own bytes, so removing this private import cannot
            # mutate them and does not accumulate abandoned large archive copies.
            try:
                (self.root / (identifier + '.rpf')).unlink()
            except OSError as exc:
                raise ModError('Pack is removed from the catalog, but private archive cleanup failed; existing launches are unchanged.') from exc
            return self.catalog()

    def snapshot(self, mode, base_manifest_bytes, dlc_list_bytes):
        if mode not in ('story', 'sandbox', 'lan', 'multiplayer'):
            raise ModError('Unknown launch mode.')
        with self._lock:
            if mode in ('lan', 'multiplayer') and any(record['enabled'] for record in self._state):
                raise ModError('Browser DLC mods are available only in Story and Free Roam. LAN asset parity is unverified.')
            try:
                manifest = json.loads(base_manifest_bytes)
                files = manifest['files']
                if not isinstance(files, list) or any(not isinstance(r, list) or len(r) < 2 or not isinstance(r[0], str)
                    or type(r[1]) is not int or not 0 <= r[1] <= 9007199254740991 for r in files):
                    raise ValueError()
                normalized = [_path(r[0]) for r in files]
                if len(set(normalized)) != len(files):
                    raise ValueError()
                xml = dlc_list_bytes.decode('utf-8')
                _xml(dlc_list_bytes)
                close = re.search(r'</Paths\s*>', xml, re.I)
                if not close:
                    raise ValueError()
            except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
                raise ModError('Invalid original manifest or DLC list; no overlay was created.') from exc
            overrides, selected = {}, []
            def add(path, blob):
                key = _path(path)
                if key in normalized:
                    index = normalized.index(key)
                    files[index][1] = len(blob)
                else:
                    files.append([path, len(blob), 0]); normalized.append(key)
                overrides[key] = blob
            for record, pack in self._packs():
                if not record['enabled']:
                    continue
                prefix = 'x64/dlcPacks/' + pack['name'] + '/'
                add(prefix + 'dlc.rpf', pack['_data'])
                add(prefix + 'setup2.xml', pack['setup'])
                add(prefix + 'content.xml', pack['content'])
                path = 'platform:\\dlcPacks\\' + pack['name'] + '\\'
                if path.lower() not in xml.lower():
                    xml = re.sub(r'</Paths\s*>', lambda match: '\t<Item>' + path + '</Item>\n' + match.group(), xml, count=1, flags=re.I)
                selected.append({'id': record['id'], 'name': pack['name'], 'models': pack['models'], 'vehicleModels': pack['vehicleModels']})
            if selected:
                add('common/data/dlcList.xml', xml.encode())
            digest = hashlib.sha256(base_manifest_bytes + dlc_list_bytes + _json([mode, selected])).hexdigest()
            manifest['version'] = 'zema-mods-' + digest
            return Snapshot(manifest, overrides, selected)
