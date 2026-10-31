"""Exercise the actual composed cache read function with sync OPFS fixtures."""
import hashlib, json, subprocess, sys, tempfile, unittest
from pathlib import Path
from public_test_inputs import game_file
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import io_scratch, stage_browser, serve_browser

class IOScratch101(unittest.TestCase):
 def test_actual_workers_and_bounded_fallback(self):
  raw=game_file('b/8b0b5899ed/io_worker.js').read_bytes()
  self.assertEqual(hashlib.sha256(raw).hexdigest(),stage_browser.PINS['io_worker.js'])
  for mode in ['lan','story','sandbox']:
   worker=(stage_browser.patch('io_worker.js',raw) if mode=='lan' else serve_browser.offline_worker('io_worker.js',raw,mode)).decode()
   self.assertIn('ZGTA_IO_LIFECYCLE_V1',worker)
   self.assertIn(io_scratch.MARK,worker)
   with self.assertRaises(ValueError):io_scratch.apply(worker)
   start=worker.index('let storeReadScratch = null;')
   end=worker.index('// ---- without a store',start)
   fragment=worker[start:end]
   fixture=r'''
const assert=require('node:assert/strict');
const BS=4096,index=new Map(),HEAPU8=new Uint8Array(2*1024*1024);
const disk=new Uint8Array(3*1024*1024);for(let i=0;i<disk.length;i++)disk[i]=(i*17+Math.floor(i/BS))%251;
let sharedReadFails=false,rejectShared=false,short=false,calls=[],logs=0;
function log(){logs++;}
const sh={read(dst,{at}){
 calls.push({size:dst.length,at,buffer:dst.buffer});
 if(rejectShared&&dst.buffer===HEAPU8.buffer)throw Error('Shared destinations unsupported');
 const n=short?dst.length-1:dst.length;dst.set(disk.subarray(at,at+n));return n;
}};
''' + fragment + r'''
// Contiguous read spanning >3 scratch chunks, with unaligned file boundaries.
for(let i=0;i<300;i++)index.set(1048576+i,i*BS);
const length=900001,offset=37,dst=113;
readFromStore(1,offset,length,dst);
assert.equal(storeReadScratch,null);assert.equal(calls.length,1);
assert.deepEqual(HEAPU8.slice(dst,dst+length),disk.slice(offset,offset+length));
rejectShared=true;calls=[];HEAPU8.fill(0);readFromStore(1,offset,length,dst);
assert.equal(logs,1);assert.equal(storeReadScratch.length,256*1024);
const scratch=storeReadScratch;assert.equal(calls.length,5);
assert(calls.slice(1).every(c=>c.size<=256*1024&&c.buffer===scratch.buffer));
assert.deepEqual(HEAPU8.slice(dst,dst+length),disk.slice(offset,offset+length));
calls=[];readFromStore(1,offset,length,dst);assert.equal(storeReadScratch,scratch);assert.equal(logs,1);assert.equal(calls.length,4);
// A fragmented store maps adjacent file blocks to nonadjacent disk offsets.
index.set(2*1048576,0);index.set(2*1048576+1,10*BS);calls=[];
readFromStore(2,BS-20,40,0);
assert.deepEqual(HEAPU8.slice(0,20),disk.slice(BS-20,BS));assert.deepEqual(HEAPU8.slice(20,40),disk.slice(10*BS,10*BS+20));
assert.equal(calls.length,2);
// Invalid/short disk data must never copy stale scratch bytes into engine memory.
short=true;HEAPU8.fill(77);assert.throws(()=>readFromStore(1,0,BS,0),/store read returned/);
assert(HEAPU8.slice(0,BS).every(v=>v===77));short=false;
calls=[];readFromStore(1,0,0,0);assert.equal(calls.length,0);
console.log('PASS bounded cache fallback, direct path, reuse, fragments and short reads');
'''
   with tempfile.NamedTemporaryFile('w',suffix='.cjs') as f:
    f.write(fixture);f.flush()
    result=subprocess.run(['node',f.name],text=True,capture_output=True,timeout=10)
   self.assertEqual(result.returncode,0,mode+': '+result.stdout+result.stderr)

if __name__=='__main__':unittest.main()
