/* Runs only after explicit navigation from Play. Hold a lease before any worker. */
'use strict';
const selected=ZemaLaunchSettings.decode(location.search);
selected.mode=location.pathname.split('/').pop();
const runtimeSettings=ZemaLaunchSettings.normalize(selected);
window.ZemaRuntime={settings:runtimeSettings,query:ZemaLaunchSettings.query(runtimeSettings,{width:innerWidth,height:innerHeight})};
window.ZemaRuntime.features={mode:runtimeSettings.mode,pad:ZemaBrowserFeatures.createPad(),trainer:ZemaTrainer.createShared(),voice:new SharedArrayBuffer(25984)};
window.ZemaGameReady=false;
ZemaBrowserFeatures.publish(window.ZemaRuntime.features.pad,null,runtimeSettings);
addEventListener('pagehide',()=>{ZemaTrainer.cancel(window.ZemaRuntime.features.trainer);ZemaBrowserFeatures.publish(window.ZemaRuntime.features.pad,null,runtimeSettings);const session=/^\/session\/([a-f0-9]{32})\//.exec(location.pathname);if(session&&window.ZemaLaunchLease)fetch('/zema-lab/session/release',{method:'POST',headers:{'Content-Type':'application/json','X-Zema-Lab':'1'},body:JSON.stringify({id:session[1],lease:window.ZemaLaunchLease}),keepalive:true}).catch(()=>{});});
let resolveAdmission;window.ZemaRuntimeAdmission=new Promise(resolve=>{resolveAdmission=resolve;});
window.ZemaRuntimeReady=new Promise(resolve=>{
 addEventListener('DOMContentLoaded',async()=>{
  if(!runtimeSettings.fill){const canvas=document.getElementById('canvas');canvas.style.cssText+=';width:min(100vw,177.7778vh);height:min(100vh,56.25vw);left:50%;top:50%;transform:translate(-50%,-50%)';}
  const fail=message=>{resolveAdmission(false);const p=document.createElement('section');p.style.cssText='position:fixed;inset:0;z-index:3000;background:#101b18;color:white;padding:60px;font:18px system-ui';const text=document.createElement('p');text.textContent=message;const back=document.createElement('a');back.href='/';back.textContent='Back to settings';back.style.color='#9ce8b9';p.append(text,back);document.body.append(p);};
  if(!crossOriginIsolated||!navigator.gpu||!navigator.locks){fail('Chrome needs WebGPU, shared memory and Web Locks on this local server. No game was started.');return;}
  const support=ZemaBrowserPerformance.engineSupport();
  if(!support.memory64||!support.typedFunctions){fail('This browser cannot run the current engine safely. Update Chrome: WebAssembly memory64 and typed function references are required. Your game files and saves are preserved.');return;}
  try{const adapter=await navigator.gpu.requestAdapter({powerPreference:"high-performance"});if(!adapter)throw Error('No WebGPU adapter is available. No game was started.');
   if(adapter.features && !adapter.features.has('texture-compression-bc'))throw Error('This GPU cannot render the game’s BC textures. This Android/browser device is not supported by the current renderer. Your saves are preserved.');
   await navigator.locks.request('zema-browser-game-v1',{ifAvailable:true},async lock=>{
    if(!lock){fail('Another lab game is open. Close it before starting a second session; saves were preserved.');return;}
    const end=new Promise(done=>addEventListener('pagehide',done,{once:true}));
    resolveAdmission(true);
    if(runtimeSettings.mode==='lan')await window.ZemaLanReady;
    resolve();await end;
   });
  }catch(error){fail(error.message);}
 });
});
