"""Real native ABI, typed browser WASM and worker wakeups for socket retirement."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import hashlib
import sys
from fixture import ROOT, engine, patcher, reviewed_feature_lan

class SocketLifecycle(unittest.TestCase):
    def test_real_feature_engine_close_extension_keeps_all_other_bodies_and_indices(self):
        before=reviewed_feature_lan();after,hook=patcher.append_socket_close(before)
        self.assertEqual(hashlib.sha256(before).hexdigest(),patcher.FEATURE_LAN_BEFORE_CLOSE)
        oldtypes,oldindices,_=patcher.gate.module_abi(before);newtypes,newindices,_=patcher.gate.module_abi(after)
        self.assertEqual(newtypes,oldtypes);self.assertEqual(newindices,oldindices+[oldindices[184]])
        old=dict(patcher.gate.sections(before));new=dict(patcher.gate.sections(after))
        self.assertEqual([(k,v) for k,v in old.items() if k not in (3,4,7,10)],[(k,v) for k,v in new.items() if k not in (3,4,7,10)])
        def bodies(raw):
            r=patcher.gate.Reader(raw);out=[r.take(r.uint()) for _ in range(r.count())];r.finish();return out
        a,b=bodies(old[10]),bodies(new[10]);imported=len(oldindices)-len(a)
        self.assertEqual([i+imported for i,(x,y) in enumerate(zip(a,b)) if x!=y],[184]);self.assertEqual(b[-1],a[184-imported])
        self.assertEqual(hook['results'],[])
        with self.assertRaisesRegex(ValueError,'Unreviewed feature LAN'):patcher.append_socket_close(before+b'changed')
        with tempfile.TemporaryDirectory(prefix='zema-close-engine-') as folder:
            binary=Path(folder)/'socket-close.wasm';binary.write_bytes(after)
            result=subprocess.run(['node','--wasm-staging','-e',"const fs=require('node:fs'),assert=require('node:assert/strict');const b=fs.readFileSync(process.argv[1]);assert(WebAssembly.validate(b));const m=new WebAssembly.Module(b);assert(WebAssembly.Module.exports(m).some(x=>x.name==='zema:lan:original:socket_close'));",str(binary)],capture_output=True,text=True,timeout=120)
            self.assertEqual(result.returncode,0,result.stderr)
    def test_actual_native_shutdown_callback_and_rust_lifecycle(self):
        library=Path(os.environ.get('ZEMA_TEST_LAN_LIBRARY',str(ROOT.parent/'app/Build/EngineLAN/RustHost/debug/libzema_engine_lan.a')))
        host=(ROOT/'EngineLanHost.c').read_text();start=host.index('static void close_socket(');end=host.index('\n}',start)+2
        fixture=(ROOT/'tests/native_socket_lifecycle.c').read_text().replace('/* PRODUCTION_CLOSE_CALLBACK */',host[start:end])
        with tempfile.TemporaryDirectory(prefix='zema-socket-close-') as folder:
            path=Path(folder);(path/'fixture.c').write_text(fixture)
            built=subprocess.run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT),str(path/'fixture.c'),str(library),'-o',str(path/'fixture')],capture_output=True,text=True)
            self.assertEqual(built.returncode,0,built.stderr)
            run=subprocess.run([str(path/'fixture')],capture_output=True,text=True,timeout=10)
            self.assertEqual(run.returncode,0,run.stderr);self.assertIn('NATIVE_SOCKET_LIFECYCLE_PASS',run.stdout)
    def test_typed_browser_shutdown_32_and_64_bit_tables_and_shared_workers(self):
        with tempfile.TemporaryDirectory(prefix='zema-browser-close-') as folder:
            path=Path(folder)/'fixture.json'
            for table64 in [False,True]:
                data,contract=engine(table64,include_close=True);patched,metadata=patcher.transform(data,contract)
                path.write_text(json.dumps({'wasm':base64.b64encode(patched).decode(),'metadata':metadata}))
                run=subprocess.run(['node',str(ROOT/'tests/socket_lifecycle.cjs'),str(path)],capture_output=True,text=True,timeout=20)
                self.assertEqual(run.returncode,0,run.stderr);self.assertIn('BROWSER_SOCKET_LIFECYCLE_PASS',run.stdout)
    def test_real_engine_shutdown_is_explicitly_pinned(self):
        contract=json.loads((ROOT.parent/'app/Tests/glue5_engine_lan_contract.json').read_text())
        close=next(h for h in contract['hooks'] if h['field']=='socket_close')
        self.assertEqual((close['name'],close['index'],close['params'],close['results']),('rage::netSocket::NativeShutdown()',184,['i64'],[]))
        self.assertEqual(close['body_sha256'],'06dad1d71648b7b639f74e144454fc9e7756ade58209086d325a7f1de769be17')
        self.assertIn('.socket_close=close_socket',(ROOT/'EngineLanHost.c').read_text())
