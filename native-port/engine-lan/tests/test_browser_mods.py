"""Synthetic Legacy DLC fixtures only; never touches a game or existing saves."""
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zipfile
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import browser_mods as mods


def rpf(files, compressed=(), resources=None):
    resources = resources or {}
    count = len(files) + 1
    names = b'\0'
    offsets = {}
    for path in files:
        offsets[path] = len(names); names += path.encode() + b'\0'
    table_end = 16 + count * 16 + len(names)
    output = bytearray((table_end + 511) // 512 * 512)
    struct.pack_into('<4I', output, 0, 0x52504637, count, len(names), 0x4e45504f)
    struct.pack_into('<4I', output, 16, 0, 0x7fffff00, 1, len(files))
    output[16 + count * 16:table_end] = names
    for index, (path, data) in enumerate(files.items(), 1):
        offset = len(output)
        if path in compressed:
            c = zlib.compressobj(wbits=-15); blob = c.compress(data) + c.flush()
        else:
            blob = data
        version = resources.get(path)
        packed = offsets[path] | ((len(blob) if path in compressed or version is not None else 0) << 16) | ((offset // 512) << 40)
        first, second = packed & 0xffffffff, packed >> 32
        third, fourth = len(data), 0
        if version is not None:
            second |= 0x80000000; third = (version >> 4) << 28; fourth = (version & 15) << 28
        struct.pack_into('<4I', output, 16 + index * 16, first, second, third, fourth)
        output.extend(blob); output.extend(b'\0' * (-len(output) % 512))
    return bytes(output)


def pack(name='testcar', model='testvehicle', compressed=()):
    return rpf({'setup2.xml': ('<Setup><deviceName>dlc_' + name + '</deviceName></Setup>').encode(),
                'content.xml': b'<CDataFileMgr__ContentsOfDataFileXml/>',
                'vehicles.meta': ('<InitDatas><Item><modelName>' + model + '</modelName></Item></InitDatas>').encode()}, compressed)


BASE = json.dumps({'mount': '/game/', 'version': 'original', 'files': [
    ['common/data/dlcList.xml', 14, 17], ['original.bin', 20, 18],
    ['x64/dlcPacks/testcar/setup2.xml', 5, 19]]}).encode()
DLC = b'<?xml version="1.0"?><SMandatoryPacksData><Paths><Item>platform:\\base\\</Item></Paths></SMandatoryPacksData>'


class BrowserModsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='zema-browser-mods-')
        self.parent = Path(self.temp.name).resolve()
        self.manager = mods.BrowserMods(self.parent / 'imports')

    def tearDown(self):
        self.temp.cleanup()

    def test_import_reload_private_permissions(self):
        result = self.manager.import_bytes('car.rpf', pack())
        record = result['packs'][0]
        self.assertEqual(record['name'], 'testcar')
        self.assertEqual(record['vehicleModels'], ['testvehicle'])
        self.assertTrue(record['enabled'])
        self.assertEqual(stat.S_IMODE(self.manager.root.stat().st_mode), 0o700)
        for path in self.manager.root.iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(mods.BrowserMods(self.manager.root).catalog(), result)

    def test_immutable_snapshot_preserves_indices_originals_and_cache_version(self):
        before = hashlib.sha256(BASE + DLC).digest()
        identifier = self.manager.import_bytes('car.rpf', pack())['packs'][0]['id']
        snapshot = self.manager.snapshot('story', BASE, DLC)
        manifest = json.loads(snapshot.manifest_bytes)
        self.assertEqual(manifest['files'][0][0], 'common/data/dlcList.xml')
        self.assertEqual(manifest['files'][1], ['original.bin', 20, 18])
        self.assertEqual(manifest['files'][2][0], 'x64/dlcPacks/testcar/setup2.xml')
        self.assertEqual(manifest['files'][2][2], 19)
        self.assertEqual(snapshot.resolve('X64/dlcPacks/testcar/dlc.rpf'), pack())
        self.assertIn(b'platform:\\dlcPacks\\testcar\\', snapshot.resolve('common/data/dlcList.xml'))
        self.assertIsNone(snapshot.resolve('original.bin'))
        self.manager.set_enabled(identifier, False)
        empty = self.manager.snapshot('story', BASE, DLC)
        self.assertIsNone(empty.resolve('x64/dlcPacks/testcar/dlc.rpf'))
        self.assertNotEqual(snapshot.version, empty.version)
        self.manager.remove(identifier)
        self.assertEqual(snapshot.resolve('x64/dlcPacks/testcar/dlc.rpf'), pack())
        self.assertEqual(hashlib.sha256(BASE + DLC).digest(), before)
        self.assertFalse((self.manager.root / (identifier + '.rpf')).exists())

    def test_compressed_xml_and_modes(self):
        self.manager.import_bytes('car.rpf', pack(compressed=('setup2.xml', 'content.xml', 'vehicles.meta')))
        versions = {self.manager.snapshot(mode, BASE, DLC).version for mode in ('story', 'sandbox')}
        self.assertEqual(len(versions), 2)
        with self.assertRaisesRegex(mods.ModError, 'LAN asset parity'):
            self.manager.snapshot('lan', BASE, DLC)
        with self.assertRaises(mods.ModError):
            self.manager.snapshot('forged', BASE, DLC)

    def test_zip_import_and_atomic_multi_pack_rejection(self):
        def archive(entries):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as output:
                for key, value in entries:
                    output.writestr(key, value)
            return buffer.getvalue()
        result = self.manager.import_bytes('bundle.zip', archive([('vehicle/dlc.rpf', pack()), ('README.txt', b'notes')]))
        self.assertEqual(len(result['packs']), 1)
        old = self.manager.catalog()
        with self.assertRaises(mods.ModError):
            self.manager.import_bytes('bundle.zip', archive([('other.rpf', pack('other', 'othercar')), ('bad.rpf', b'bad')]))
        self.assertEqual(self.manager.catalog(), old)
        for entries in [[('../car.rpf', pack())], [('car.rpf', pack()), ('CAR.RPF', pack())], [('car.rpf', pack()), ('loader.lua', b'print(1)')]]:
            with self.assertRaises(mods.ModError):
                self.manager.import_bytes('bad.zip', archive(entries))

    def test_zip_symlinks_encryption_size_and_unknown_format(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as output:
            entry = zipfile.ZipInfo('dlc.rpf'); entry.create_system = 3; entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            output.writestr(entry, b'/outside')
        with self.assertRaises(mods.ModError):
            self.manager.import_bytes('bad.zip', buffer.getvalue())
        for name, data in [('bad.rar', b'x'), ('bad.zip', b'notzip'), ('bad.rpf', b'')]:
            with self.assertRaises(mods.ModError):
                self.manager.import_bytes(name, data)
        self.assertEqual(self.manager.catalog()['packs'], [])

    def test_encrypted_enhanced_plugin_nested_and_xml_rejection(self):
        encrypted = bytearray(pack()); struct.pack_into('<I', encrypted, 12, 0)
        enhanced = rpf({'setup2.xml': b'<Setup><deviceName>dlc_car</deviceName></Setup>',
                        'content.xml': b'<Data/>',
                        'models.rpf': rpf({'car.yft': b'X'*16}, resources={'car.yft': 163})})
        plugin = rpf({'setup2.xml': b'<S><deviceName>dlc_car</deviceName></S>', 'content.xml': b'<Data/>', 'hack.asi': b'PE'})
        xml = rpf({'setup2.xml': b'<!DOCTYPE x [<!ENTITY a "bad">]><S><deviceName>dlc_car</deviceName></S>',
                   'content.xml': b'<Data/>', 'vehicles.meta': b'<modelName>car</modelName>'})
        utf16 = rpf({'setup2.xml': '<!DOCTYPE x [<!ENTITY a "bad">]><S><deviceName>dlc_car</deviceName></S>'.encode('utf-16'),
                     'content.xml': b'<Data/>', 'vehicles.meta': b'<modelName>car</modelName>'})
        for data in (bytes(encrypted), enhanced, plugin, xml, utf16):
            with self.assertRaises(mods.ModError):
                self.manager.import_bytes('bad.rpf', data)

    def test_legacy_resource_and_duplicate_names_or_models(self):
        valid = rpf({'setup2.xml': b'<S><deviceName>dlc_car</deviceName></S>', 'content.xml': b'<Data/>',
                     'models.rpf': rpf({'car.yft': b'X'*16}, resources={'car.yft': 162})})
        self.assertEqual(mods.parse_pack(valid)['models'], ['car'])
        self.manager.import_bytes('car.rpf', pack())
        for data in (pack(), pack('other', 'testvehicle'), pack('testcar', 'other')):
            with self.assertRaises(mods.ModError):
                self.manager.import_bytes('other.rpf', data)
        self.assertEqual(len(self.manager.catalog()['packs']), 1)

    def test_unsafe_storage_and_corruption_preserved(self):
        linked = self.parent / 'link'; linked.symlink_to(self.manager.root, target_is_directory=True)
        with self.assertRaises(mods.ModError):
            mods.BrowserMods(linked)
        unsafe = self.parent / 'unsafe'; unsafe.mkdir(mode=0o755)
        with self.assertRaises(mods.ModError):
            mods.BrowserMods(unsafe)
        self.manager.import_bytes('car.rpf', pack())
        catalog = self.manager.root / 'catalog.json'
        catalog.write_bytes(b'corrupt')
        with self.assertRaises(mods.ModError):
            mods.BrowserMods(self.manager.root)
        self.assertEqual(catalog.read_bytes(), b'corrupt')

    def test_changed_import_refused_without_mutation(self):
        identifier = self.manager.import_bytes('car.rpf', pack())['packs'][0]['id']
        target = self.manager.root / (identifier + '.rpf')
        replacement = pack('newcar', 'newvehicle')
        target.write_bytes(replacement)
        with self.assertRaisesRegex(mods.ModError, 'changed unexpectedly'):
            self.manager.snapshot('story', BASE, DLC)
        self.assertEqual(target.read_bytes(), replacement)

    def test_catalog_write_failure_rolls_back_only_new_imports(self):
        self.manager.import_bytes('car.rpf', pack())
        original = {p.name: p.read_bytes() for p in self.manager.root.iterdir()}
        original_catalog = self.manager.catalog()
        write = self.manager._write
        def fail_catalog(name, data):
            if name == 'catalog.json':
                raise OSError('injected catalog disk failure')
            return write(name, data)
        with mock.patch.object(self.manager, '_write', side_effect=fail_catalog):
            with self.assertRaisesRegex(OSError, 'injected catalog'):
                self.manager.import_bytes('new.rpf', pack('newcar', 'newvehicle'))
        self.assertEqual({p.name: p.read_bytes() for p in self.manager.root.iterdir()}, original)
        self.assertEqual(self.manager.catalog(), original_catalog)
        self.assertEqual(mods.BrowserMods(self.manager.root).catalog(), original_catalog)

    def test_post_commit_sync_failure_keeps_referenced_archive_and_reload_valid(self):
        write = self.manager._write
        def fail_after_catalog(name, data):
            write(name, data)
            if name == 'catalog.json':
                raise OSError('injected directory fsync failure')
        with mock.patch.object(self.manager, '_write', side_effect=fail_after_catalog):
            with self.assertRaisesRegex(OSError, 'injected directory'):
                self.manager.import_bytes('car.rpf', pack())
        result = self.manager.catalog()
        self.assertEqual(len(result['packs']), 1)
        self.assertEqual(mods.BrowserMods(self.manager.root).catalog(), result)

    def test_archive_write_failure_rolls_back_and_preserves_existing_orphan(self):
        orphan_blob = pack('orphan', 'orphanvehicle')
        orphan = self.manager.root / (hashlib.sha256(orphan_blob).hexdigest() + '.rpf')
        orphan.write_bytes(orphan_blob); orphan.chmod(0o600)
        write = self.manager._write
        def fail_after_archive(name, data):
            write(name, data)
            if name.endswith('.rpf'):
                raise OSError('injected archive directory sync failure')
        with mock.patch.object(self.manager, '_write', side_effect=fail_after_archive):
            with self.assertRaises(OSError):
                self.manager.import_bytes('car.rpf', pack())
        self.assertEqual(list(self.manager.root.iterdir()), [orphan])
        self.assertEqual(orphan.read_bytes(), orphan_blob)
        self.assertEqual(mods.BrowserMods(self.manager.root).catalog()['packs'], [])

    def test_remove_catalog_failure_preserves_archive_and_prior_catalog(self):
        identifier = self.manager.import_bytes('car.rpf', pack())['packs'][0]['id']
        original = {p.name: p.read_bytes() for p in self.manager.root.iterdir()}
        with mock.patch.object(self.manager, '_write', side_effect=OSError('injected catalog failure')):
            with self.assertRaises(OSError):
                self.manager.remove(identifier)
        self.assertEqual({p.name: p.read_bytes() for p in self.manager.root.iterdir()}, original)
        self.assertEqual(len(mods.BrowserMods(self.manager.root).catalog()['packs']), 1)

    def test_remove_cleanup_failure_reports_committed_catalog_and_preserves_bytes(self):
        identifier = self.manager.import_bytes('car.rpf', pack())['packs'][0]['id']
        path = self.manager.root / (identifier + '.rpf')
        unlink = Path.unlink
        def fail_archive(target, *args, **kwargs):
            if target == path:
                raise OSError('injected archive deletion failure')
            return unlink(target, *args, **kwargs)
        with mock.patch.object(Path, 'unlink', autospec=True, side_effect=fail_archive):
            with self.assertRaisesRegex(mods.ModError, 'removed from the catalog'):
                self.manager.remove(identifier)
        self.assertEqual(path.read_bytes(), pack())
        self.assertEqual(self.manager.catalog()['packs'], [])
        self.assertEqual(mods.BrowserMods(self.manager.root).catalog()['packs'], [])

    def test_no_path_or_invalid_manifest_escape(self):
        for data in (b'{}', b'not json', json.dumps({'files': [['../escape', 1]]}).encode(),
                     json.dumps({'files': [['same', 1], ['SAME', 2]]}).encode(),
                     *[json.dumps({'files': [['same', value]]}).encode() for value in (-1, True, 0.1, 9007199254740992)]):
            with self.assertRaises(mods.ModError):
                self.manager.snapshot('story', data, DLC)
        snapshot = self.manager.snapshot('story', BASE, DLC)
        for path in ('../secret', '/absolute', 'a\\b', 'a//b'):
            with self.assertRaises(mods.ModError):
                snapshot.resolve(path)
        with self.assertRaises(mods.ModError):
            self.manager.set_enabled('unknown', True)


if __name__ == '__main__':
    unittest.main()
