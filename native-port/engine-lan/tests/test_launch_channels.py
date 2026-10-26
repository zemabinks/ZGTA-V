import json,subprocess,sys,unittest
from pathlib import Path
from public_test_inputs import game_file
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import launch_channels as c
import serve_browser
APP=ROOT.parent/'app';MIRROR=game_file('');STAGE=APP/'Build/Browser-VisibilityWait-20261021-v46'

class LaunchChannels(unittest.TestCase):
 def test_loading_helper_receives_only_its_launch_and_blocks_gpu_failure(self):
  code=r'''
const a=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),{BroadcastChannel}=require('node:worker_threads');
const source=fs.readFileSync(process.argv[1],'utf8');
async function test(failure=null){
 const failed=failure!==null;
 let now=0,tick,events={},notes=[],frontend=0;const shared=new SharedArrayBuffer(256),w=new Int32Array(shared);w[14]=0;w[15]=1;
 const name=n=>n+'-fixture-current';
 const ctx={window:{},ZemaRuntime:{settings:{mode:'lan'},features:{pad:shared}},ZemaLaunchChannels:{name},SharedArrayBuffer,Int32Array,Atomics,Map,String,performance:{now:()=>now},BroadcastChannel,
  addEventListener:(n,fn)=>events[n]=fn,setInterval:fn=>(tick=fn,1),clearInterval:()=>{},fetch:async(_,v)=>{notes.push(...JSON.parse(v.body).lines);return {};}};
 vm.createContext(ctx);vm.runInContext(source,ctx);events.DOMContentLoaded();
 const old=new BroadcastChannel('game-progress-fixture-old'),sender=new BroadcastChannel(name('game-progress')),receiver=new BroadcastChannel(name('game-progress'));receiver.onmessage=e=>{if(e.data.frontend)frontend++;};
 const pause=()=>new Promise(r=>setTimeout(r,40));
 try{
  old.postMessage({pct:76});await pause();w[18]++;tick();now=1600;w[18]++;tick();await pause();a.equal(frontend,0,'Old game progress must be ignored');
  sender.postMessage({pct:76,...(failure||{})});await pause();now=1700;w[18]++;tick();now=3300;w[18]++;tick();await pause();
  a.equal(frontend,failed?0:1);if(failed)a.ok(notes.some(n=>n.includes(failure.gpuInitFailed?'Graphics initialization failed':'Graphics device disconnected')));
 }finally{events.pagehide();old.close();sender.close();receiver.close();}
}
(async()=>{await test();await test({gpuInitFailed:true});await test({gpuLost:true});await test({gpuLost:''});console.log('PASS actual loading helper scoped progress, stale launch refusal and GPU failure blocking');})().catch(e=>{console.error(e);process.exitCode=1;});
'''
  p=subprocess.run(['node','-e',code,str(ROOT/'lan-loading.js')],capture_output=True,text=True,timeout=10)
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)

 def test_real_page_worker_graph_scoped_without_engine_or_storage_change(self):
  for mode in ['story','sandbox','lan']:
   page=serve_browser.index((MIRROR/'index.html').read_bytes(),mode).decode()
   self.assertIn(c.MARK,page);self.assertIn('new Worker(ZemaLaunchChannels.url(',page)
   self.assertNotRegex(page,c.LITERAL)
  entry=(ROOT/'entry.js').read_text()
  for name in ['profile-worker.js','network-worker.js']:
   self.assertIn("new Worker(ZemaLaunchChannels.url(base+'"+name+"'))",entry)
  for name in c.COUNTS:
   path=STAGE/name
   if name=='browser-features.js':path=ROOT/name
   if name=='engine-lan-browser.js':path=ROOT/'browser.js'
   data=path.read_bytes()
   if name in ['loader.js','wgpu_worker.js']:data=serve_browser.fps_transport(name,data)
   fixed=c.worker(name,data).decode();self.assertNotRegex(fixed,c.LITERAL)
   self.assertEqual(fixed.count('ZemaLaunchChannels.name('),sum(c.COUNTS[name].values()))
   if name=='loader.js':
    self.assertEqual(fixed.count('new Worker(ZemaLaunchChannels.url('),2)
    self.assertIn('mainScriptUrlOrBlob: ZemaLaunchChannels.url(',fixed)
   with self.assertRaises(ValueError):c.worker(name,fixed.encode())
   for old in ['gta5-userdata','zema-engine-lan-userdata-v1','zema-browser-story-gamedata-v1']:
    self.assertEqual(fixed.count(old),data.decode().count(old))
   with self.assertRaises(ValueError):c.worker(name,data.replace(b'new BroadcastChannel',b'new MissingChannel',1))
  self.assertEqual(c.worker('game.wasm',b'unchanged'),b'unchanged')

 def test_real_broadcast_channels_do_not_close_a_new_launch(self):
  code=r'''
const vm=require('node:vm'),a=require('node:assert/strict'),{BroadcastChannel}=require('node:worker_threads');
const boot=JSON.parse(process.argv[1]);
function scope(id,page=false){const loc=new URL('http://127.0.0.1:18887/b/loader.js?zgtaLaunch='+id),ctx={URL,location:loc,Set,Object,Error};if(page){ctx.document={};ctx.crypto={randomUUID:()=>id};}vm.runInNewContext(boot,ctx);return ctx.ZemaLaunchChannels;}
const old=scope('1'.repeat(32)),fresh=scope('2'.repeat(32)),peer=scope('2'.repeat(32));
a.notEqual(old.name('game-io'),fresh.name('game-io'));a.equal(fresh.name('game-io'),peer.name('game-io'));
a.throws(()=>scope('../bad'));a.throws(()=>fresh.name('private'));
a.throws(()=>fresh.url('https://elsewhere.example/game.js'));
const url=new URL(fresh.url('/b/game.js?console=1&log=1'));a.equal(url.searchParams.get('console'),'1');a.equal(url.searchParams.get('log'),'1');a.equal(url.searchParams.get('zgtaLaunch'),'2'.repeat(32));
a.equal(scope('12345678-1234-1234-1234-123456789abc',true).scope,'12345678123412341234123456789abc');
(async()=>{const sender=new BroadcastChannel(old.name('game-io')),receiver=new BroadcastChannel(fresh.name('game-io')),same=new BroadcastChannel(peer.name('game-io'));let closed=0;receiver.onmessage=e=>{if(e.data==='close')closed++;};
try{sender.postMessage('close');await new Promise(r=>setTimeout(r,100));a.equal(closed,0,'Old pagehide must not close the newer IO worker');same.postMessage('close');await new Promise(r=>setTimeout(r,100));a.equal(closed,1,'The matching page still closes its own IO worker');}finally{sender.close();receiver.close();same.close();}console.log('PASS old/new launch isolation and own-IO closure');})().catch(e=>{console.error(e);process.exitCode=1;});
'''
  p=subprocess.run(['node','-e',code,json.dumps(c.BOOT)],capture_output=True,text=True,timeout=10)
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)

if __name__=='__main__':unittest.main()
