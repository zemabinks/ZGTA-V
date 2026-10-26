'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(process.argv[2],'utf8'),flush=()=>new Promise(resolve=>setImmediate(resolve));
async function scenario({failure=false,admission=true,cancel=false,missing=false,restart=false,hostRestart=false}={}){
 const events={},posted=[],workers=[],redirects=[],stored=new Map(),nodes=[],presentations=[];let admit;
 const hostNodes=[],hostCalls=[],polls=new Map(),details=[],reconnect={},live={},badge={style:{},appendChild:n=>details.push(n),append:(...n)=>hostNodes.push(...n),querySelector:n=>({button:reconnect,output:live}[n])};
 class Worker{constructor(url){this.url=url;assert.equal(new URL(url).searchParams.get('zgtaLaunch'),'1'.repeat(32));workers.push(this);}postMessage(m){if(cancel)return;queueMicrotask(()=>{
  if(this.stopped)return;
  if(new URL(this.url).pathname.endsWith('profile-worker.js')){assert.equal(m.buffer.byteLength,4096+8*1024*1024+36);this.onmessage({data:{type:'ready',context:{protocol:'zema-profile-rpc/1',id:123456,name:'SavedName',buffer:m.buffer}}});}
  else if(m.type==='resume')this.onmessage({data:{type:'resumed'}});
  else{assert.equal(m.name,'SavedName');assert.equal(m.room,'LOS-SANTOS');assert.equal(m.url,'ws://127.0.0.1:47540/engine-lan');this.onmessage({data:failure?{type:'error',message:'Local engine-LAN connection failed'}:{type:'joined',context:{version:'zema-engine-lan/1',buffer:new SharedArrayBuffer(4096)}}});}
 });}terminate(){this.stopped=true;}}
 const features={test:'same bounded features context'},context={addEventListener:(name,f)=>events[name]=f,document:{body:{appendChild:n=>nodes.push(n)}},Worker,SharedArrayBuffer,TextEncoder,URL,URLSearchParams,ZemaLaunchChannels:{url:path=>'http://127.0.0.1:18887'+path+'?zgtaLaunch='+'1'.repeat(32)},ZemaEngineLan:require('../browser.js'),crossOriginIsolated:true,setTimeout,clearTimeout,setInterval:fn=>(polls.set(fn,fn),fn),clearInterval:fn=>polls.delete(fn),console,sessionStorage:{setItem:(k,v)=>stored.set(k,v)},location:{replace:u=>redirects.push(u),reload:()=>redirects.push("reload")},ZemaRuntime:{settings:{version:1,preset:'balanced',fps:60,mode:'lan',connection:'LAN',lobbyRole:hostRestart?'host':'join',relay:'ws://127.0.0.1:47540/engine-lan',room:'LOS-SANTOS',player:'Mac'},features},ZemaRuntimeAdmission:new Promise(r=>admit=r)};let hostState={owned:true,running:true,id:'fixture-lobby',peers:1,room:'LOS-SANTOS',connection:'LAN',join:'ws://127.0.0.1:47540/engine-lan',lan:'ws://192.168.1.2:47540/engine-lan'},failRestart=true;
 context.confirm=()=>true;context.fetch=async(url,options)=>{const action=url.split('/').pop(),body=JSON.parse(options.body);hostCalls.push(action);assert.equal(options.headers['X-Zema-Lab'],'1');if(action!=='status')assert.equal(body.id,'fixture-lobby');if(action==='stop')hostState={...hostState,running:false,can_restart:true};if(action==='restart'){if(failRestart){failRestart=false;return {ok:false,json:async()=>({error:'The previous lobby port is busy'})};}hostState={...hostState,running:true,can_restart:false};}return {ok:true,json:async()=>({...hostState})};};
 context.ZemaConnectionUI={mount:settings=>{assert.equal(settings.room,'LOS-SANTOS');const detail={},saveOutput={},hostDetails={},hostButton={},stopHost={},rejoin={hidden:true};detail.textContent='Room: '+settings.room+' · '+settings.relay;details.push(detail,saveOutput);hostNodes.push(hostButton,stopHost,hostDetails,rejoin);nodes.push(badge);return {live,reconnect,rejoin,hostDetails,hostButton,stopHost,saveOutput,render:(state,value)=>presentations.push({state,...value}),destroy:()=>presentations.push({state:'destroyed'})};}};
 context.window=context;if(missing)delete context.ZemaRuntime;
 vm.runInNewContext(source,context);
 const game={postMessage:(m,t)=>posted.push({m,t})},canvas={},transfer=[canvas];
 const pending=context.ZemaLabLaunch(game,{args:['-nonetwork','-rootdir=/game/','-wasmstartchoice=0'],keepThreads:1},transfer).catch(e=>e);
 assert.equal(workers.length,0);const startup=events.DOMContentLoaded();assert.equal(workers.length,0);
 if(missing){await startup;assert.equal(new URLSearchParams(redirects[0].split('?')[1]).get('lan'),'failed');assert.equal(posted.length,0);await pending;return;}
 admit(admission);await flush();
 if(cancel){assert.equal(workers.length,1);events.pagehide();await startup;assert(workers.every(w=>w.stopped));assert.equal(redirects.length,0);assert.equal(posted.length,0);return;}
 await startup;
 if(!admission){assert.equal(workers.length,0);assert.equal(posted.length,0);assert.equal(redirects.length,0);events.pagehide();return;}
 await pending;
 assert.equal(workers.length,2);
 if(failure){assert.equal(posted.length,0);assert.equal(nodes.length,0);assert.equal(new URLSearchParams(redirects[0].split('?')[1]).get('lan'),'failed');const retry=new URLSearchParams(redirects[0].split('?')[1]);assert.equal(retry.get('preset'),'balanced');assert.equal(retry.get('fps'),'60');assert.equal(retry.get('mode'),'lan');assert.equal(retry.get('room'),'LOS-SANTOS');assert.match(JSON.parse(stored.get('zema-browser-lan-error-v1')).message,/connection failed/);assert(workers.every(w=>w.stopped));return;}
 assert.equal(details.length,2);assert.equal(details[0].textContent,'Room: LOS-SANTOS · ws://127.0.0.1:47540/engine-lan');assert.match(details[1].textContent,/Checking stored character/);workers[0].onmessage({data:{type:'profile-status',state:'error'}});assert.match(details[1].textContent,/save failed/);workers[0].onmessage({data:{type:'profile-status',state:'pending'}});assert.match(details[1].textContent,/Saving/);workers[0].onmessage({data:{type:'profile-status',state:'saved',characterFiles:0,characterReads:0}});assert.match(details[1].textContent,/has not saved a character file/);workers[0].onmessage({data:{type:'profile-status',state:'saved',characterFiles:1,characterReads:0}});assert.match(details[1].textContent,/not yet read/);workers[0].onmessage({data:{type:'profile-status',state:'saved',characterFiles:1,characterReads:1}});assert.match(details[1].textContent,/stored and read by the game/);assert.equal(redirects.length,0);assert.equal(nodes.length,1);assert.equal(posted.length,1);assert.equal(posted[0].m.keepThreads,7);assert.equal(posted[0].m.engineLan.profile.name,'SavedName');assert.equal(posted[0].m.engineLan.features,features);assert.equal(posted[0].t,transfer);assert(!posted[0].m.args.includes('-nonetwork'));assert(posted[0].m.args.includes('-wasmstartchoice=1'));assert(!posted[0].m.args.includes('-wasmstartchoice=0'));
 if(hostRestart){
  const [detailsButton,toggle,status]=hostNodes;
  assert.match(status.textContent,/Hosting on this computer/,'Host details load after admission without clicking');
  assert.equal(polls.size,1);hostState.peers=2;await [...polls.values()][0]();assert.match(status.textContent,/2 player\(s\)/);
  context.document.hidden=true;let calls=hostCalls.length;await [...polls.values()][0]();assert.equal(hostCalls.length,calls,'Hidden tabs do not poll');context.document.hidden=false;
  await detailsButton.onclick();assert.match(status.textContent,/Hosting on this computer/);
  await toggle.onclick();assert.equal(toggle.textContent,'Start hosting again');assert.equal(toggle.disabled,false);assert.equal(hostState.running,false);
  await toggle.onclick();assert.match(status.textContent,/port is busy/);assert.equal(toggle.textContent,'Start hosting again');assert.equal(toggle.disabled,false);
  await Promise.all([toggle.onclick(),toggle.onclick()]);await flush();assert.equal(hostCalls.filter(x=>x==='restart').length,2,'Duplicate action must be ignored');assert.equal(toggle.textContent,'Stop hosting');assert.equal(hostState.running,true);assert.match(live.textContent,/host connection is restored/);assert.equal(workers.length,2);assert.equal(posted.length,1);assert.equal(redirects.length,0,'Hosting restart preserves the running game');
  hostState.room='OTHER';await toggle.onclick();assert.equal(hostCalls.filter(x=>x==='stop').length,1,'Never stop another lobby');assert.equal(toggle.disabled,true);assert.match(status.textContent,/Another lobby was left running/);
 }
 workers[1].onmessage({data:{type:'status',state:'disconnected',message:'Disconnected'}});assert.equal(reconnect.disabled,false);reconnect.onclick();await flush();assert.equal(reconnect.disabled,true);assert.match(live.textContent,/host connection is restored/);assert.equal(workers.length,2);assert.equal(posted.length,1);
 assert.match(live.textContent,/Find New Session/);assert.match(live.textContent,/without reloading/);assert.equal(presentations.at(-1).state,'recovered');assert.equal(hostNodes.at(-1).hidden,false,'A working transport must not hide gameplay recovery');
 workers[1].onmessage({data:{type:'status',state:'connected',message:'LAN connected'}});assert.equal(hostNodes.at(-1).hidden,false,'Later transport status must not conceal the rejoin action');

 if(restart){
  workers[1].onmessage({data:{type:'error',operation:'resume',code:'transport',message:'Host is still starting'}});
  assert.deepEqual(redirects,[],'A temporary host failure must keep the running game');assert.equal(posted.length,1);assert.equal(hostNodes.at(-1).hidden,false);
  reconnect.onclick();await flush();assert.match(live.textContent,/host connection is restored/);assert.equal(redirects.length,0);
 }else{
  const fallback=hostNodes.at(-1);
  workers[0].onmessage({data:{type:'profile-status',state:'error'}});
  workers[1].onmessage({data:{type:'error',operation:'resume',code:'address-in-use',message:'Original address occupied'}});assert.equal(reconnect.textContent,'Reconnect');assert.equal(fallback.hidden,false);assert.equal(redirects.length,0,'Conflict never reloads automatically');fallback.onclick();
  assert.equal(redirects.length,0);assert.equal(reconnect.disabled,false);assert.match(live.textContent,/storage needs attention/);
  workers[0].onmessage({data:{type:'profile-status',state:'saved',characterFiles:0}});fallback.onclick();assert.equal(redirects.length,0);assert.equal(reconnect.disabled,false);assert.match(live.textContent,/not saved a character/);
  workers[0].onmessage({data:{type:'profile-status',state:'pending',characterFiles:1}});fallback.onclick();assert.equal(redirects.length,0);assert.equal(reconnect.disabled,true);
  workers[0].onmessage({data:{type:'profile-status',state:'saved',characterFiles:1,characterReads:1}});assert.deepEqual(redirects,['reload']);assert.equal(posted.length,1,'A changed relay must never be injected into the running engine');
 }
 events.pagehide();assert(workers.every(w=>w.stopped));assert.equal(polls.size,0,"Host refresh timer is released");assert.equal(presentations.at(-1).state,"destroyed");
}
(async()=>{await scenario();await scenario({restart:true});await scenario({hostRestart:true});await scenario({failure:true});await scenario({admission:false});await scenario({cancel:true});await scenario({missing:true});console.log('EXPLICIT_SHARED_PROFILE_AND_LAN_GAME_LAUNCH_PASS single-screen success failure admission cancellation direct-link');})().catch(e=>{console.error(e);process.exit(1);});
