"""Execute production C/WASM guards on the same edge cases and pin real patches."""
import hashlib
import json
from pathlib import Path
from public_test_inputs import game_file
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import engine_safety as safety
b=safety.b
APP=ROOT.parent/'app'
MIRROR=game_file('b/8b0b5899ed/game.wasm')
STAGE=APP/'Build/Browser-UpstreamStability-20261021-v42'

def run(args,timeout=120):
    p=subprocess.run([str(v) for v in args],capture_output=True,text=True,timeout=timeout)
    if p.returncode:raise AssertionError(p.stdout+'\n'+p.stderr)
    return p.stdout

def fixture(memory64,job_resolution=None):
    rows=safety.helpers(0,memory64,memory64,job_type=1,job_resolution=job_resolution);types=[];functions=[]
    for sig,_ in rows:
        if sig not in types:types.append(sig)
        functions.append(types.index(sig))
    inverse={n:k for k,n in b.gate.TYPES.items()}
    raw=b'\0asm\1\0\0\0'+b.section(1,b.leb(len(types))+b''.join(b'\x60'+b.leb(len(p))+bytes(inverse[v] for v in p)+b.leb(len(r))+bytes(inverse[v] for v in r) for p,r in types))
    raw+=b.section(2,b'\1'+b.string('env')+b.string('memory')+b'\2'+b.leb(7 if memory64 else 3)+b.leb(512)+b.leb(512))
    raw+=b.section(3,b.leb(len(functions))+b''.join(b.leb(v) for v in functions))
    raw+=b.section(4,b'\1\x70'+b.leb(5 if memory64 else 1)+b.leb(16)+b.leb(16))
    raw+=b.section(7,b.leb(len(rows))+b''.join(b.string(n)+b'\0'+b.leb(i) for i,n in enumerate(safety.HELPER_NAMES)))
    raw+=b.section(9,b'\1\0'+(safety.i64(14) if memory64 else safety.i32(14))+b'\x0b\2\0\1')
    return raw+b.section(10,b.leb(len(rows))+b''.join(b.leb(len(code))+code for _,code in rows))

class EngineSafety(unittest.TestCase):
    def test_signed_constants_terminate_and_preserve_i64_limits(self):
        for value,encoded in [(-1,b'\x7f'),(-64,b'\x40'),(-65,b'\xbf\x7f'),
                              (0,b'\0'),(64,b'\xc0\0'),
                              (-(1<<63),b'\x80'*9+b'\x7f'),((1<<63)-1,b'\xff'*9+b'\0')]:
            self.assertEqual(b.sleb(value),encoded)
        for value in [1<<63,-(1<<63)-1,True]:
            with self.assertRaises(ValueError):b.sleb(value)

    def test_native_and_wasm_guards_agree_for_poison_budgets_phases_and_jobs(self):
        with tempfile.TemporaryDirectory(prefix='zgta-engine-guards-') as folder:
            d=Path(folder);exe=d/'guards'
            run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror',APP/'Tests/engine_safety.c','-o',exe])
            expected=json.loads(run([exe]))
            for memory64 in [False,True]:
                path=d/('helpers'+str(memory64)+'.wasm');path.write_bytes(fixture(memory64))
                result=json.loads(run(['node','--wasm-staging',ROOT/'tests/engine_safety.cjs',path,str(memory64).lower()]))
                self.assertEqual(result,expected)

    def test_exact_browser_images_compile_and_preserve_every_unselected_body(self):
        for name in ['game.features.offline.wasm','game.engine-lan.wasm']:
            original=(STAGE/name).read_bytes();output,record=safety.transform(original)
            old=dict(b.gate.sections(original));new=dict(b.gate.sections(output))
            types,indices,_=b.gate.module_abi(original);_,after_indices,_=b.gate.module_abi(output)
            self.assertEqual(after_indices[:len(indices)],indices)
            reader=b.gate.Reader(old[3]);imported=len(indices)-reader.count()
            def bodies(raw):
                r=b.gate.Reader(raw);return [r.take(r.uint()) for _ in range(r.count())]
            a,c=bodies(old[10]),bodies(new[10])
            self.assertEqual([i+imported for i,(x,y) in enumerate(zip(a,c)) if x!=y],list(safety.SELECTED))
            self.assertEqual(len(c),len(a)+len(safety.HELPER_NAMES))
            for kind,data in old.items():
                if kind not in [1,3,7,10]:self.assertEqual(data,new[kind])
            with tempfile.TemporaryDirectory(prefix='zgta-safety-compile-') as folder:
                path=Path(folder)/'candidate.wasm';path.write_bytes(output)
                run(['node','--wasm-staging','-e',"const b=require('fs').readFileSync(process.argv[1]);if(!WebAssembly.validate(b))throw Error('validation');new WebAssembly.Module(b);",path])
            with self.assertRaisesRegex(ValueError,'Unreviewed'):safety.transform(output)
            with self.assertRaisesRegex(ValueError,'Unreviewed'):safety.transform(original+b'changed')

    def test_native_patch_is_exact_reversible_and_refuses_changed_functions(self):
        cached=ROOT.parents[1].parent/'gta-intel-multiplayer-build-20261016/native-port/app/Generated'
        groups={}
        for index in safety.SELECTED:groups.setdefault(safety.ROWS[index]['c_part'],[]).append(index)
        for part,selected in groups.items():
            original=(cached/part).read_bytes();patched=safety.native_part(original,selected)
            self.assertEqual(safety.native_part(patched,selected,undo=True),original)
            with self.assertRaises(ValueError):safety.native_part(patched,selected)
            corrupt=original.replace(b'(void)wasm_rt_local_memory_size;',b'(void)wasm_rt_local_memory_size; /* changed */')
            with self.assertRaises(ValueError):safety.native_part(corrupt,selected)
        code=safety.restore_code()
        self.assertLess(code.index(safety.call(5315)),len(code))
        self.assertIn('w2c_game_f5315(instance, 0u)',safety.native_edits(29099)[1])
        self.assertIn('.func_type != w2c_game_t4',safety.native_edits(2861)[1])

    def test_native_wait_uses_existing_futex_without_writing_engine_state(self):
        prelude=r'''
#include <assert.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <math.h>
#include "NativeEngineSafety.h"
typedef struct { uint8_t *data; uint64_t size; } wasm_rt_shared_memory_t;
typedef struct { wasm_rt_shared_memory_t *w2c_env_memory; } w2c_game;
static unsigned calls;
static uint32_t pg_atomic_wait32(wasm_rt_shared_memory_t *m,uint64_t at,uint32_t seen,uint64_t ns) {
  assert(at==25038496 && seen==0x12345678 && ns==1000000);
  assert(pg_safety_u32(m->data,at)==seen);calls++;return 2;
}
static uint32_t pg_atomic_notify(wasm_rt_shared_memory_t *m,uint64_t at,uint32_t count) {
  (void)m;(void)at;(void)count;return 0;
}
'''
        body='\n'.join(line for line in safety.NATIVE_HEADER.decode().splitlines() if not line.startswith('#include'))
        main=r'''
int main(void) {
  wasm_rt_shared_memory_t m={calloc(1,1u<<25),1u<<25};assert(m.data);
  w2c_game game={&m};uint32_t seen=0x12345678;memcpy(m.data+25038496,&seen,4);
  assert(!pg_engine_audio_idle_wait(&game,0));m.size=8;pg_engine_render_notify(&game);m.size=1u<<25;
  pg_engine_frame_idle_wait(&game,0);pg_engine_frame_idle_wait(&game,NAN);
  pg_engine_frame_idle_wait(&game,-1);assert(calls==0);
  m.size=10;pg_engine_frame_idle_wait(&game,0.002f);assert(calls==0);
  m.size=1u<<25;pg_engine_frame_idle_wait(&game,0.002f);assert(calls==1);
  assert(pg_safety_u32(m.data,25038496)==seen);free(m.data);return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='zgta-frame-wait-') as folder:
            d=Path(folder);(d/'helper.h').write_text(body);(d/'wait.c').write_text(prelude+'\n#include "helper.h"\n'+main)
            run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-I',APP/'Source',d/'wait.c','-o',d/'wait'])
            run([d/'wait'])

    def test_audio_wait_matches_native_deadline_and_render_wake_contract(self):
        source=r'''
#include <assert.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <math.h>
#include <stdio.h>
#include "NativeEngineSafety.h"
typedef struct { uint8_t *data; uint64_t size; } wasm_rt_shared_memory_t;
typedef struct { wasm_rt_shared_memory_t *w2c_env_memory; } w2c_game;
static unsigned waits,notifies;
static uint32_t pg_atomic_wait32(wasm_rt_shared_memory_t *m,uint64_t at,uint32_t seen,uint64_t ns) {
  assert(at==6638636 && seen==41 && ns==pg_safety_audio_idle_ns(15));
  assert(pg_safety_u32(m->data,at)==42);waits++;return 1;
}
static uint32_t pg_atomic_notify(wasm_rt_shared_memory_t *m,uint64_t at,uint32_t count) {
  assert(at==6638636 && count==UINT32_MAX);assert(pg_safety_u32(m->data,at)==42);notifies++;return 0;
}
'''
        body='\n'.join(line for line in safety.NATIVE_HEADER.decode().splitlines() if not line.startswith('#include'))
        main=r'''
int main(void) {
  float values[]={0,0.02f,0.021f,1,15,15.01f,NAN,INFINITY,-1};
  printf("[");for(unsigned i=0;i<sizeof(values)/sizeof(*values);i++)printf("%s%llu",i?",":"",(unsigned long long)pg_safety_audio_idle_ns(values[i]));printf("]\n");
  wasm_rt_shared_memory_t m={calloc(1,1u<<24),1u<<24};assert(m.data);w2c_game game={&m};
  pg_engine_frame_idle_wait(&game,0);
  uint32_t seen=41,current=42;memcpy(m.data+12046712,&seen,4);memcpy(m.data+6638636,&current,4);
  assert(!pg_engine_audio_idle_wait(&game,0));assert(!pg_engine_audio_idle_wait(&game,NAN));
  m.size=8;assert(!pg_engine_audio_idle_wait(&game,15));pg_engine_render_notify(&game);assert(!waits&&!notifies);
  m.size=1u<<24;assert(pg_engine_audio_idle_wait(&game,15));pg_engine_render_notify(&game);assert(waits==1&&notifies==1);
  assert(pg_safety_u32(m.data,12046712)==41&&pg_safety_u32(m.data,6638636)==42);free(m.data);return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='zgta-audio-wait-') as folder:
            d=Path(folder);(d/'helper.h').write_text(body);(d/'audio.c').write_text(source+'\n#include "helper.h"\n'+main)
            run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-I',APP/'Source',d/'audio.c','-o',d/'audio'])
            expected=json.loads(run([d/'audio']))
            for memory64 in [False,True]:
                path=d/('audio'+str(memory64)+'.wasm');path.write_bytes(fixture(memory64))
                script="""const fs=require('fs'),a=require('assert/strict'),wide=process.argv[2]==='true';
const memory=new WebAssembly.Memory({initial:wide?512n:512,maximum:wide?512n:512,shared:true,...(wide?{address:'i64'}:{})});
const e=new WebAssembly.Instance(new WebAssembly.Module(fs.readFileSync(process.argv[1])),{env:{memory}}).exports,v=new DataView(memory.buffer);
console.log(JSON.stringify([0,.02,.021,1,15,15.01,NaN,Infinity,-1].map(x=>Number(e.audio_idle_ns(x)))));
v.setUint32(12046712,41,true);v.setUint32(6638636,42,true);
a.equal(e.audio_idle_wait(0),0);a.equal(e.audio_idle_wait(NaN),0);a.equal(e.audio_idle_wait(15),1);e.render_notify();
a.equal(v.getUint32(12046712,true),41);a.equal(v.getUint32(6638636,true),42);
"""
                actual=json.loads(run(['node','--wasm-staging','-e',script,path,str(memory64).lower()]))
                self.assertEqual(actual,expected)

    def test_typed_job_guard_preserves_existing_lan_resolution(self):
        # The slot may intentionally name a typed LAN adapter. Check the same
        # resolved function the existing call_indirect would have called.
        with tempfile.TemporaryDirectory(prefix='zgta-job-resolution-') as folder:
            d=Path(folder);path=d/'mapped.wasm';path.write_bytes(fixture(True,{14:15}))
            script="""const fs=require('fs'),a=require('assert/strict');
const memory=new WebAssembly.Memory({initial:512n,maximum:512n,shared:true,address:'i64'});
const e=new WebAssembly.Instance(new WebAssembly.Module(fs.readFileSync(process.argv[1])),{env:{memory}}).exports,v=new DataView(memory.buffer);
v.setBigUint64(4096+96,14n,true);a.equal(e.stale_job(4096n),0);
v.setBigUint64(4096+96,0n,true);a.equal(e.stale_job(4096n),1);
v.setBigUint64(4096+96,16n,true);a.equal(e.stale_job(4096n),1);
"""
            run(['node','--wasm-staging','-e',script,path])
            old,new=safety.native_edits(2861);guard=new[:-len(old)]
            source=r'''
#include <assert.h>
#include <stdlib.h>
#include "NativeEngineSafety.h"
typedef uint64_t u64;
typedef struct { uint8_t *data; uint64_t size; } Memory;
typedef struct { int func_type; } Entry;
typedef struct { uint64_t size; Entry data[16]; } Table;
typedef struct { Memory *w2c_env_memory; Table w2c_0x5F_indirect_function_table; } w2c_game;
static int mapped,lookups;
enum { w2c_game_t4=4 };
static u64 ZemaSocialResolve(Table *table,int type,u64 index) {
  (void)table;assert(type==4);lookups++;return mapped&&index==14?15:index;
}
static int valid_job(w2c_game *instance,u64 var_l1) {
'''
            source+=guard+'  return 1;\nvar_L0: return 0;\n}\n'
            source+=r'''
int main(void) {
  Memory m={calloc(1,1u<<24),1u<<24};assert(m.data);
  w2c_game game={.w2c_env_memory=&m,.w2c_0x5F_indirect_function_table={.size=16}};
  game.w2c_0x5F_indirect_function_table.data[15].func_type=4;
  uint64_t index=15;memcpy(m.data+4096+96,&index,8);assert(valid_job(&game,4096));
  index=14;memcpy(m.data+4096+96,&index,8);assert(!valid_job(&game,4096));
  mapped=1;assert(valid_job(&game,4096));
  int previous=lookups;index=16;memcpy(m.data+4096+96,&index,8);
  assert(!valid_job(&game,4096)&&lookups==previous);
  assert(!valid_job(&game,UINT64_MAX)&&lookups==previous);
  index=15;memcpy(m.data+4096+96,&index,8);m.data[4096+110]=1;
  uint32_t size=268435457;memcpy(m.data+4096+112,&size,4);
  assert(!valid_job(&game,4096)&&lookups==previous);
  assert(pg_safety_u64(m.data,4096+96)==15);free(m.data);return 0;
}
'''
            (d/'job.c').write_text(source)
            run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-I',APP/'Source',d/'job.c','-o',d/'job'])
            run([d/'job'])

if __name__=='__main__':unittest.main()
