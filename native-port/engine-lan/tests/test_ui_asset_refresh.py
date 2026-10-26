"""Refresh bounded UI bytes despite old OPFS blocks; no engine or cache deletion."""
from pathlib import Path
from public_test_inputs import game_file
import json
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import ui_asset_refresh as refresh
import stage_browser
import serve_browser
MIRROR=game_file('b/8b0b5899ed')

class UIRefresh(unittest.TestCase):
    def test_original_worker_patch_all_modes_and_refusal(self):
        original=(MIRROR/'io_worker.js').read_bytes()
        lan=stage_browser.patch('io_worker.js',original)
        self.assertIn(refresh.MARK.encode(),lan)
        for mode in ['story','sandbox']:
            worker=serve_browser.offline_worker('io_worker.js',original,mode)
            self.assertIn(refresh.MARK.encode(),worker)
            self.assertIn(('zema-browser-'+mode+'-gamedata-v1').encode(),worker)
        with self.assertRaises(ValueError):refresh.apply('changed worker')
        with self.assertRaises(ValueError):refresh.apply(lan.decode())
        self.assertIn(b'readFromStore(id, off, len, dst)',lan)
        self.assertNotIn(b'removeEntry(',lan)

    def test_actual_serve_bypasses_old_blocks_and_notifies_engine(self):
        worker=stage_browser.patch('io_worker.js',(MIRROR/'io_worker.js').read_bytes()).decode()
        setup=r'''
(async()=>{
 mem={buffer:new SharedArrayBuffer(4096)}; HEAPU8=new Uint8Array(mem.buffer);HEAP32=new Int32Array(mem.buffer);
 files=[{path:'common/data/ui/frontend.xml',size:4,zemaUIRefresh:true}];base='/data/';dataQuery='';table=64;sh={};
 noteRequest=()=>{};let staleReads=0;readFromStore=()=>{staleReads++};
 const w=table/4+16;HEAP32[w+1]=0;HEAP32[w+2]=1;HEAP32[w+4]=512;HEAP32[w+6]=2;
 await serve(0);
 if(staleReads!==0||HEAP32[w]!==2||HEAP32[w+7]!==2||HEAPU8[512]!==2||HEAPU8[513]!==3)throw Error('UI read used stale cache or broke slot completion');
 console.log('ACTUAL_UI_SERVE_FRESH_COPY_AND_COMPLETION_PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        prelude=r'''
const vm=require('node:vm');
const context={console,setTimeout,clearTimeout,AbortController,SharedArrayBuffer,Uint8Array,Int32Array,Atomics,
 TextDecoder,TextEncoder,performance,URL,self:{postMessage(){}},fetch:async()=>({ok:true,body:{getReader(){let sent=false;return {
 read:async()=>sent?{done:true}:(sent=true,{done:false,value:Uint8Array.from([1,2,3,4])}),cancel:async()=>{},releaseLock:()=>{}}}}}),
 BroadcastChannel:class {postMessage(){} close(){}}};
'''
        with tempfile.TemporaryDirectory(prefix='zgta-ui-serve-') as folder:
            p=Path(folder)/'test.cjs';p.write_text(prelude+'\nvm.runInNewContext('+json.dumps(worker+'\n'+setup)+',context);\n')
            result=subprocess.run(['node',str(p)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('ACTUAL_UI_SERVE_FRESH_COPY_AND_COMPLETION_PASS',result.stdout)

    def test_small_fresh_file_shared_request_size_failure_and_cache_fallback(self):
        test=r'''
const assert=require('node:assert/strict');
let fetches=0,cancelled=0;
const file={path:'common/data/ui/frontend.xml',size:4,zemaUIRefresh:true};
function response(chunks,ok=true){return {ok,body:{getReader(){let i=0;return {
 read:async()=>i<chunks.length?{done:false,value:Uint8Array.from(chunks[i++])}:{done:true},
 cancel:async()=>{cancelled++},releaseLock:()=>{}}}}};}
(async()=>{
 const network=async(url,options)=>{fetches++;assert.equal(url,'/data/common/data/ui/frontend.xml?v=1');assert.equal(options.cache,'no-store');return response([[1,2],[3,4]])};
 const [a,b]=await Promise.all([zemaUIAsset(file,'/data/','?v=1',network),zemaUIAsset(file,'/data/','?v=1',network)]);
 assert.strictEqual(a,b);assert.deepEqual([...a],[1,2,3,4]);assert.equal(fetches,1);
 assert.strictEqual(await zemaUIAsset(file,'/data/','?v=1',network),a);assert.equal(fetches,1);
 const archive={path:'x64/huge.rpf',size:999999999};assert.equal(await zemaUIAsset(archive,'','',network),null);assert.equal(fetches,1);
 assert.equal(await zemaUIAsset({...file,path:'oversized',size:1048577},'','',network),null);assert.equal(fetches,1);
 for(const [path,reply] of [['short',response([[1]])],['large',response([[1,2,3,4,5]])],['http',response([],false)]]) {
   const f={...file,path};let calls=0;
   assert.equal(await zemaUIAsset(f,'','',async()=>{calls++;return reply}),null);
   assert.equal(await zemaUIAsset(f,'','',network),null);assert.equal(calls,1);
 }
 assert.equal(cancelled,2);
 let signal;
 const failure={...file,path:'network'};
 assert.equal(await zemaUIAsset(failure,'','',async(u,o)=>{signal=o.signal;throw Error('offline')}),null);
 assert(signal instanceof AbortSignal);console.log('UI_FRESH_BYTES_BOUNDED_SHARED_FALLBACK_PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        with tempfile.TemporaryDirectory(prefix='zgta-ui-refresh-') as folder:
            p=Path(folder)/'test.cjs';p.write_text(refresh.HELPER+'\n'+test)
            result=subprocess.run(['node',str(p)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('UI_FRESH_BYTES_BOUNDED_SHARED_FALLBACK_PASS',result.stdout)

if __name__=='__main__':unittest.main()
