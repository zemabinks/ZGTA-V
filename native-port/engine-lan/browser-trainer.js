/* Offline cheats and private Engine LAN world tools. Engine calls run only in the post-ioPad engine-thread hook.
 * Native parity sources: EngineHost.c pg_gamepad_cheats/pg_process_vehicle_spawn.
 * A delivered cheat sequence is not confirmation that the game accepted a cheat. */
(function(root){'use strict';
 const SIZE=512,PAD=12840656,INPUT_DEVICE=24627136,PREFIX='zema:features:';
 const rows=[
 ['PAINKILLER','Invincibility (five minutes)','Player',[8192,64,8192,32768,8192,8,8192,32768,64,16]],
 ['TURTLE','Restore health and armour','Player',[32,4,16,2,64,128,32,8192,128,4,4,4]],
 ['TOOLUP','Weapons and ammunition','Player',[16,2,32768,4,64,8192,16,16384,128,4,4,4]],
 ['FUGITIVE','Raise wanted level','Player',[8,8,32,2,32768,8192,32768,8192,32768,8192]],
 ['LAWYERUP','Lower wanted level','Player',[8,8,32,2,8192,32768,8192,32768,8192,32768]],
 ['POWERUP','Recharge special ability','Player',[64,64,128,8,4,64,8192,32768,64]],
 ['CATCHME','Fast running','Player',[16,32768,8192,8192,1,4,128]],
 ['GOTGILLS','Fast swimming','Player',[32768,32768,4,8192,8192,2,32768,1,8192]],
 ['HOPTOIT','Super jump','Player',[32768,32768,16,16,8192,8192,32768,8192,128,8,2]],
 ['SKYFALL','Skyfall','Player',[4,1,8,2,32768,8192,32768,8192,4,1,8,2,32768,8192,32768,8192]],
 ['FLOATER','Moon gravity','World',[32768,32768,4,8,4,8192,32768,4,32768]],
 ['SLOWMO','Slow motion','World',[16,32768,8192,8192,128,2,8]],
 ['DEADEYE','Slow-motion aiming','Combat',[128,1,8,16,32768,128,1,8192,64]],
 ['MAKEITRAIN','Cycle weather','World',[2,64,4,4,1,1,1,128]],
 ['HOTHANDS','Explosive melee','Combat',[8192,32768,64,16,8,32,32,32,1]],
 ['INCENDIARY','Flaming ammunition','Combat',[4,8,128,8,32768,2,8,32768,128,8192,4,4]],
 ['HIGHEX','Explosive ammunition','Combat',[8192,128,64,32768,8,2,32768,8192,8192,4,4,4]],
 ['LIQUOR','Drunk mode','Player',[16,8192,8192,32768,8192,128,32,32768]],
 ['SKYDIVE','Give parachute','Player',[32768,8192,4,1,8,2,2,32768,32768,8192,4]],
 ['COMET','Spawn Comet','Vehicles',[8,32,2,8192,4,1,64,64,128,8]],
 ['RAPIDGT','Spawn Rapid GT','Vehicles',[2,4,32,8192,4,8,8192,32768,32,2]],
 ['VINEWOOD','Spawn limousine','Vehicles',[2,8192,1,32768,32768,8,4,32,8192]],
 ['TRASHED','Spawn Trashmaster','Vehicles',[32,8,32,8,32768,32768,8,4,32,8192]],
 ['BARNSTORM','Spawn stunt plane','Vehicles',[32,8192,4,1,32768,8,4,4,32768,32768,64,16]],
 ['BUZZOFF','Spawn Buzzard','Vehicles',[32,32,4,32,32,32,4,1,8,16,32,16]],
 ['FLYSPRAY','Spawn Duster','Vehicles',[8192,32768,8,8,8,32768,16,16,64,32,4,4]],
 ['BANDIT','Spawn BMX','Vehicles',[32768,32768,8192,8192,32768,8192,128,32,16,8,2]],
 ['ROCKET','Spawn PCJ-600','Vehicles',[8,8192,32768,8192,2,32768,8192,128,8192,1,4,4]],
 ['OFFROAD','Spawn Sanchez','Vehicles',[32,64,4,32,32,4,32,8,2,1,4,4]]
 ];
 const catalog=Object.freeze(rows.map(([code,label,category,buttons],index)=>Object.freeze({index,code,label,category,buttons:Object.freeze(buttons)})));
 // Kept for existing callers; all menus use the generated shared catalog.
 const vehicleCatalog=root.ZemaVehicleCatalog||(typeof module==='object'?require('./vehicle-catalog.js'):null);
 const vehicles=Object.freeze((vehicleCatalog?.vehicles||[]).filter(v=>v.kind!=='train').map(v=>Object.freeze({model:v.model,label:v.name,category:v.category})));
 const spawnRequired=Object.freeze(['PlayerPedId','DoesEntityExist','RequestModel','HasModelLoaded','SetModelAsNoLongerNeeded','GetEntityCoords','GetEntityHeading','CreateVehicle','IsPedInAnyVehicle','GetVehiclePedIsIn','TaskLeaveVehicle','ClearPedTasksImmediately','SetPedIntoVehicle','SetVehicleEngineOn','malloc','tls-base']);
 const ownershipRequired=['NetworkGetThisScriptIsNetworkScript','NetworkGetEntityIsNetworked','NetworkHasControlOfEntity'];
 const waypointRequired=Object.freeze(['PlayerPedId','DoesEntityExist','IsPedDeadOrDying','GetFirstBlipInfoId','DoesBlipExist','GetBlipInfoIdCoord','IsPedInAnyVehicle','GetVehiclePedIsIn','GetPedInVehicleSeat','IsNewLoadSceneActive','NewLoadSceneStartSphere','IsNewLoadSceneLoaded','NewLoadSceneStop','RequestCollisionAtCoord','GetGroundZFor3dCoord','SetEntityCoordsNoOffset','SetEntityVelocity','malloc','tls-base']);
 const required=Object.freeze([...new Set([...spawnRequired,...waypointRequired,...ownershipRequired])]);
 const states=new WeakMap(),availabilityCaches=new WeakMap();
 const PROBE_FIRST=16,PROBE_SLOTS=28,LOADING=19473636;
 function availability(buffer,model){
  let hash;try{hash=modelHash(model);}catch(_){return 'unknown';}if(!hash)return 'unknown';
  const w=sharedWords(buffer),epoch=Atomics.load(w,13);let cache=availabilityCaches.get(buffer);
  if(!cache||cache.epoch!==epoch){cache={epoch,values:new Map()};availabilityCaches.set(buffer,cache);}
  if(Atomics.load(w,14)!==1)return 'unknown';
  for(let n=0;n<PROBE_SLOTS;n++){const at=PROBE_FIRST+n*4,state=Atomics.load(w,at+1);if(state>=2){const h=Atomics.load(w,at)>>>0;if(cache.values.size>=4096&&!cache.values.has(h))cache.values.delete(cache.values.keys().next().value);cache.values.set(h,({2:'missing',3:'available',4:'unsupported',5:'unknown'})[state]);Atomics.store(w,at+1,0);}}
  if(cache.values.has(hash))return cache.values.get(hash);
  for(let n=0;n<PROBE_SLOTS;n++){const at=PROBE_FIRST+n*4;if(Atomics.load(w,at+1)===1&&(Atomics.load(w,at)>>>0)===hash)return 'checking';}
  for(let n=0;n<PROBE_SLOTS;n++){const at=PROBE_FIRST+n*4;if(Atomics.compareExchange(w,at+1,0,-1)===0){Atomics.store(w,at,hash|0);Atomics.store(w,at+1,1);return 'checking';}}
  return 'checking';
 }
 function report(text){let channel;try{if(typeof BroadcastChannel!=='function')return;channel=new BroadcastChannel('game-log');channel.postMessage('[world-tools] '+text);}catch(_){}finally{channel?.close();}}
 function sharedWords(buffer){if(!(buffer instanceof SharedArrayBuffer)||buffer.byteLength!==SIZE)throw Error('Invalid trainer buffer');return new Int32Array(buffer);}
 function createShared(){return new SharedArrayBuffer(SIZE);}
 function joaat(name){let n=0;for(const c of name.toLowerCase()){n=(n+c.charCodeAt(0))>>>0;n=(n+(n<<10))>>>0;n^=n>>>6;}n=(n+(n<<3))>>>0;n^=n>>>11;return(n+(n<<15))>>>0;}
 function modelHash(model){if(typeof model!=='string'||!/^([a-z][a-z0-9_]{0,62}|0x[0-9a-f]{1,8})$/i.test(model))throw Error('Use a model name of 1–63 letters, digits or underscores, starting with a letter, or a hexadecimal hash such as 0x1234');return /^0x/i.test(model)?parseInt(model.slice(2),16)>>>0:joaat(model);}
 // Single UI writer, engine-thread reader; only stable even revisions are read.
 function replacement(w,hash){Atomics.add(w,10,1);Atomics.store(w,11,hash|0);Atomics.add(w,10,1);}
 function pendingReplacement(w){return Atomics.load(w,10)!==Atomics.load(w,12);}
 function readReplacement(w){const version=Atomics.load(w,10);if((version&1)||version===Atomics.load(w,12))return null;const hash=Atomics.load(w,11)>>>0;return version===Atomics.load(w,10)?{version,hash}:null;}
 function request(buffer,command){
  const w=sharedWords(buffer),sequence=Atomics.load(w,0),result=Atomics.load(w,3);
  let type,arg=0;
  if(command?.type==='cheat'){const entry=catalog.find(c=>c.code===command.code);if(!entry)throw Error('Unknown cheat');type=1;arg=entry.index;}
  else if(command?.type==='spawn'){type=2;arg=modelHash(command.model);if(!arg)throw Error('Invalid model');}
  else if(command?.type==='waypoint')type=3;
  else throw Error('Unknown trainer command');
  const busy=sequence!==Atomics.load(w,4)||result===1||(sequence!==0&&result===0)||Atomics.load(w,8)||pendingReplacement(w);
  if(busy){
   if(type===2&&Atomics.load(w,1)===2){replacement(w,arg);report('vehicle replacement accepted');return status(buffer);}
   throw Error('Another game action is still running or cleaning up.');
  }
  Atomics.store(w,1,type);Atomics.store(w,2,arg|0);Atomics.store(w,3,0);Atomics.store(w,5,0);Atomics.store(w,9,0);Atomics.add(w,0,1);report('queued #'+Atomics.load(w,0)+' '+(type===3?'waypoint':type===2?'vehicle':'cheat'));return status(buffer);
 }
 function status(buffer){const w=sharedWords(buffer);return {sequence:Atomics.load(w,0),ack:Atomics.load(w,4),result:Atomics.load(w,3),detail:Atomics.load(w,5),ready:Atomics.load(w,6)===1,type:Atomics.load(w,1),cleanupPending:Atomics.load(w,8)!==0,replacementPending:pendingReplacement(w)&&Atomics.load(w,11)!==0,phase:Atomics.load(w,9)};}
 function cancel(buffer){const w=sharedWords(buffer);if(pendingReplacement(w))replacement(w,0);Atomics.add(w,7,1);const sequence=Atomics.load(w,0),ack=Atomics.load(w,4);if(sequence!==ack&&Atomics.compareExchange(w,4,ack,sequence)===ack){Atomics.store(w,5,0);Atomics.store(w,3,-5);}}
 function offline(mode){return mode==='story'||mode==='sandbox'||mode==='freeroam';}
 function create({memory,exports,shared,mode,voice,now=()=>performance.now()}){
  const w=sharedWords(shared);Atomics.store(w,14,0);for(let at=PROBE_FIRST;at<128;at++)Atomics.store(w,at,0);Atomics.add(w,13,1);let job=null,vectors=0,disposed=false,pendingCleanup=null,cancelled=Atomics.load(w,7);
  const fn=name=>{const f=exports[PREFIX+name];if(typeof f!=='function')throw Error('Missing engine export '+name);return f;};
  function view(){return new DataView(memory.buffer);}
  function ptr(n,length){n=typeof n==='bigint'?Number(n):n;if(!Number.isSafeInteger(n)||n<0||!Number.isSafeInteger(length)||length<0||n>memory.buffer.byteLength-length)throw Error('Trainer pointer out of bounds');return n;}
  function preflight(names){for(const name of names){if(name==='tls-base'){if(typeof exports[PREFIX+name]?.value!=='bigint')throw Error('Missing TLS');}else fn(name);}}
  function activeScript(callback){
   const raw=exports[PREFIX+'tls-base']?.value;if(typeof raw!=='bigint')throw Error('Missing engine TLS global');
   const active=ptr(raw+3088n,8),d=view(),previous=d.getBigUint64(active,true),threads=d.getBigUint64(ptr(15409704,8),true),count=d.getUint16(ptr(15409712,2),true);if(count>1024)throw Error('Invalid script list');let chosen=0n;
   for(let i=0;i<count;i++){const thread=d.getBigUint64(ptr(threads+BigInt(i*8),8),true);if(!thread)continue;const p=ptr(thread+428n,32);let name='';for(let j=0;j<32;j++){const c=d.getUint8(p+j);if(!c)break;if(c<32||c>126){name='';break;}name+=String.fromCharCode(c);}if(mode==='lan'){if(name==='freemode'){chosen=thread;break;}}else{if(name==='main'){chosen=thread;break;}if(!chosen&&name)chosen=thread;}}
   if(!chosen)return false;d.setBigUint64(active,chosen,true);try{if(mode==='lan'&&!fn('NetworkGetThisScriptIsNetworkScript')())return false;callback();}finally{view().setBigUint64(active,previous,true);}return true;
  }
  function cleanup(){
   if(!pendingCleanup)return true;
   try{if(!activeScript(()=>{
    if(pendingCleanup.modelRequested){fn('SetModelAsNoLongerNeeded')(pendingCleanup.hash|0);pendingCleanup.modelRequested=false;}
    if(pendingCleanup.sceneOwned){fn('NewLoadSceneStop')();pendingCleanup.sceneOwned=false;}
   }))return false;}catch(_){return false;}
   pendingCleanup=null;Atomics.store(w,8,0);return true;
  }
  function finish(result,detail=0){
   const old=job;job=null;
   report('finished #'+Atomics.load(w,0)+' '+((old?.type??Atomics.load(w,1))===3?'waypoint':(old?.type??Atomics.load(w,1))===2?'vehicle':'cheat')+' result='+result);
   if(old&&(old.modelRequested||old.sceneOwned)){pendingCleanup=old;Atomics.store(w,8,1);cleanup();}
   Atomics.store(w,9,0);Atomics.store(w,5,detail|0);Atomics.store(w,3,result);
  }
  function vector(at,x,y,z){const d=view();for(const [i,n]of[x,0,y,0,z,0].entries())d.setFloat32(at+4*i,n,true);}
  function storage(){if(!vectors){vectors=ptr(fn('malloc')(128n),128);if(!vectors)throw Error('Engine allocation failed');}}
  function valid(x,y,z){return [x,y,z].every(Number.isFinite)&&Math.abs(x)<=20000&&Math.abs(y)<=20000&&z>=-100&&z<=2000;}
  function controlled(entity){return mode!=='lan'||!fn('NetworkGetEntityIsNetworked')(entity)||!!fn('NetworkHasControlOfEntity')(entity);}
  function setPad(pad,bits){const p=ptr(pad,136),buffer=memory.buffer,buttons=new Uint32Array(buffer,p+12,1),axes=new Uint8Array(buffer,p+20,6);Atomics.store(buttons,0,bits);for(let i=0;i<4;i++)Atomics.store(axes,i,128);Atomics.store(axes,4,bits&1?255:0);Atomics.store(axes,5,bits&2?255:0);if(buffer.byteLength>=INPUT_DEVICE+4)Atomics.store(new Int32Array(buffer,INPUT_DEVICE,1),0,0);}
  function spawn(t){
   if(t-job.started>=30000){finish(-4);return;}
   Atomics.store(w,9,1);
   if(!activeScript(()=>{
    if(Atomics.load(w,14)===1&&typeof exports[PREFIX+'IsModelInCdImage']==='function'&&typeof exports[PREFIX+'IsModelAVehicle']==='function'&&(!fn('IsModelInCdImage')(job.hash|0)||!fn('IsModelAVehicle')(job.hash|0))){finish(-13);return;}
    fn('RequestModel')(job.hash|0);job.modelRequested=true;
    if(!fn('HasModelLoaded')(job.hash|0))return;
    if(pendingReplacement(w))return;
    const ped=fn('PlayerPedId')()>>>0;if(!ped||!fn('DoesEntityExist')(ped)){finish(-11);return;}if(!controlled(ped)){finish(-8);return;}
    storage();fn('GetEntityCoords')(BigInt(vectors),ped,1);const d=view(),x=d.getFloat32(vectors,true),y=d.getFloat32(vectors+8,true),z=d.getFloat32(vectors+16,true),heading=fn('GetEntityHeading')(ped);
    if(!valid(x,y,z)||!Number.isFinite(heading)){finish(-7);return;}
    const out=vectors+32,rad=heading*Math.PI/180;vector(out,x-Math.sin(rad)*4.5,y+Math.cos(rad)*4.5,z+.5);
    const net=mode==='lan'?1:0;let vehicle=fn('CreateVehicle')(job.hash|0,BigInt(out),heading,net,0,0)>>>0;
    if(!vehicle){view().setFloat32(out+16,z+1.2,true);vehicle=fn('CreateVehicle')(job.hash|0,BigInt(out),heading,net,0,0)>>>0;}
    if(!vehicle){finish(-12);return;}if(!controlled(vehicle)){finish(-8);return;}
    if(fn('IsPedInAnyVehicle')(ped,0)){const old=fn('GetVehiclePedIsIn')(ped,0)>>>0;if(old)fn('TaskLeaveVehicle')(ped,old,16);}
    fn('ClearPedTasksImmediately')(ped);fn('SetPedIntoVehicle')(ped,vehicle,-1);fn('SetVehicleEngineOn')(vehicle,1,1,0);finish(2,vehicle);
   }))Atomics.store(w,9,mode==='lan'?4:3);
  }
  function localEntity(){
   const ped=fn('PlayerPedId')()>>>0;if(!ped||!fn('DoesEntityExist')(ped)||fn('IsPedDeadOrDying')(ped,0))return {error:-11};
   if(!controlled(ped))return {error:-8};let vehicle=0;
   if(fn('IsPedInAnyVehicle')(ped,0)){vehicle=fn('GetVehiclePedIsIn')(ped,0)>>>0;if(!vehicle||!fn('DoesEntityExist')(vehicle)||(fn('GetPedInVehicleSeat')(vehicle,-1,0)>>>0)!==ped||!controlled(vehicle))return {error:-8};}
   return {ped,vehicle,entity:vehicle||ped};
  }
  function waypoint(t){
   if(t-job.started>=15000){finish(-4);return;}Atomics.store(w,9,2);
   if(!activeScript(()=>{
    const target=localEntity();if(target.error){finish(target.error);return;}
    if(!job.target){
     const blip=fn('GetFirstBlipInfoId')(8)>>>0;if(!blip||!fn('DoesBlipExist')(blip)){finish(-6);return;}
     storage();fn('GetBlipInfoIdCoord')(BigInt(vectors),blip);const d=view(),x=d.getFloat32(vectors,true),y=d.getFloat32(vectors+8,true),z=d.getFloat32(vectors+16,true);
     if(!valid(x,y,z)){finish(-7);return;}if(fn('IsNewLoadSceneActive')()){finish(-10);return;}
     if(!fn('NewLoadSceneStartSphere')(BigInt(vectors),150,0)){finish(-10);return;}
     job.sceneOwned=true;job.target=target;job.x=x;job.y=y;job.frames=0;
    }else if(target.ped!==job.target.ped||target.vehicle!==job.target.vehicle){finish(-9);return;}
    const heights=[0,100,250,500,800,1000];vector(vectors+32,job.x,job.y,heights[job.frames++%6]);fn('RequestCollisionAtCoord')(BigInt(vectors+32));
    if(!fn('IsNewLoadSceneLoaded')())return;
    vector(vectors+32,job.x,job.y,1000);view().setFloat32(vectors+124,NaN,true);
    if(!fn('GetGroundZFor3dCoord')(BigInt(vectors+32),BigInt(vectors+124),0,0))return;
    const z=view().getFloat32(vectors+124,true);if(!valid(job.x,job.y,z)||z>1000){finish(-7);return;}
    const checked=localEntity();if(checked.error){finish(checked.error);return;}if(checked.ped!==job.target.ped||checked.vehicle!==job.target.vehicle){finish(-9);return;}
    vector(vectors+64,job.x,job.y,z+(checked.vehicle?1.5:1));vector(vectors+96,0,0,0);
    fn('SetEntityVelocity')(checked.entity,BigInt(vectors+96));fn('SetEntityCoordsNoOffset')(checked.entity,BigInt(vectors+64),0,0,0);finish(2);
   }))Atomics.store(w,9,mode==='lan'?4:3);
  }
  function probeModels(){
   if(memory.buffer.byteLength<LOADING+4||new DataView(memory.buffer).getInt32(LOADING,true)!==0||typeof exports[PREFIX+'IsModelInCdImage']!=='function'||typeof exports[PREFIX+'IsModelAVehicle']!=='function'){Atomics.store(w,14,0);return;}
   let ready=false;activeScript(()=>{const ped=fn('PlayerPedId')()>>>0;if(!ped||!fn('DoesEntityExist')(ped))return;ready=true;Atomics.store(w,14,1);let done=0;
    for(let n=0;n<PROBE_SLOTS&&done<8;n++){const at=PROBE_FIRST+n*4;if(Atomics.load(w,at+1)!==1)continue;const hash=Atomics.load(w,at)|0;let state=5;try{state=!fn('IsModelInCdImage')(hash)?2:fn('IsModelAVehicle')(hash)?3:4;}catch(_){}Atomics.store(w,at+1,state);done++;}
   });if(!ready)Atomics.store(w,14,0);
  }
  const voiceWords=voice instanceof SharedArrayBuffer&&voice.byteLength===25984?new Int32Array(voice,0,16):null;
  const voiceView=voiceWords?new DataView(voice):null;let lastVoice=0;
  function voicePosition(t){
   if(!voiceWords||mode!=='lan'||t-lastVoice<100)return;lastVoice=t;let pos=null;
   try{if(Atomics.load(new Int32Array(memory.buffer),LOADING/4)===0)activeScript(()=>{const ped=fn('PlayerPedId')()>>>0;if(!ped||!fn('DoesEntityExist')(ped))return;storage();fn('GetEntityCoords')(BigInt(vectors+96),ped,1);const d=view();const x=d.getFloat32(vectors+96,true),y=d.getFloat32(vectors+104,true),z=d.getFloat32(vectors+112,true);if(valid(x,y,z))pos=[x,y,z];});}catch(_){}
   Atomics.add(voiceWords,4,1);for(let i=0;i<3;i++)voiceView.setFloat32(20+i*4,pos?.[i]||0,true);Atomics.store(voiceWords,8,Date.now()|0);Atomics.store(voiceWords,9,pos?1:0);Atomics.add(voiceWords,4,1);
  }
  function tick(pad=PAD){
   if(disposed||Number(pad)!==PAD)return;const t=now();if(!Number.isFinite(t))return;Atomics.store(w,6,1);
   voicePosition(t);
   try{probeModels();}catch(_){Atomics.store(w,14,0);}
   const swap=readReplacement(w);
   if(swap){
    if(!swap.hash){Atomics.store(w,12,swap.version);}
    else if(!job||job.type===2){
     if(job)finish(-5);
     Atomics.store(w,3,1);
     if(pendingCleanup&&!cleanup())return;
     const newest=readReplacement(w);if(!newest)return;
     if(!newest.hash){Atomics.store(w,12,newest.version);Atomics.store(w,3,-5);return;}
     Atomics.store(w,1,2);Atomics.store(w,2,newest.hash|0);Atomics.store(w,5,0);Atomics.store(w,9,0);
     Atomics.add(w,0,1);Atomics.store(w,3,0);Atomics.store(w,12,newest.version);
    }
   }
   if(pendingCleanup&&!cleanup())return;if(Atomics.load(w,8))return;
   const cancellation=Atomics.load(w,7);if(cancellation!==cancelled){cancelled=cancellation;if(job){if(job.type===1)setPad(pad,0);finish(-5);}return;}
   const seq=Atomics.load(w,0),ack=Atomics.load(w,4);
   if(seq!==ack&&!job&&Atomics.compareExchange(w,4,ack,seq)===ack){
    const type=Atomics.load(w,1),arg=Atomics.load(w,2);
    if((!offline(mode)&&mode!=='lan')||(type===1&&!offline(mode))){finish(-2);return;}
    if(type===1&&catalog[arg])job={type,entry:catalog[arg],started:t,index:-1,down:false,next:t+100};
    else if((type===2&&arg)||type===3){
     try{preflight(type===2?spawnRequired:waypointRequired);if(mode==='lan')preflight(ownershipRequired);}catch(_){finish(-3);return;}
     job={type,hash:arg>>>0,started:t};
    }else{finish(-1);return;}Atomics.store(w,3,1);
   }
   if(!job)return;
   try{
    if(job.type===2){spawn(t);return;}if(job.type===3){waypoint(t);return;}
    if(t-job.started>15000){setPad(pad,0);finish(-4);return;}
    if(t>=job.next){if(job.settling){setPad(pad,0);finish(2);return;}if(job.index<0){job.index=0;job.down=true;job.next=t+90;}else if(job.down){job.down=false;job.next=t+60;}else if(job.index+1<job.entry.buttons.length){job.index++;job.down=true;job.next=t+90;}else{job.settling=true;job.next=t+400;}}
    setPad(pad,job.down?job.entry.buttons[job.index]:0);
   }catch(_){if(job?.type===1){try{setPad(pad,0);}catch(_){}}finish(-3);}
  }
  return {tick,dispose(){if(job){if(job.type===1){try{setPad(PAD,0);}catch(_){}}finish(-3);}cleanup();disposed=true;Atomics.store(w,6,0);}};
 }
 function apply(memory,exports,buffer,mode,pad=PAD,now,voice){let state=states.get(buffer);if(state&&(state.memory!==memory||state.exports!==exports||state.mode!==mode)){state.engine.dispose();state=null;}if(!state){state={memory,exports,mode,engine:create({memory,exports,shared:buffer,mode,now,voice})};states.set(buffer,state);}state.engine.tick(pad);}
 const api={SIZE,PAD,catalog,vehicles,availability,required,spawnRequired,waypointRequired,createShared,request,status,cancel,joaat,modelHash,create,apply};root.ZemaTrainer=api;if(typeof module==='object')module.exports=api;
})(globalThis);
