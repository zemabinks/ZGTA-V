/* Typed engine pad hook. Main-thread input crosses only a bounded shared buffer. */
(function(root){'use strict';
 const MAGIC=0x5a504144,SIZE=256,PRIMARY=12840656n,LAN='1f532d3c3d06f664c8698509652b9b19c646d1b5d574b93b4c399dd5e8261c79';
 const sessionPin={session_pointer:29044456,state_offset:99916,players_address:28504084,readers:[{index:83019,body_sha256:'0a1e9b65d28c5bac1d3b4d70380f6aece8d104705eb13f9c0ae8b32184cac305'},{index:54857,body_sha256:'11070da59d21321fdfd76f55bf1abe676b361aaf8c111beada00cad361f1dcee'}]};
 function observeSession(memory){
  // Read the same fields as the pinned engine readers. Never repair flags,
  // invoke game functions or treat local session state as peer synchronization.
  const v=new DataView(memory.buffer);if(v.byteLength<29044464)return {state:-2,players:-1};
  const pointer=v.getBigUint64(29044456,true),players=v.getInt32(28504084,true);
  let state=-1;
  if(pointer!==0n){const at=pointer+99916n;state=at%4n===0n&&at+4n<=BigInt(v.byteLength)?Atomics.load(new Int32Array(memory.buffer),Number(at)/4):-2;}
  return {state,players};
 }
 const buttonBits=[6,5,7,4,2,3,0,1,8,11,9,10,12,14,15,13];
 function createPad(){const b=new SharedArrayBuffer(SIZE),w=new Int32Array(b);w[0]=MAGIC;w[1]=1;w[11]=1;w[14]=-1;return b;}
 function words(buffer){if(!(buffer instanceof SharedArrayBuffer)||buffer.byteLength!==SIZE)throw Error('Analog pad buffer mismatch');const w=new Int32Array(buffer);if(Atomics.load(w,0)!==MAGIC||Atomics.load(w,1)!==1)throw Error('Analog pad protocol mismatch');return w;}
 function finite(value,fallback=0){return Number.isFinite(value)?value:fallback;}
 function state(pad,settings){
  const out={active:false,buttons:0,axes:[0,0,0,0],triggers:[0,0],targeting:settings.targetingMode??1};
  if(!pad?.connected||pad.mapping!=='standard'||!settings.controller)return out;
  out.active=true;const axis=i=>Math.max(-1,Math.min(1,finite(pad.axes?.[i]))),trigger=i=>Math.max(0,Math.min(1,finite(pad.buttons?.[i]?.value,pad.buttons?.[i]?.pressed?1:0)));
  out.triggers=[trigger(6),trigger(7)];
  for(let i=0;i<buttonBits.length;i++)if(pad.buttons?.[i]?.pressed)out.buttons|=1<<buttonBits[i];
  const aim=out.triggers[0]>.2,speed=(aim?settings.aimSensitivity:settings.lookSensitivity)/2.5;
  out.axes=[axis(0),axis(1),Math.max(-1,Math.min(1,axis(2)*speed)),Math.max(-1,Math.min(1,axis(3)*speed*(settings.invertY?-1:1)))];return out;
 }
 function publish(buffer,pad,settings,now=Date.now()){
  const w=words(buffer),s=state(pad,settings),seq=Atomics.load(w,2);if(seq&1)throw Error('Pad publisher contention');Atomics.store(w,2,seq+1);
  Atomics.store(w,3,s.active?1:0);Atomics.store(w,4,s.buttons);
  s.axes.forEach((n,i)=>Atomics.store(w,5+i,Math.round(n*32767)));s.triggers.forEach((n,i)=>Atomics.store(w,9+i,Math.round(n*65535)));
  Atomics.store(w,11,Number.isInteger(s.targeting)&&s.targeting>=0&&s.targeting<=3?s.targeting:1);
  Atomics.store(new BigInt64Array(buffer,64,1),0,BigInt(Math.trunc(now)));Atomics.store(w,2,seq+2);
 }
 function read(buffer,now=Date.now()){
  const w=words(buffer),seq=Atomics.load(w,2);if(seq&1)return null;const active=Atomics.load(w,3),bits=Atomics.load(w,4),axes=[5,6,7,8].map(i=>Atomics.load(w,i)),triggers=[9,10].map(i=>Atomics.load(w,i)),targeting=Atomics.load(w,11),stamp=Number(Atomics.load(new BigInt64Array(buffer,64,1),0));
  if(seq!==Atomics.load(w,2))return null;
  return {active:active===1&&now>=stamp&&now-stamp<=500,buttons:bits&65535,axes:axes.map(n=>Math.max(-32767,Math.min(32767,n))/32767),triggers:triggers.map(n=>Math.max(0,Math.min(65535,n))/65535),targeting};
 }
 function applyPad(memory,pad,shared,now=Date.now()){
  if(pad!==PRIMARY)return;const state=read(shared,now);if(!state)return;const p=Number(pad);if(p<0||p+136>memory.buffer.byteLength)throw Error('Pad memory bounds');
  if(state.active){let bits=state.buttons;const triggers=state.triggers.map(v=>Math.round(v*255));if(triggers[0]>30)bits|=1;if(triggers[1]>30)bits|=2;
   const ints=new Int32Array(memory.buffer),bytes=new Uint8Array(memory.buffer);Atomics.or(ints,(p+12)/4,bits);state.axes.forEach((v,i)=>Atomics.store(bytes,p+20+i,Math.round(127.5+v*127.5)));Atomics.store(bytes,p+24,triggers[0]);Atomics.store(bytes,p+25,triggers[1]);}
  Atomics.store(words(shared),13,1);return state;
 }
 function install(instance,memory,context,metadata=root.ZemaBrowserFeaturesModule){
  if(!metadata||metadata.format!=='zema-browser-features-v1'||!context||!['story','sandbox','lan'].includes(context.mode)||!(memory instanceof WebAssembly.Memory))throw Error('Explicit browser features context required');
  words(context.pad);if(!root.ZemaTrainer)throw Error('Trainer bridge absent');root.ZemaTrainer.status(context.trainer);if(typeof instance.exports['zema:features:tls-base']?.value!=='bigint')throw Error('Feature TLS global absent');const table=instance.exports.__indirect_function_table;
  if(!(table instanceof WebAssembly.Table))throw Error('Feature function table absent');
  for(const [alias,spec]of Object.entries(metadata.exports)){const fn=instance.exports['zema:features:'+alias];if(typeof fn!=='function'||fn.length!==spec.params.length)throw Error('Feature export ABI mismatch: '+alias);}
  const mode=metadata.input_sha256===LAN?'lan':context.mode;if(metadata.input_sha256!==LAN&&mode==='lan')throw Error('Offline engine cannot masquerade as multiplayer');let targeting=-1;const loading=metadata.loading_state;if(loading&&(loading.address!==19473636||loading.function_index!==34946||loading.body_sha256!=='e26ef5d2ee14a038c89052fd37041a9098b62a653a9a8270064a7ce4430042dc'))throw Error('Loading state pin mismatch');
  const observation=metadata.session_observation;
  if(observation&&(JSON.stringify(observation)!==JSON.stringify(sessionPin)||![LAN,'11ca8d2c04c5e843d18ff4aea4899d72c86973c6b031df334e67c446b2ae83e0'].includes(metadata.input_sha256)))throw Error('Session observation pin mismatch');
  const restart=mode==='lan'&&metadata.session_restart?root.ZemaSessionRestart.create({memory,exports:instance.exports,shared:context.pad,mode,pin:metadata.session_restart,note:message=>{let c;try{c=new BroadcastChannel('game-log');c.postMessage('[session] '+message);}finally{c?.close();}}}):null;
  let lastObservation=-Infinity;
  const callback=pad=>{
   const s=applyPad(memory,pad,context.pad);if(pad!==PRIMARY)return;
   if(s&&s.targeting!==targeting&&s.targeting>=0&&s.targeting<=3){instance.exports['zema:features:SetMenuPreference'](3,s.targeting);const v=new DataView(memory.buffer);if(v.byteLength<19571448)throw Error('Preference memory bounds');const listeners=v.getBigUint64(19571440,true);if(listeners!==0n)instance.exports['zema:features:SetProfilePreference'](listeners,0,s.targeting);targeting=s.targeting;}
   if(loading){if(memory.buffer.byteLength<loading.address+4)throw Error('Loading state bounds');const w=words(context.pad),active=Atomics.load(new Int32Array(memory.buffer),loading.address/4)!==0;Atomics.store(w,14,active?1:0);if(active)Atomics.store(w,15,1);Atomics.add(w,18,1);}
   if(mode==='lan'&&observation){const now=performance.now();if(now-lastObservation>=250){lastObservation=now;const s=observeSession(memory),w=words(context.pad);Atomics.add(w,21,1);Atomics.store(w,19,s.state);Atomics.store(w,20,s.players);Atomics.add(w,21,1);}}
   restart?.tick();
   root.ZemaTrainer.apply(memory,instance.exports,context.trainer,mode,pad,undefined,context.voice);
  };
  const callbacks={pad_update:callback},mh=metadata.memory_file_name;
  if(mh){if(mh.index!==1652||mh.body_sha256!=='3bf0f7632417fac9a02fa60cfb1e5fdee80c87d8955ee8124c61fdab1f3c9da6'||mh.slot!==metadata.hook.slot+1||!root.ZemaMemoryFilename)throw Error('Memory filename hook pin/helper mismatch');callbacks.memory_file_name=root.ZemaMemoryFilename.callback(memory);}
  const th=metadata.text_fallback;
  if(th){if(th.index!==77480||th.body_sha256!=='fd017869f336468fcfc1e7aff84596ed412b4f694dceeca6ec95dfb819b9c182'||th.slot!==metadata.hook.slot+2||th.original_export!=='zema:features:original_text'||!root.ZemaTextFallback)throw Error('Text fallback hook pin/helper mismatch');callbacks.text_get_internal=root.ZemaTextFallback.callback(memory,instance.exports[th.original_export],instance.exports['zema:features:malloc'],message=>{let channel;try{channel=new BroadcastChannel('game-log');channel.postMessage(message);}finally{channel?.close();}});}
  const bh=metadata.script_bank;
  if(bh){
   const expected=[['script_bank_request',21855,'325fa66ec6242aa144d7c0b950b7b1ab0e1672572ac8d7a51f371491137d33a3'],['bank_loading_status',7226,'17562dbe06dc555370e99be693f02ba9eb120c67096435322eac8f07fb391198']];
   if(!Array.isArray(bh)||bh.length!==2||!root.ZemaScriptBank)throw Error('Script bank hook pin/helper mismatch');
   for(let n=0;n<expected.length;n++){const h=bh[n],[field,index,hash]=expected[n];if(h.field!==field||h.index!==index||h.body_sha256!==hash||h.slot!==metadata.hook.slot+3+n||h.original_export!=='zema:features:original_'+field)throw Error('Script bank hook pin/helper mismatch');}
   Object.assign(callbacks,root.ZemaScriptBank.callbacks(instance.exports[bh[0].original_export],instance.exports[bh[1].original_export],bank=>{let channel;try{channel=new BroadcastChannel('game-log');channel.postMessage('[script-bank] failed optional bank bypassed during script request: '+bank);}finally{channel?.close();}}));
  }
  const gh=metadata.gamer_tag;
  if(gh){if(gh.index!==35212||gh.body_sha256!=='e0ace01496a38052316e53d340f57787bc8a041f1aec8febb7c072e5dfedbfbb'||gh.slot!==metadata.hook.slot+5||gh.original_export!=='zema:features:original_gamer_tag_render'||!root.ZemaGamerTags)throw Error('Gamer tag hook pin/helper mismatch');callbacks.gamer_tag_render=root.ZemaGamerTags.callback(memory,instance.exports[gh.original_export]);}
  const ih=metadata.blip_sprites;
  if(ih){if(ih.index!==35144||ih.body_sha256!=='78dc74cd2772bd5f8d7cbd6cc84c5c82884f3df16867caace594d039cb16263d'||ih.slot!==metadata.hook.slot+6||ih.original_export!=='zema:features:original_blip_asset_name'||!root.ZemaBlipSprites)throw Error('Blip diagnostic hook pin/helper mismatch');callbacks.blip_asset_name=root.ZemaBlipSprites.callback(memory,instance.exports[ih.original_export],message=>{let channel;try{channel=new BroadcastChannel('game-log');channel.postMessage(message);}finally{channel?.close();}});}
  const aux=new WebAssembly.Instance(new WebAssembly.Module(Uint8Array.from(metadata.auxiliary_wasm)),{zema:callbacks});
  table.set(metadata.table64?BigInt(metadata.hook.slot):metadata.hook.slot,aux.exports.pad_update);
  if(mh)table.set(metadata.table64?BigInt(mh.slot):mh.slot,aux.exports.memory_file_name);
  if(th)table.set(metadata.table64?BigInt(th.slot):th.slot,aux.exports.text_get_internal);
  if(bh)for(const h of bh)table.set(metadata.table64?BigInt(h.slot):h.slot,aux.exports[h.field]);
  if(gh)table.set(metadata.table64?BigInt(gh.slot):gh.slot,aux.exports.gamer_tag_render);
  if(ih)table.set(metadata.table64?BigInt(ih.slot):ih.slot,aux.exports.blip_asset_name);
 }
 function instance(module,imports,context,metadata=root.ZemaBrowserFeaturesModule){const result=new WebAssembly.Instance(module,imports);install(result,imports.env?.memory,context,metadata);if(metadata.deferred_start)result.exports['zema:features:start']();return result;}
 async function instantiate(bytes,imports,context,metadata=root.ZemaBrowserFeaturesModule){const input=bytes instanceof Uint8Array?bytes:new Uint8Array(bytes),hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',input)),n=>n.toString(16).padStart(2,'0')).join('');if(hash!==metadata?.patched_sha256)throw Error('Feature engine hash mismatch');const module=await WebAssembly.compile(input);return {module,instance:instance(module,imports,context,metadata)};}
 async function instantiateStreaming(response,imports,context,metadata){const r=await response;if(!r.ok)throw Error('Feature engine unavailable');return instantiate(await r.arrayBuffer(),imports,context,metadata);}
 const api={SIZE,MAGIC,createPad,state,publish,read,applyPad,observeSession,install,instance,instantiate,instantiateStreaming};root.ZemaBrowserFeatures=api;if(typeof module==='object')module.exports=api;
})(globalThis);
