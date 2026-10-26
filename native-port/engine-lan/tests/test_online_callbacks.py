"""Offline, synthetic native callbacks and disposable private profile files."""
import hashlib
import importlib.util
import json
from pathlib import Path
import os
import subprocess
import struct
import tempfile
import unittest
import zlib

ROOT=Path(__file__).resolve().parents[1]
LIB=Path(os.environ.get('ZEMA_TEST_LAN_LIBRARY',str(ROOT.parent/'app/Build/EngineLAN/RustHost/debug/libzema_engine_lan.a')))

class NativeCallbacks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='zema-online-test-')
        cls.path=Path(cls.temp.name).resolve();cls.binary=cls.path/'fixture'
        for source in [ROOT/'OnlineCallbacks.c',ROOT/'tests/online_fixture.c']:
            subprocess.run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT),'-c',str(source),'-o',str(cls.path/(source.stem+'.o'))],check=True,capture_output=True,timeout=30)
        subprocess.run(['/usr/bin/swiftc','-warnings-as-errors','-I',str(ROOT),'-I',str(ROOT/'tests'),'-module-cache-path',str(cls.path/'cache'),
            str(ROOT/'EngineLanProfileFile.swift'),str(ROOT/'tests/online_fixture.swift'),str(cls.path/'OnlineCallbacks.o'),str(cls.path/'online_fixture.o'),str(LIB),'-o',str(cls.binary)],check=True,capture_output=True,timeout=90)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def run_fixture(self,folder):
        return subprocess.run([str(self.binary),str(folder)],capture_output=True,text=True,timeout=20)

    def test_callbacks_disk_save_and_new_process_restore(self):
        folder=self.path/'zema-engine-lan-roundtrip'
        first=self.run_fixture(folder);self.assertEqual(first.returncode,0,first.stderr);self.assertIn('PROFILE_DISK_SAVE_PASS',first.stdout);self.assertEqual(first.stderr.count('[session] native-state/players 5/2 (observation only)'),1);self.assertIn('[session] native-state/players -2/2 (observation only)',first.stderr);self.assertIn('[session] native-state/players -1/0 (observation only)',first.stderr)
        data=(folder/'profile.zemapf').read_bytes();self.assertEqual(data[:8],b'ZEMAPF1\0');self.assertEqual(zlib.crc32(data[:-4]),int.from_bytes(data[-4:],'little'))
        second=self.run_fixture(folder);self.assertEqual(second.returncode,0,(second.stdout,second.stderr,[(p.name,oct(p.stat().st_mode&0o777)) for p in folder.iterdir()]));self.assertIn('PROFILE_DISK_RESUME_PASS',second.stdout)
        self.assertEqual(data,(folder/'profile.zemapf').read_bytes())
        self.assertEqual(folder.stat().st_mode&0o777,0o700)
        for p in folder.iterdir():self.assertEqual(p.stat().st_mode&0o777,0o600)

    def test_corrupt_current_preserved_without_backup_fallback(self):
        folder=self.path/'zema-engine-lan-corrupt';self.assertEqual(self.run_fixture(folder).returncode,0)
        target=folder/'profile.zemapf';original=target.read_bytes();bad=bytearray(original);bad[-1]^=1;target.write_bytes(bad)
        before={p.name:p.read_bytes() for p in folder.iterdir()}
        result=self.run_fixture(folder);self.assertNotEqual(result.returncode,0)
        self.assertEqual(before,{p.name:p.read_bytes() for p in folder.iterdir()})

    def test_changed_profile_keeps_previous_good_snapshot(self):
        folder=self.path/'zema-engine-lan-backup';self.assertEqual(self.run_fixture(folder).returncode,0)
        original=(folder/'profile.zemapf').read_bytes()
        r=subprocess.run([str(self.binary),str(folder),'mutate'],capture_output=True,text=True,timeout=20);self.assertEqual(r.returncode,0,(r.stdout,r.stderr))
        self.assertEqual((folder/'profile.previous.zemapf').read_bytes(),original)
        self.assertNotEqual((folder/'profile.zemapf').read_bytes(),original)

    def test_external_change_is_not_overwritten(self):
        folder=self.path/'zema-engine-lan-external';self.assertEqual(self.run_fixture(folder).returncode,0)
        r=subprocess.run([str(self.binary),str(folder),'external-change'],capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,(r.stdout,r.stderr));self.assertIn('EXTERNAL_CHANGE_PRESERVED_PASS',r.stdout)

    def test_valid_checksum_still_rejects_duplicate_unsafe_and_wrong_typed_records(self):
        for number,rows in enumerate([
            [('hdeadbeef',bytes(8)),('hdeadbeef',bytes(8))],
            [('f:../Story.save',b'bad')],
            [('hdeadbeef',bytes(4))],
            [('hffffffff',bytes(8)),('h00000000',bytes(8))],
        ]):
            data=b'ZEMAPF1\0'+struct.pack('<IHH',123456,4,len(rows))+b'zema'
            for key,value in rows:
                key=key.encode();data+=struct.pack('<HI',len(key),len(value))+key+value
            data+=struct.pack('<I',zlib.crc32(data))
            folder=self.path/('zema-engine-lan-invalid-'+str(number));folder.mkdir(mode=0o700);p=folder/'profile.zemapf';p.write_bytes(data);p.chmod(0o600)
            result=self.run_fixture(folder);self.assertNotEqual(result.returncode,0);self.assertEqual(p.read_bytes(),data)
            code="const fs=require('fs'),p=require(process.argv[1]);try{p.Profile.decode(fs.readFileSync(process.argv[2]));process.exit(1);}catch{process.exit(0);}"
            r=subprocess.run(['node','-e',code,str(ROOT/'online.js'),str(p)],capture_output=True,text=True,timeout=10);self.assertEqual(r.returncode,0,r.stderr)

    def test_symlink_and_nonprivate_profiles_refused(self):
        folder=self.path/'zema-engine-lan-links';folder.mkdir(mode=0o700);outside=self.path/'outside';outside.write_bytes(b'preserve')
        (folder/'profile.zemapf').symlink_to(outside)
        self.assertNotEqual(self.run_fixture(folder).returncode,0);self.assertEqual(outside.read_bytes(),b'preserve')
        direct=self.path/'zema-engine-lan-public';direct.mkdir(mode=0o755)
        self.assertNotEqual(self.run_fixture(direct).returncode,0);self.assertEqual(list(direct.iterdir()),[])

    def test_generated_complete_typed_abi_matches_pinned_contract(self):
        spec=importlib.util.spec_from_file_location('generate_online_host',ROOT/'generate_online_host.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        for name,text in m.generate().items():self.assertEqual((ROOT/name).read_text(),text)
        contract=json.loads((ROOT.parent/'app/Tests/glue5_engine_lan_contract.json').read_text())
        header=(ROOT/'ZemaOnlineHost.h').read_text()
        self.assertEqual(sum('ZemaOnline_'+h['field']+'(' in header for h in contract['hooks'] if h['group']!='vnet'),52)

    def test_browser_52_typed_callbacks_read_exact_native_profile(self):
        folder=self.path/'zema-engine-lan-cross-runtime';r=self.run_fixture(folder);self.assertEqual(r.returncode,0,r.stderr)
        spec=importlib.util.spec_from_file_location('browser_wasm',ROOT/'browser_wasm.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        contract=json.loads((ROOT.parent/'app/Tests/glue5_engine_lan_contract.json').read_text());helper=self.path/'online-typed.wasm'
        helper.write_bytes(m.auxiliary([h for h in contract['hooks'] if h['group']!='vnet']))
        r=subprocess.run(['node',str(ROOT/'tests/online_fixture.cjs'),str(folder/'profile.zemapf'),str(helper)],capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stderr);self.assertIn('BROWSER_52_TYPED_CALLBACKS_AND_NATIVE_PROFILE_COMPAT_PASS',r.stdout)

if __name__=='__main__':unittest.main()
