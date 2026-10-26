"""The actual shared helper must not turn a timed-out scan into completion."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import engine_safety as safety
from test_engine_safety import fixture, run

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT.parent/'app'

class VisibilityWait(unittest.TestCase):
    def test_native_event_consumption_timeout_signalling_and_scope(self):
        prelude=r'''
#include <assert.h>
#include <stdatomic.h>
#include <stdlib.h>
#include "NativeEngineSafety.h"
typedef struct { uint8_t *data; uint64_t size; } wasm_rt_shared_memory_t;
typedef struct { wasm_rt_shared_memory_t *w2c_env_memory; } w2c_game;
static unsigned waits,originals;static int signal_during_wait;
uint32_t w2c_game_f126(w2c_game *g,uint64_t event) {
  originals++;
  return atomic_exchange_explicit((_Atomic uint32_t*)(g->w2c_env_memory->data+event),0,memory_order_seq_cst)==1;
}
static uint32_t pg_atomic_wait32(wasm_rt_shared_memory_t *m,uint64_t at,uint32_t seen,uint64_t ns) {
  assert(at==4096 && seen==0 && ns==1000000);
  assert(atomic_load((_Atomic uint32_t*)(m->data+at+4))==1);waits++;
  if(signal_during_wait)atomic_store((_Atomic uint32_t*)(m->data+at),1);
  return signal_during_wait?0:2;
}
'''
        body='\n'.join(line for line in safety.VISIBILITY_NATIVE_HEADER.decode().splitlines() if not line.startswith('#include'))
        main=r'''
int main(void) {
  wasm_rt_shared_memory_t m={calloc(1,1u<<25),1u<<25};assert(m.data);w2c_game g={&m};
  uint64_t scan=4096;memcpy(m.data+11497192,&scan,8);
  uint32_t produced=7,active=1;memcpy(m.data+21308712,&produced,4);memcpy(m.data+11497184,&active,4);
  _Atomic uint32_t *state=(_Atomic uint32_t*)(m.data+4096),*waiters=state+1;
  assert(pg_engine_visibility_poll(&g,scan)==1);assert(waits==1&&!originals&&!atomic_load(waiters));
  // Timed out, but the external work counters and event stay unchanged.
  assert(!atomic_load(state));assert(pg_safety_u32(m.data,21308712)==7 && pg_safety_u32(m.data,11497184)==1);
  atomic_store(state,1);assert(pg_engine_visibility_poll(&g,scan)==1);assert(waits==1&&!atomic_load(state));
  signal_during_wait=1;assert(pg_engine_visibility_poll(&g,scan)==1);assert(waits==2&&!atomic_load(state)&&!atomic_load(waiters));
  assert(pg_engine_visibility_poll(&g,8192)==0);assert(originals==1);
  atomic_store((_Atomic uint32_t*)(m.data+8192),1);assert(pg_engine_visibility_poll(&g,8192)==1);assert(originals==2);
  atomic_store(state,2);assert(pg_engine_visibility_poll(&g,scan)==0);assert(originals==3&&!atomic_load(state));
  m.size=11497192;assert(pg_engine_visibility_poll(&g,scan)==0);assert(originals==4);
  assert(waits==2&&!atomic_load(waiters));free(m.data);return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='zgta-visibility-native-') as temp:
            d=Path(temp);(d/'helper.h').write_text(body);(d/'check.c').write_text(prelude+'\n#include "helper.h"\n'+main)
            run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-I',APP/'Source',d/'check.c','-o',d/'check'])
            run([d/'check'])

    def test_real_wasm_timeout_and_original_event_semantics_memory32_and_64(self):
        script=r'''
const fs=require('fs'),a=require('assert/strict'),wide=process.argv[2]==='true';
const memory=new WebAssembly.Memory({initial:wide?512n:512,maximum:wide?512n:512,shared:true,...(wide?{address:'i64'}:{})});
const e=new WebAssembly.Instance(new WebAssembly.Module(fs.readFileSync(process.argv[1])),{env:{memory}}).exports;
const v=new DataView(memory.buffer),words=new Int32Array(memory.buffer),set=(p,n)=>v.setUint32(p,n,true);
v.setBigUint64(11497192,4096n,true);set(21308712,7);set(11497184,1);
a.equal(e.visibility_poll(4096n),1);a.equal(v.getUint32(4096,true),0);a.equal(v.getUint32(4100,true),0);
a.equal(v.getUint32(21308712,true),7);a.equal(v.getUint32(11497184,true),1);
set(4096,1);a.equal(e.visibility_poll(4096n),1);a.equal(v.getUint32(4096,true),0);a.equal(v.getUint32(4100,true),0);
a.equal(e.visibility_poll(8192n),0);set(8192,1);a.equal(e.visibility_poll(8192n),1);a.equal(v.getUint32(8192,true),0);
set(4096,2);a.equal(e.visibility_poll(4096n),0);a.equal(v.getUint32(4096,true),0);a.equal(v.getUint32(4100,true),0);
v.setBigUint64(11497192,8192n,true);set(4096,1);a.equal(e.visibility_poll(4096n),1);
a.throws(()=>e.visibility_poll(4097n),WebAssembly.RuntimeError);
if(wide)a.throws(()=>e.visibility_poll(0xfffffffffffffffcn),WebAssembly.RuntimeError);
console.log('VISIBILITY_WAIT_SCOPE_EVENT_AND_COUNTERS_PASS');
'''
        with tempfile.TemporaryDirectory(prefix='zgta-visibility-wasm-') as temp:
            d=Path(temp)
            for wide in [False,True]:
                wasm=d/('wait-'+str(wide)+'.wasm');wasm.write_bytes(fixture(wide))
                self.assertIn('VISIBILITY_WAIT_SCOPE_EVENT_AND_COUNTERS_PASS',run(['node','--wasm-staging','-e',script,wasm,str(wide).lower()]))

    def test_only_scanner_call_is_redirected_and_set_event_is_pinned(self):
        self.assertEqual(safety.PINS['visibility_scan']['caller'],28266)
        old,new=safety.native_edits(28266)
        self.assertEqual(old.count('w2c_game_f126'),1)
        self.assertEqual(new.count('pg_engine_visibility_poll'),1)
        self.assertNotIn(126,safety.SELECTED);self.assertNotIn(127,safety.SELECTED)
        # The existing signal stores 1, checks waiter count, and notifies the
        # original event word. Pinning it guards the helper's wakeup contract.
        self.assertEqual(safety.ROWS[127]['wasm_body_sha256'],'2ef94b9947ec6b9573d56497eb993dfa57f46b221e970eb1d7b3999e230b99d9')
        cached=ROOT.parents[1].parent/'gta-intel-multiplayer-build-20261016/native-port/app/Generated'
        safety.verify_native_support(cached)
        with tempfile.TemporaryDirectory(prefix='zgta-visibility-contract-') as temp:
            d=Path(temp);original=(cached/'game_2.c').read_text()
            (d/'game_2.c').write_text(original.replace('u32 w2c_game_f126(', 'u32 changed_poll(',1))
            with self.assertRaisesRegex(ValueError,'event contract'):safety.verify_native_support(d)

if __name__=='__main__':unittest.main()
