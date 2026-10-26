"""Hash-only map captions and bounded missing-text diagnostics."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'app'

class MapTextLabels(unittest.TestCase):
    def test_map_sprite_names_and_hash_only_getter_route(self):
        rows=dict(json.loads((APP/'Source/TextLabels.json').read_text()))
        for key,text in {'BLIP_77':'Lester','BLIP_78':'Michael','BLIP_8':'Waypoint',
                         'BLIP_66':'Strangers and Freaks','BLIP_DEST':'Destination',
                         'BLIP_CAR':'Vehicle','BLIP_CONT':'Contact'}.items():
            self.assertEqual(rows[key],text)
        self.assertNotIn('(null)',rows)
        self.assertTrue((APP/'Source/TextLabels-LICENSE.txt').is_file())

    def test_live_map_hashes_resolve_through_real_browser_callback(self):
        # Captured by the bounded in-app diagnostic while opening the pause map.
        # Hashes are independently matched against v-labels blob a41fa82b10d1c49cee82b2a07671e8deeec8b4ce.
        source=r'''
const assert=require('node:assert/strict'),helper=require(process.argv[1]);
const memory=new WebAssembly.Memory({initial:1});let next=1024n;
const hook=helper.callback(memory,()=>0n,n=>{const p=next;next+=n;return p;});
for(const [hash,caption] of [[0xf1fd8d5f,'Luxury Autos'],[0x0b9fe52a,'Premium Deluxe Motorsport'],
 [0x1ee6e520,'Junk Energy Skydive'],[0xdba644a6,'Stash House'],[0xea49f2f7,'Downtown Cab Co.'],
 [0x9f37311e,'RC Bandito Time Trial'],[0x2a1f0dd9,'Ron Jakowski'],
 [0x5360143f,'LS Car Meet'],[0x5f1c9b8f,'The Music Locker']]){
 const ptr=Number(hook(hash)),b=new Uint8Array(memory.buffer);assert(ptr>0);
 assert.equal(new TextDecoder().decode(b.subarray(ptr,b.indexOf(0,ptr))),caption);
}
'''
        subprocess.run(['node','-e',source,str(ROOT/'engine-lan/text_fallback.js')],check=True,capture_output=True)

    def test_native_audit_zero_collision_limit_and_repeat(self):
        source=r'''
#include "NativeMissingTextAudit.h"
#include <assert.h>
int main(void) {
  PGTextMissingAudit a={0};
  assert(pg_text_missing_first(&a,0));assert(!pg_text_missing_first(&a,0));
  assert(pg_text_missing_first(&a,UINT32_MAX));assert(!pg_text_missing_first(&a,UINT32_MAX));
  for(unsigned i=1;i<=126;i++) {assert(pg_text_missing_first(&a,i*256));assert(!pg_text_missing_first(&a,i*256));}
  assert(a.count==128);assert(!pg_text_missing_first(&a,123));assert(a.count==128);
}
'''
        with tempfile.TemporaryDirectory(prefix='zgta-text-audit-') as temporary:
            p=Path(temporary);(p/'test.c').write_text(source)
            subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(APP/'Source'),str(p/'test.c'),'-o',str(p/'test')],check=True,capture_output=True)
            subprocess.run([str(p/'test')],check=True)

    def test_browser_audit_never_changes_unknown_or_original_return(self):
        source=r'''
const assert=require('node:assert/strict');
const helper=require(process.argv[1]);
const memory=new WebAssembly.Memory({initial:1});let original=0n,allocations=0;const logs=[];
const hook=helper.callback(memory,()=>original,()=>{allocations++;return 512n;},s=>logs.push(s));
for(let i=0;i<150;i++) {assert.equal(hook(i),0n);assert.equal(hook(i),0n);}
assert.equal(logs.length,128);assert.equal(logs[0],'[text-missing] hash 0x00000000');assert.equal(allocations,0);
original=222n;assert.equal(hook(1),222n);assert.equal(logs.length,128);
original=0n;const throwing=helper.callback(memory,()=>0n,()=>0n,()=>{throw Error('diagnostic sink');});
assert.equal(throwing(123),0n);
const map=helper.callback(memory,()=>0n,()=>1024n);const ptr=map(helper.labelHash('BLIP_78'));
const b=new Uint8Array(memory.buffer),at=Number(ptr);assert.equal(new TextDecoder().decode(b.subarray(at,b.indexOf(0,at))),'Michael');
'''
        subprocess.run(['node','-e',source,str(ROOT/'engine-lan/text_fallback.js')],check=True,capture_output=True)

if __name__=='__main__':unittest.main()
