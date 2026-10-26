import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import browser_wasm as b
import save_worker_probe as probe
import local_save_gamer
from fixture import reviewed_feature_lan

class SaveWorkerProbe(unittest.TestCase):
    def test_forwarding_scope_and_no_pointer_logs(self):
        p=subprocess.run(['node',str(ROOT/'tests/save_worker_probe.cjs')],capture_output=True,text=True,timeout=20)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)

    def test_exact_engine_changes_only_three_forwarding_bodies(self):
        closed,_=b.append_socket_close(reviewed_feature_lan())
        original,_=local_save_gamer.append(closed)
        output,hooks=probe.append(original)
        def bodies(data):
            types,indices,names=b.gate.module_abi(data);sections=dict(b.gate.sections(data));r=b.gate.Reader(sections[3]);imported=len(indices)-r.count()
            r=b.gate.Reader(sections[10]);return imported,[r.take(r.uint()) for _ in range(r.count())]
        imported,old=bodies(original);_,new=bodies(output);selected={h['index']-imported for h in hooks}
        self.assertEqual(len(new),len(old)+3)
        for index,body in enumerate(old):
            if index not in selected:self.assertEqual(body,new[index])
        for n,h in enumerate(hooks):self.assertEqual(new[len(old)+n],old[h['index']-imported])
        before=dict(b.gate.sections(original));after=dict(b.gate.sections(output))
        for kind,body in before.items():
            if kind not in (3,4,7,10):self.assertEqual(body,after[kind])
        with tempfile.TemporaryDirectory(prefix='zgta-save-worker-') as tmp:
            path=Path(tmp)/'probe.wasm';path.write_bytes(output)
            p=subprocess.run(['node','--wasm-staging','-e',"const a=require('node:assert/strict'),b=require('node:fs').readFileSync(process.argv[1]);a(WebAssembly.validate(b));new WebAssembly.Module(b);",str(path)],capture_output=True,text=True,timeout=120)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        with self.assertRaisesRegex(ValueError,'Unreviewed'):probe.append(output)
        with self.assertRaisesRegex(ValueError,'Unreviewed'):probe.append(original+b'changed')

if __name__=='__main__':unittest.main()
