"""Execute the pinned cipher entry in C/WASM; cipher stubs expose dispatch only."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import open_rpf as patch
b=patch.b
APP=ROOT.parent/'app'
NATIVE=APP/'Build/Phone-ModThermalDiagnostics-20261024-v76/AppRoot/Generated/game_1.c'
BROWSER=APP/'Build/Browser-DirectSession-20261023-v70-r4'


def run(args):
    result=subprocess.run([str(v) for v in args],capture_output=True,text=True,timeout=120)
    if result.returncode:raise AssertionError(result.stdout+'\n'+result.stderr)
    return result.stdout


def bodies(data):
    sections=dict(b.gate.sections(data))
    types,indices,_=b.gate.module_abi(data)
    r=b.gate.Reader(sections[3]);imported=len(indices)-r.count()
    r=b.gate.Reader(sections[10]);rows=[r.take(r.uint()) for _ in range(r.count())]
    return imported,rows


def fixture(body):
    # Only remap two original callees to test imports; retain the cipher's code.
    assert body.count(b'\x10\xa6\x09')==1 and body.count(b'\x10\xa5\x09')==1
    body=body.replace(b'\x10\xa6\x09',b'\x10\x00').replace(b'\x10\xa5\x09',b'\x10\x01')
    types=b'\x03\x60\x02\x7e\x7f\x01\x7e\x60\x03\x7e\x7f\x7e\x00\x60\x03\x7f\x7e\x7f\x00'
    imports=(b'\x03'+b.string('env')+b.string('key')+b'\x00\x00'+
             b.string('env')+b.string('cipher')+b'\x00\x01'+
             b.string('env')+b.string('memory')+b'\x02\x07'+b.leb(256)+b.leb(256))
    global_=b'\x01\x7e\x01\x42'+b.sleb(131072)+b'\x0b'
    return (b'\0asm\1\0\0\0'+b.section(1,types)+b.section(2,imports)+
            b.section(3,b'\x01\x02')+b.section(6,global_)+
            b.section(7,b'\x01'+b.string('decrypt')+b'\0\x02')+
            b.section(10,b'\x01'+b.leb(len(body))+body))


class OpenRPF(unittest.TestCase):
    def test_full_browser_modules_change_only_cipher_and_validate(self):
        for name in ['game.features.offline.wasm','game.engine-lan.wasm']:
            original=(BROWSER/name).read_bytes();after,record=patch.transform(original)
            a,old=bodies(original);c,new=bodies(after)
            self.assertEqual(a,c)
            self.assertEqual([i+a for i,(x,y) in enumerate(zip(old,new)) if x!=y],[1194])
            self.assertEqual(len(old),len(new))
            self.assertEqual([(k,v)for k,v in b.gate.sections(original)if k!=10],[(k,v)for k,v in b.gate.sections(after)if k!=10])
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'engine.wasm';path.write_bytes(after)
                run(['node','--wasm-staging','-e',"new WebAssembly.Module(require('fs').readFileSync(process.argv[1]));",path])
            self.assertEqual(record['scope'],'OPEN_PLAINTEXT_TABLES_ONLY')
            with self.assertRaises(ValueError):patch.transform(after)

    def test_original_and_corrected_wasm_dispatch(self):
        data=(BROWSER/'game.features.offline.wasm').read_bytes()
        imported,rows=bodies(data);original=rows[1194-imported]
        script='''const fs=require('fs');
const memory=new WebAssembly.Memory({initial:256n,maximum:256n,shared:true,address:'i64'});
const view=new Uint8Array(memory.buffer);let calls=0;
const game=new WebAssembly.Instance(new WebAssembly.Module(fs.readFileSync(process.argv[1])),{env:{memory,key:()=>{calls++;return 0n},cipher:(at,n)=>{for(let i=0;i<n;i++)view[Number(at)+i]^=0xaa}}});
let out=[];for(const key of [0x4e45504f,0x0ffffff9,0,0x12345678,0x0fefffff]){
calls=0;view.fill(0,8360520,8360528);view.fill(0x5a,512,544);
game.exports.decrypt(key,512n,32);out.push([key,calls,Array.from(view.slice(512,544))]);}
console.log(JSON.stringify(out));'''
        with tempfile.TemporaryDirectory() as folder:
            results=[]
            for name,body in [('before',original),('after',patch.patch_body(original))]:
                path=Path(folder)/(name+'.wasm');path.write_bytes(fixture(body))
                results.append(json.loads(run(['node','--wasm-staging','-e',script,path])))
            before,after=results
            self.assertEqual(before[0][1],1)
            self.assertEqual(after[0][1:], [0,[0x5a]*32])
            self.assertEqual(before[1:],after[1:])

    def test_exact_native_entry_preserves_open_tables_other_keys_unchanged(self):
        original=NATIVE.read_bytes();after=patch.patch_native(original)
        self.assertEqual(patch.patch_native(after,undo=True),original)
        with self.assertRaises(ValueError):patch.patch_native(after)
        prefix='''#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;typedef uint64_t u64;
typedef struct{uint8_t *data;uint64_t size;} Memory;
typedef struct{Memory *w2c_env_memory;uint64_t w2c_g0;} w2c_game;
#define FUNC_PROLOGUE
#define FUNC_EPILOGUE
static unsigned calls;
static uint64_t i64_load_shared(const void*a,uint64_t b,Memory*m,uint64_t at){(void)a;(void)b;uint64_t v;memcpy(&v,m->data+at,8);return v;}
static uint64_t w2c_game_f1190(w2c_game*g,uint64_t at,uint32_t key){(void)g;(void)at;(void)key;calls++;return 0;}
static void w2c_game_f1189(w2c_game*g,uint64_t at,uint32_t n,uint64_t ctx){(void)ctx;for(unsigned i=0;i<n;i++)g->w2c_env_memory->data[at+i]^=0xaa;}
'''
        suffix='''int main(void){static uint8_t data[1<<24];Memory m={data,sizeof data};w2c_game g={&m,131072};
unsigned keys[]={0x4e45504f,0x0ffffff9,0,0x12345678,0x0fefffff};
for(unsigned i=0;i<5;i++){calls=0;memset(data+512,0x5a,32);w2c_game_f1194(&g,keys[i],512,32);printf("%u %u %u\\n",keys[i],calls,data[512]);}return 0;}
'''
        with tempfile.TemporaryDirectory() as folder:
            results=[]
            for name,text in [('before',original),('after',after)]:
                root=Path(folder);p=root/(name+'.c');p.write_text(prefix+patch.native_body(text.decode())[0]+suffix)
                exe=root/name;run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror',p,'-o',exe])
                results.append(run([exe]).splitlines())
            before,after=results
            self.assertEqual(before[0],str(patch.OPEN)+' 1 240')
            self.assertEqual(after[0],str(patch.OPEN)+' 0 90')
            self.assertEqual(before[1:],after[1:])


if __name__=='__main__':unittest.main()
