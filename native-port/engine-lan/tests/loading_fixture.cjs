'use strict';
const assert=require('node:assert/strict'),{Tracker}=require('../lan-loading.js'),F=require('../browser-features.js');
const b=F.createPad(),w=new Int32Array(b),t=new Tracker(b);assert.equal(t.sample(true,0),false); // no native observations
w[14]=0;w[18]=1;assert.equal(t.sample(true,100),false); // never saw loading active
w[14]=1;w[15]=1;w[18]++;assert.equal(t.sample(true,200),false);
w[14]=0;for(let now=300;now<3000;now+=250){w[18]++;assert.equal(t.sample(false,now),false);} // no presented frame
for(let now=3000;now<4500;now+=250){w[18]++;assert.equal(t.sample(true,now),false);}w[18]++;assert.equal(t.sample(true,4500),true);assert.equal(t.sample(true,4750),false);assert.equal(w[14],0);assert.equal(w[15],1);
const stalled=new Tracker(b);assert.equal(stalled.sample(true,0),false);assert.equal(stalled.sample(true,1600),false); // stale engine state cannot uncover
console.log('NATIVE_LOADING_OBSERVATION_FRONTEND_GATE_PASS_NO_READY_FROM_STALE_OR_FRAME_ALONE');

// A fatal worker rejection must become a visible loading error, not a stuck %.
const fs=require('node:fs'),vm=require('node:vm'),events={},channels=new Map(),posted=[],batches=[];let tick,now=0;
class Channel{constructor(name){this.name=name;channels.set(name,this);}postMessage(value){posted.push([this.name,value]);}close(){}}
// The generated page supplies this bootstrap dependency; use deterministic names here.
const box={window:{},ZemaLaunchChannels:{name:name=>name},ZemaRuntime:{settings:{mode:'lan'},features:{pad:b}},Int32Array,Atomics,performance:{now:()=>now},BroadcastChannel:Channel,addEventListener:(n,f)=>events[n]=f,setInterval:f=>(tick=f,1),clearInterval:()=>{},fetch:async(_url,request)=>{batches.push(JSON.parse(request.body));},console};
vm.runInNewContext(fs.readFileSync(require.resolve('../lan-loading.js'),'utf8'),box);events.DOMContentLoaded();channels.get('game-crash').onmessage({data:{kind:'rejection',text:'TypeError: shared buffer refused\nprivate stack'}});const error=posted.find(([name,value])=>name==='game-progress'&&value.error)?.[1];assert(error);assert.match(error.error,/Game worker stopped: TypeError: shared buffer refused/);assert(!error.error.includes('private stack'));assert(!posted.some(([,value])=>value.frontend));
console.log('FATAL_WORKER_REJECTION_VISIBLE_WITHOUT_FALSE_READY_PASS');

// The real channel handler must retain GPU errors amid the observed audio flood.
for(let i=0;i<2000;i++)channels.get('game-log').onmessage({data:'[Audio_NorthAudio] Network Script 0: none'});
channels.get('game-log').onmessage({data:'[wgpu] validation error: world submit rejected'});
w[19]=5;w[20]=1;w[21]=2;tick();
assert(batches[0].lines.some(line=>line==='[session] native-state/players 5/1 (observation only)'));
assert(batches[0].lines.some(line=>line.includes('world submit rejected')));
assert.equal(batches[0].lines.filter(line=>line==='[Audio_NorthAudio] Network Script 0: none').length,1);
console.log('AUDIO_FLOOD_COALESCED_WITH_GPU_SIGNAL_PRESERVED_PASS');
(async()=>{await new Promise(resolve=>setImmediate(resolve));
channels.get('game-log').onmessage({data:'[wasm] Main waits on mutex 0x123 (waiters 1)'});
channels.get('game-log').onmessage({data:'[wgpu] initialization: requesting WebGPU device'});
tick();await new Promise(resolve=>setImmediate(resolve));
assert(batches.some(batch=>batch.lines.some(line=>line.includes('Main waits on mutex'))));
assert(batches.some(batch=>batch.lines.some(line=>line.includes('requesting WebGPU device'))));
console.log('STARTUP_LOCK_AND_GPU_INIT_DIAGNOSTICS_RETAINED_PASS');

// Reproduce the live per-frame spinner flood using the actual channel handler.
// Each first signal and repeat count survives while unrelated errors/waits arrive.
const spinner='[ui_spinner] CBusySpinner::Update - ms_CurrentBodyText = Joining GTA Online. ';
for(let i=0;i<20000;i++)channels.get('game-log').onmessage({data:spinner});
channels.get('game-log').onmessage({data:'[wgpu] validation error: retained after spinner flood'});
channels.get('game-log').onmessage({data:'[wasm] Main waits on mutex 0x456 (waiters 1)'});
now=5000;tick();await new Promise(resolve=>setImmediate(resolve));
const floodLines=batches.flatMap(batch=>batch.lines);
assert.equal(floodLines.filter(line=>line===spinner).length,1);
assert(floodLines.some(line=>line.includes('[diagnostic repeats] 19999 '+spinner.trim())));
assert(floodLines.some(line=>line.includes('retained after spinner flood')));
assert(floodLines.some(line=>line.includes('Main waits on mutex 0x456')));
// New messages after the window are recorded again, not permanently suppressed.
channels.get('game-log').onmessage({data:spinner});tick();await new Promise(resolve=>setImmediate(resolve));
assert.equal(batches.flatMap(batch=>batch.lines).filter(line=>line===spinner).length,2);
console.log('JOIN_SPINNER_FLOOD_COALESCED_WITH_COUNTS_ERRORS_AND_WAITS_PASS');
// Saturating the bounded dedup table must not suppress a new distinct failure.
for(let i=0;i<400;i++)channels.get('game-log').onmessage({data:'[script] unique diagnostic '+i});
channels.get('game-log').onmessage({data:'[wgpu] validation error: distinct after saturation'});
for(let i=0;i<12;i++){tick();await new Promise(resolve=>setImmediate(resolve));}
assert(batches.flatMap(batch=>batch.lines).some(line=>line.includes('distinct after saturation')));
console.log('BOUNDED_DEDUP_TABLE_SATURATION_PRESERVES_NEW_ERROR_PASS');




events.pagehide();
})().catch(error=>{console.error(error);process.exit(1);});
