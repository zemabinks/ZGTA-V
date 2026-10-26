"""Exercise the production layout repairs and pin both engine representations."""
from pathlib import Path
from public_test_inputs import game_file
import hashlib
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import gamer_tags as tags
ENGINE=game_file('b/8b0b5899ed/game.wasm')
GENERATED=ROOT.parent/'app/Build/EngineLAN-WorldTools-20261018/AppRoot/Generated'

class GamerTags(unittest.TestCase):
    def test_native_actual_helper_preserves_valid_order_and_repairs_only_duplicates(self):
        fixture=r'''
#include <assert.h>
#include <stdlib.h>
#include "ZemaGamerTagLayout.h"
static uint8_t* mem;static uint64_t size=21000000,hud=20000000;static int calls;
static const int32_t sorted[15]={1,3,13,0,11,6,5,10,8,9,14,2,4,7,12};
uint8_t* mugoat_memory_data(void* instance,uint64_t* out){(void)instance;*out=size;return mem;}
void w2c_game_f35212_zema_tag_original(w2c_game* instance){(void)instance;calls++;mem[ZEMA_TAG_SORTED]=1;memcpy(mem+ZEMA_TAG_ORDER,sorted,sizeof sorted);}
static void seed(void){memset(mem,0,(size_t)size);memcpy(mem+ZEMA_TAG_HUD,&hud,8);memcpy(mem+ZEMA_TAG_ORDER,sorted,sizeof sorted);mem[ZEMA_TAG_SORTED]=1;}
int main(void){
 mem=calloc(1,(size_t)size);assert(mem);seed();
 mem[ZEMA_TAG_SORTED]=0;assert(ZemaGamerTagComplete(mem,size)==0);mem[ZEMA_TAG_SORTED]=1;
 assert(ZemaGamerTagComplete(mem,size)==15);assert(!memcmp(mem+ZEMA_TAG_ORDER,sorted,sizeof sorted));
 for(int32_t i=15;i<30;i++){int32_t n;memcpy(&n,mem+ZEMA_TAG_ORDER+4*i,4);assert(n==i);}
 for(unsigned i=0;i<52;i++){assert(mem[hud+i*672+264]==1);assert(mem[hud+i*672+263]==0&&mem[hud+i*672+265]==0);}
 assert(ZemaGamerTagComplete(mem,size)==0);
 seed();int32_t bad=-1;memcpy(mem+ZEMA_TAG_ORDER+116,&bad,4);uint8_t before[120];memcpy(before,mem+ZEMA_TAG_ORDER,120);assert(ZemaGamerTagComplete(mem,size)==0&&!memcmp(before,mem+ZEMA_TAG_ORDER,120));
 seed();uint64_t wrong=UINT64_MAX-10;memcpy(mem+ZEMA_TAG_HUD,&wrong,8);memcpy(before,mem+ZEMA_TAG_ORDER,120);assert(ZemaGamerTagComplete(mem,size)==0&&!memcmp(before,mem+ZEMA_TAG_ORDER,120));
 seed();assert(ZemaGamerTagComplete(mem,ZEMA_TAG_ORDER+119)==0);
 seed();mem[ZEMA_TAG_SORTED]=0;memset(mem+ZEMA_TAG_ORDER,0,120);w2c_game_f35212((w2c_game*)1);assert(calls==1);assert(!memcmp(mem+ZEMA_TAG_ORDER,sorted,sizeof sorted));int32_t last;memcpy(&last,mem+ZEMA_TAG_ORDER+116,4);assert(last==29);
 free(mem);return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'game.h').write_text('#include <stdint.h>\ntypedef struct {int unused;} w2c_game;\n')
            (p/'helper.c').write_bytes(tags.helper());(p/'main.c').write_text('#include "game.h"\nvoid w2c_game_f35212(w2c_game*);\n'+fixture)
            result=subprocess.run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT),'-I',str(p),str(p/'helper.c'),str(p/'main.c'),'-o',str(p/'test')],text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            subprocess.run([str(p/'test')],check=True)

    def test_browser_actual_helper_centering_bounds_and_original_first(self):
        script=r'''
const assert=require('node:assert/strict'),T=require(process.argv[1]);
const memory={buffer:new SharedArrayBuffer(21000000)},v=new DataView(memory.buffer),O=19506224,S=19506092,H=19561688,hud=20000000;
const first=[1,3,13,0,11,6,5,10,8,9,14,2,4,7,12];
function seed(){new Uint8Array(memory.buffer).fill(0);v.setBigUint64(H,BigInt(hud),true);first.forEach((p,i)=>v.setInt32(O+4*i,p,true));v.setUint8(S,1);}
function order(){return Array.from({length:30},(_,i)=>v.getInt32(O+4*i,true));}
function nameCentre(parts){const width=44,total=parts.filter(p=>p===0).length*width;let x=-total/2,last;for(const p of parts)if(p===0){last=x+width/2;x+=width;}return last;}
seed();assert.equal(nameCentre(order()),330);assert.equal(T.complete(memory),15);assert.equal(nameCentre(order()),0);assert.deepEqual(order().slice(0,15),first);assert.deepEqual(order().slice(15),Array.from({length:15},(_,i)=>i+15));
for(let i=0;i<52;i++){assert.equal(v.getUint8(hud+i*672+264),1);assert.equal(v.getUint8(hud+i*672+263),0);assert.equal(v.getUint8(hud+i*672+265),0);}
assert.equal(T.complete(memory),0);
for(const invalid of [-1,30,1000]){seed();v.setInt32(O+116,invalid,true);const before=order();assert.equal(T.complete(memory),0);assert.deepEqual(order(),before);}
seed();v.setBigUint64(H,0xffffffffffffffffn,true);const before=order();assert.equal(T.complete(memory),0);assert.deepEqual(order(),before);
seed();v.setUint8(S,0);assert.equal(T.complete(memory),0);
assert.equal(T.complete({buffer:new ArrayBuffer(4)}),0);
seed();let calls=0;v.setUint8(S,0);const cb=T.callback(memory,()=>{calls++;v.setUint8(S,1);});cb();assert.equal(calls,1);assert.equal(nameCentre(order()),0);
// Reacquire views on growth, never keep a detached stale view.
const grow=new WebAssembly.Memory({initial:321,maximum:322});grow.grow(1);assert.equal(T.complete(grow),0);
console.log('BROWSER_GAMER_TAG_LAYOUT_CENTERED_BOUNDED_ORIGINAL_FIRST_PASS');
'''
        result=subprocess.run(['node','-e',script,str(ROOT/'gamer_tags.js')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('LAYOUT_CENTERED',result.stdout)

    def test_original_engine_body_and_native_source_pin_and_repatch_rejection(self):
        data=ENGINE.read_bytes();self.assertEqual(tags.inspect(data),tags.HOOK)
        source=(GENERATED/'game_19.c').read_bytes();patched=tags.patch_part(source)
        self.assertEqual(patched.replace(tags.RENAMED.encode()+b' {\n',tags.SIGNATURE.encode()+b' {\n',1),source)
        with self.assertRaises(ValueError):tags.patch_part(patched)
        with self.assertRaises(ValueError):tags.patch_part(source.replace(tags.SIGNATURE.encode()+b' {\n',tags.SIGNATURE.encode()+b' {\n/* changed */\n',1))
        with self.assertRaises(ValueError):tags.inspect(b'wrong engine')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'game_19.c').write_bytes(source)
            tags.stage(data,p);tags.verify(data,p)
            (p/'ZemaNativeGamerTags.c').write_bytes(tags.helper()+b'changed')
            with self.assertRaises(ValueError):tags.verify(data,p)

if __name__=='__main__':unittest.main()
