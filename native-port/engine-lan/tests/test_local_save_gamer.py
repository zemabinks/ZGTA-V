"""Pinned local-save gate regression; no game or user saves are executed."""
import hashlib
from pathlib import Path
import subprocess
import sys
import unittest
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import local_save_gamer as save
import browser_wasm as b
from fixture import reviewed_feature_lan

class LocalSaveGamer(unittest.TestCase):
    def test_scoped_offline_writer_preserves_remote_callers(self):
        r=subprocess.run(['node',str(ROOT/'tests/local_save_gamer.cjs')],capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('LOCAL_SAVE_GAMER_SCOPE_DURABLE_CHARACTER_AND_SIGNIN_STATE_PASS',r.stdout)

    def test_exact_engine_extension_changes_only_the_guard_body(self):
        before,_=b.append_socket_close(reviewed_feature_lan())
        after,hook=save.append(before)
        self.assertEqual(hook['field'],'active_gamer_info')
        self.assertEqual(hook['index'],83013)
        _,indices,_=b.gate.module_abi(before)
        def bodies(data):
            sections=dict(b.gate.sections(data));r=b.gate.Reader(sections[3]);defined=r.count();imported=len(b.gate.module_abi(data)[1])-defined
            r=b.gate.Reader(sections[10]);return imported,[r.take(r.uint()) for _ in range(r.count())]
        imported,old=bodies(before);_,new=bodies(after)
        self.assertEqual(len(new),len(old)+1)
        for n,body in enumerate(old):
            if n==83013-imported:self.assertNotEqual(new[n],body)
            else:self.assertEqual(new[n],body)
        self.assertEqual(new[-1],old[83013-imported])
        self.assertEqual(hashlib.sha256(before).hexdigest(),save.INPUT)
        with tempfile.TemporaryDirectory(prefix='zgta-local-save-wasm-') as tmp:
            file=Path(tmp)/'save-candidate.wasm';file.write_bytes(after)
            code="const a=require('node:assert/strict'),b=require('node:fs').readFileSync(process.argv[1]);a(WebAssembly.validate(b));const m=new WebAssembly.Module(b);a(WebAssembly.Module.exports(m).some(e=>e.name==='zema:lan:original:active_gamer_info'));console.log('VALIDATED_NOT_INSTANTIATED');"
            r=subprocess.run(['node','--wasm-staging','-e',code,str(file)],capture_output=True,text=True,timeout=120)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        with self.assertRaisesRegex(ValueError,'Unreviewed LAN'):save.append(before+b'changed')
        with self.assertRaisesRegex(ValueError,'Unreviewed LAN'):save.append(after)

if __name__=='__main__':unittest.main()
