"""Execute the actual wrapper bytecode and C adapter using controlled originals."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import render_hooks as h
import browser_wasm as b


# Authenticated original WASM passive2637 bytes1454..1518 (table7344304).
ORIGINAL_TABLE = struct.pack('<32H', *([0]*2+[15]*9+[0xf00f]*9+[0xf0ff]*6+[65535]*6))
assert hashlib.sha256(ORIGINAL_TABLE).hexdigest() == 'b87826b95285d0856e865236d713a540bf4ddf204f338ba08932779250c18246'


def fixture():
    signatures=[([],[]),(['i64'],[]),(['i64','i32','i32','i32'],['i32']),([],[]),(['i32','i32'],[]),([],[]),
                (['i64','i32','i32'],[]),([],['i64']),(['i64'],['i64']),(['i64'],[]),(['i32','i64','i32'],[]),(['i32'],[])]
    inverse={v:k for k,v in b.gate.TYPES.items()}
    types=[b'\x60'+b.leb(len(p))+bytes(inverse[t] for t in p)+b.leb(len(r))+bytes(inverse[t] for t in r) for p,r in signatures]
    names=['lod','unlock','begin','end','alpha','reset','hint','current','alloc','restore','emit']
    imports=[b.string('mock')+b.string(name)+b'\0'+b.leb(j) for j,name in enumerate(names)]
    original={index:j for j,index in enumerate(h.HOOKS)}
    code,emit=h.wrappers(original,(0,1,2,3),17,dict(hint=6,stack_current=7,stack_alloc=8,stack_restore=9,gpu_emit=10))
    bodies=[code[index] for index in h.HOOKS]+[emit]
    exports=[b.string(name)+b'\0'+b.leb(11+j) for j,name in enumerate(names[:6])]+[b.string('memory')+b'\x02\0']
    return b'\0asm\x01\0\0\0'+b.section(1,b.leb(len(types))+b''.join(types))+b.section(2,b.leb(len(imports))+b''.join(imports))+b.section(3,b.leb(7)+b''.join(b.leb(j) for j in [0,1,2,3,4,5,11]))+b.section(5,b'\x01\x04'+b.leb(512))+b.section(6,b'\x04'+b''.join(b'\x7f\x01'+h.i32(v)+b'\x0b' for v in [0,255,0,0]))+b.section(7,b.leb(len(exports))+b''.join(exports))+b.section(10,b.leb(len(bodies))+b''.join(b.leb(len(v))+v for v in bodies))


class RenderHooks(unittest.TestCase):
    def test_native_exact_reversal_and_tamper_rejection(self):
        stage=ROOT.parents[2]/'zgta-lan-discovery97-private-20261027/native-port/app/Build/LAN-Discovery-20261027-v97/AppRoot/Generated'
        if not stage.exists():self.skipTest('Retained native97 generated inputs unavailable')
        for filename in sorted({r['file'] for r in h.PINS['native'] if r['index'] in h.HOOKS}):
            original=(stage/filename).read_bytes()
            rows=[r for r in h.PINS['native'] if r['file']==filename and r['index'] in h.HOOKS]
            patched=h.transform_native(original.decode(),rows).encode()
            self.assertEqual(h.undo_native_part(patched,filename),original)
            first=rows[0]['index'];wrapper=h.NATIVE_BODIES[first].encode()
            corruptions=[patched.replace(wrapper,wrapper.replace(b'{',b'{ ',1),1),
                         patched.replace(b'#include "game-render-hooks98.h"\n',b'#include "game-render-hooks98.h"\n'*2,1),
                         patched.replace(('pg98_original_'+str(first)+'(').encode(),b'pg98_corrupt_original(',1),
                         patched+b'\n'+h.NATIVE_STATE.encode()]
            for damaged in corruptions:
                with self.assertRaises(ValueError):h.undo_native_part(damaged,filename)
            # Unrelated bytes remain observable by the original whole-file gate.
            unrelated=b'/* deliberate unrelated mutation */\n'+patched
            self.assertNotEqual(hashlib.sha256(h.undo_native_part(unrelated,filename)).digest(),hashlib.sha256(original).digest())
        untouched=b'void untouched(void) {}\n'
        self.assertEqual(h.undo_native_part(untouched,'game_0.c'),untouched)
        with self.assertRaises(ValueError):h.undo_native_part(untouched+b'/* pg98_orphan */','game_0.c')

    def test_memory64_wasm_execution(self):
        result=subprocess.run(['node',str(ROOT/'tests/render_hooks.cjs')],input=json.dumps(dict(wasm=base64.b64encode(fixture()).decode(),original_table_hex=ORIGINAL_TABLE.hex())),text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('EXECUTION_PASS',result.stdout)

    def test_unreviewed_input_refused(self):
        with self.assertRaisesRegex(ValueError,'Unreviewed'):h.append(fixture())

    def test_native_execution(self):
        # Extracted adapters compile against the exact generated function ABI;
        # originals are controlled to exercise ordinary/fade/range-hint branches.
        pre='''#include <stdint.h>
#include <assert.h>
#include <string.h>
typedef uint32_t u32;typedef uint64_t u64;
typedef struct {uint8_t* data;} Memory;typedef struct {Memory* w2c_env_memory;} w2c_game;
static u32 i32_load_shared(void*a,u64 b,Memory*m,u64 at){u32 v;memcpy(&v,m->data+at,4);return v;}
static u32 i32_load16_u_shared(void*a,u64 b,Memory*m,u64 at){uint16_t v;memcpy(&v,m->data+at,2);return v;}
static u64 i64_load_shared(void*a,u64 b,Memory*m,u64 at){u64 v;memcpy(&v,m->data+at,8);return v;}
static void i32_store_shared(void*a,u64 b,Memory*m,u64 at,u32 v){memcpy(m->data+at,&v,4);}
static u32 original_alpha,original_invert;
static u64 stack=4096;static u32 emitted=99,nemit=0,nhint=0,ncall=0,passes=0,fallback=2;
u64 w2c_game_emscripten_stack_get_current(w2c_game*i){return stack;}u64 w2c_game_0x5Femscripten_stack_alloc(w2c_game*i,u64 n){return stack-=n;}
void w2c_game_0x5Femscripten_stack_restore(w2c_game*i,u64 top){stack=top;}
void w2c_game_f550(w2c_game*i,u32 op,u64 at,u32 n){assert(op==65&&n==1);emitted=i32_load_shared(0,0,i->w2c_env_memory,at);nemit++;}
void w2c_game_f244(w2c_game*i,u64 r,u32 o,u32 n){assert(r==100&&o==32&&n>131072);nhint++;}
void w2c_game_f9952(w2c_game*,u64);
static void pg98_original_44583(w2c_game*i){w2c_game_f9952(i,2000);}
static void pg98_original_9952(w2c_game*i,u64 p){}
static u32 pg98_original_9291(w2c_game*i,u64 p,u32 a,u32 b,u32 c){return ++ncall==1?passes:fallback;}
static void pg98_original_9295(w2c_game*i){}
static void pg98_original_64694(w2c_game*i,u32 a,u32 b){original_alpha=a;original_invert=b;u32 raw=i32_load16_u_shared(0,0,i->w2c_env_memory,7344304ull+((u64)((a>255?255:a)>>3)*2));i32_store_shared(0,0,i->w2c_env_memory,23984584,(raw^(0u-b))&65535u);}
static void pg98_original_43886(w2c_game*i){}
'''
        post='''static uint8_t bytes[26000000];
int main(){Memory m={bytes};w2c_game i={&m};
pg98_store32(&i,6634168,20);pg98_store32(&i,21490232,11);
pg98_store32(&i,7248300,20);pg98_store32(&i,7248304,21);pg98_store32(&i,7248320,22);
static const uint16_t table[32]={0,0,15,15,15,15,15,15,15,15,15,61455,61455,61455,61455,61455,61455,61455,61455,61455,61695,61695,61695,61695,61695,61695,65535,65535,65535,65535,65535,65535};
memcpy(bytes+7344304,table,sizeof(table));
for(u32 group=20;group<=22;group++)for(u32 a=0;a<=255;a++)for(u32 invert=0;invert<=1;invert++){
 pg98_store32(&i,6634168,group);w2c_game_f64694(&i,a,invert);
 assert(original_alpha==a&&original_invert==invert);ncall=0;nemit=0;
 u32 raw=table[a>>3]^(invert?65535u:0u),mask=0;
 for(u32 phase=0;phase<4;phase++)if(((raw>>(phase*4))&15u)==15u)mask|=1u<<phase;
 assert(w2c_game_f9291(&i,100,0,0,0)==(mask?2:0));
 assert(ncall==(mask?2:1));assert(pg98_load32(&i,6634168)==group);
 assert(nemit==!!(mask&&mask!=15));if(nemit)assert(emitted==(16u|mask));
 u32 before=nemit;w2c_game_f9295(&i);
 assert(nemit==before+!!(mask&&mask!=15));if(nemit)assert(emitted==0);
 assert(!pg98_stippling&&stack==4096);
}
pg98_store32(&i,6634168,20);
w2c_game_f64694(&i,0xffffffffu,1);ncall=0;nemit=0;assert(!w2c_game_f9291(&i,100,0,0,0)&&ncall==1&&!nemit);
w2c_game_f43886(&i);assert(pg98_stipple_alpha==255&&!pg103_stipple_invert);
ncall=0;assert(!w2c_game_f9291(&i,100,0,0,0)&&ncall==1&&!nemit);
passes=3;ncall=0;nemit=0;assert(w2c_game_f9291(&i,100,0,0,0)==3&&ncall==1&&!nemit);
passes=0;ncall=0;assert(!w2c_game_f9291(&i,100,0,0,9)&&ncall==1);
for(u32 invert=0;invert<2;invert++){
 w2c_game_f64694(&i,128,invert);passes=3;ncall=0;nemit=0;assert(w2c_game_f9291(&i,100,0,0,0)==3&&ncall==1&&!nemit);
 passes=0;ncall=0;assert(!w2c_game_f9291(&i,100,0,0,9)&&ncall==1&&!nemit);
 pg98_store32(&i,6634168,0xffffffffu);ncall=0;assert(!w2c_game_f9291(&i,100,0,0,0)&&ncall==1&&!nemit);
 pg98_store32(&i,6634168,99);ncall=0;assert(!w2c_game_f9291(&i,100,0,0,0)&&ncall==1&&!nemit);
 pg98_store32(&i,6634168,20);fallback=0;ncall=0;assert(!w2c_game_f9291(&i,100,0,0,0)&&ncall==2&&!nemit);
 assert(pg98_load32(&i,6634168)==20);w2c_game_f9295(&i);assert(!nemit);
 fallback=2;
}
/* Real original ResetAlpha/SetMSAAParams semantics are authenticated and run
   in test_fade_state104. Exercise their resulting state on this native adapter. */
pg98_store32(&i,12623176,1);pg98_store32(&i,7344224,1);
w2c_game_f64694(&i,128,0);pg98_store32(&i,23984584,65535);
ncall=nemit=0;assert(w2c_game_f9291(&i,100,0,0,0)==2&&ncall==2&&!nemit);w2c_game_f9295(&i);
w2c_game_f64694(&i,255,0);pg98_store32(&i,23984584,0xf00f);
ncall=nemit=0;assert(w2c_game_f9291(&i,100,0,0,0)==2&&emitted==25&&nemit==1);w2c_game_f9295(&i);
pg98_store32(&i,12623176,4);w2c_game_f64694(&i,128,0);
u64 mask=UINT64_MAX;memcpy(bytes+12433376,&mask,8);pg98_store32(&i,23984584,0);
ncall=nemit=0;assert(w2c_game_f9291(&i,100,0,0,0)==2&&!nemit);w2c_game_f9295(&i);
mask=0;memcpy(bytes+12433376,&mask,8);pg98_store32(&i,23984584,65535);
ncall=nemit=0;assert(!w2c_game_f9291(&i,100,0,0,0)&&ncall==1&&!nemit);w2c_game_f9295(&i);
mask=0x5555555555555555ull;memcpy(bytes+12433376,&mask,8);
ncall=nemit=0;assert(w2c_game_f9291(&i,100,0,0,0)==2&&emitted==25&&nemit==1);w2c_game_f9295(&i);
u64 resource=100;memcpy(bytes+2080,&resource,8);pg98_store32(&i,2096,32);pg98_store32(&i,2100,312<<10);
w2c_game_f9952(&i,2000);assert(!nhint);w2c_game_f44583(&i);assert(nhint==1&&!pg98_rendering_lod);
pg98_store32(&i,2100,128<<10);w2c_game_f44583(&i);assert(nhint==1);
w2c_game_f43886(&i);assert(pg98_stipple_alpha==255&&!pg103_stipple_invert);return 0;}
'''
        source=pre+h.NATIVE_HEADER+h.NATIVE_STATE+'\n'.join(h.NATIVE_BODIES.values())+post
        with tempfile.TemporaryDirectory(prefix='zgta-render-hooks98-') as td:
            exe=Path(td)/'test'
            result=subprocess.run(['clang','-std=c11','-O1','-x','c','-','-o',str(exe)],input=source,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
