'use strict';
const assert=require('node:assert/strict'),T=require(process.argv[2]);let checks=0;
function test(name,fn){fn();checks++;console.log('PASS '+name);}
function harness(mode='lan'){
 const memory=new WebAssembly.Memory({initial:400,maximum:400,shared:true}),d=new DataView(memory.buffer),shared=T.createShared(),calls=[],tls=100000n,thread=310000n,previous=555n;
 d.setBigUint64(Number(tls)+3088,previous,true);d.setBigUint64(15409704,200000n,true);d.setUint16(15409712,2,true);d.setBigUint64(200000,300000n,true);d.setBigUint64(200008,thread,true);new Uint8Array(memory.buffer,300428,5).set(Buffer.from('main\0'));new Uint8Array(memory.buffer,310428,9).set(Buffer.from('freemode\0'));
 const s={time:0,model:true,ped:42,vehicle:0,driver:42,waypoint:true,x:100,y:200,z:0,ground:20,groundFound:true,sceneLoaded:true,sceneActive:false,control:true,throwCreate:false,rejectRelease:false,networkScript:true};
 const exports={};
 for(const name of T.required){
  if(name==='tls-base'){exports['zema:features:'+name]=new WebAssembly.Global({value:'i64',mutable:true},tls);continue;}
  exports['zema:features:'+name]=(...args)=>{
   calls.push({name,args});const active=d.getBigUint64(Number(tls)+3088,true);assert.equal(active,mode==='lan'?thread:300000n,'native call must borrow the correct engine script');
   const vector=(at,x,y,z)=>{d.setFloat32(Number(at),x,true);d.setFloat32(Number(at)+8,y,true);d.setFloat32(Number(at)+16,z,true);};
   switch(name){
    case 'NetworkGetThisScriptIsNetworkScript':return s.networkScript?1:0;
    case 'malloc':assert.equal(args[0],128n);return 400000n;
    case 'PlayerPedId':return s.ped;
    case 'DoesEntityExist':return args[0]?1:0;
    case 'IsPedDeadOrDying':return 0;
    case 'NetworkGetEntityIsNetworked':return 1;
    case 'NetworkHasControlOfEntity':return s.control?1:0;
    case 'HasModelLoaded':return s.model?1:0;
    case 'SetModelAsNoLongerNeeded':if(s.rejectRelease)throw Error('temporary cleanup unavailable');return;
    case 'GetEntityCoords':assert.equal(args[1],s.ped);vector(args[0],10,20,30);return;
    case 'GetEntityHeading':return 90;
    case 'CreateVehicle':assert.deepEqual(args.slice(3),mode==='lan'?[1,0,0]:[0,0,0]);if(s.throwCreate)throw Error('fixture trap');return 88;
    case 'IsPedInAnyVehicle':return s.vehicle?1:0;
    case 'GetVehiclePedIsIn':return s.vehicle;
    case 'GetPedInVehicleSeat':assert.equal(args[0],s.vehicle);assert.equal(args[1],-1);return s.driver;
    case 'GetFirstBlipInfoId':assert.equal(args[0],8);return s.waypoint?7:0;
    case 'DoesBlipExist':return args[0]===7?1:0;
    case 'GetBlipInfoIdCoord':assert.equal(args[1],7);vector(args[0],s.x,s.y,s.z);return;
    case 'IsNewLoadSceneActive':return s.sceneActive?1:0;
    case 'NewLoadSceneStartSphere':assert.equal(s.sceneActive,false);assert.equal(args[1],150);s.sceneActive=true;return 1;
    case 'IsNewLoadSceneLoaded':return s.sceneLoaded?1:0;
    case 'NewLoadSceneStop':assert(s.sceneActive);s.sceneActive=false;return;
    case 'GetGroundZFor3dCoord':d.setFloat32(Number(args[1]),s.ground,true);return s.groundFound?1:0;
    case 'SetEntityCoordsNoOffset':assert(s.sceneLoaded&&s.groundFound);assert.equal(args[0],s.vehicle||s.ped);assert.deepEqual([0,8,16].map(i=>d.getFloat32(Number(args[1])+i,true)),[s.x,s.y,s.ground+(s.vehicle?1.5:1)]);return;
    default:return 0;
   }
  };
 }
 const engine=T.create({memory,exports,shared,mode,now:()=>s.time});
 return {s,d,shared,calls,exports,engine,run(ms=0){s.time+=ms;engine.tick(T.PAD);assert.equal(d.getBigUint64(Number(tls)+3088,true),previous);},count(name){return calls.filter(c=>c.name===name).length;}};
}
for(const mode of ['story','sandbox','lan'])test(mode+' spawn flags and model cleanup',()=>{const h=harness(mode);T.request(h.shared,{type:'spawn',model:'sultan'});h.run();assert.equal(T.status(h.shared).result,2);assert.equal(h.count('CreateVehicle'),1);assert.equal(h.count('SetModelAsNoLongerNeeded'),1);assert.equal(h.count('NetworkHasControlOfEntity'),mode==='lan'?2:0);});
test('LAN still refuses cheat codes and unknown modes refuse world tools',()=>{const h=harness();T.request(h.shared,{type:'cheat',code:'TURTLE'});h.run();assert.equal(T.status(h.shared).result,-2);assert.equal(h.calls.length,0);const other=harness('internet');T.request(other.shared,{type:'spawn',model:'sultan'});other.run();assert.equal(T.status(other.shared).result,-2);assert.equal(other.calls.length,0);});
test('no waypoint and missing export do not mutate world',()=>{const h=harness();h.s.waypoint=false;T.request(h.shared,{type:'waypoint'});h.run();assert.equal(T.status(h.shared).result,-6);assert.equal(h.count('NewLoadSceneStartSphere'),0);assert.equal(h.count('SetEntityCoordsNoOffset'),0);const other=harness();delete other.exports['zema:features:GetGroundZFor3dCoord'];T.request(other.shared,{type:'waypoint'});other.run();assert.equal(T.status(other.shared).result,-3);assert.equal(other.calls.length,0);});
test('waypoint waits for ground and scene, cancels concurrent requests, and cleans up',()=>{const h=harness();h.s.sceneLoaded=false;T.request(h.shared,{type:'waypoint'});h.run();assert.equal(T.status(h.shared).phase,2);assert.equal(h.count('SetEntityCoordsNoOffset'),0);assert.throws(()=>T.request(h.shared,{type:'spawn',model:'adder'}));h.s.sceneLoaded=true;h.s.groundFound=false;h.run(1000);assert.equal(h.count('SetEntityCoordsNoOffset'),0);h.s.groundFound=true;h.run(1);assert.equal(T.status(h.shared).result,2);assert.equal(h.count('SetEntityCoordsNoOffset'),1);assert.equal(h.count('NewLoadSceneStop'),1);assert.equal(T.status(h.shared).cleanupPending,false);});
test('controlled driver vehicle moves instead of passenger or another player',()=>{const h=harness();h.s.vehicle=77;T.request(h.shared,{type:'waypoint'});h.run();assert.equal(T.status(h.shared).result,2);const passenger=harness();passenger.s.vehicle=77;passenger.s.driver=999;T.request(passenger.shared,{type:'waypoint'});passenger.run();assert.equal(T.status(passenger.shared).result,-8);assert.equal(passenger.count('NewLoadSceneStartSphere'),0);const denied=harness();denied.s.control=false;T.request(denied.shared,{type:'spawn',model:'sultan'});denied.run();assert.equal(T.status(denied.shared).result,-8);assert.equal(denied.count('CreateVehicle'),0);assert.equal(denied.count('SetModelAsNoLongerNeeded'),1);});
test('timeout, cancelled scene, changed actor and invalid ground preserve position',()=>{
 for(const reason of ['timeout','cancel','changed','ground']){const h=harness();h.s.sceneLoaded=false;T.request(h.shared,{type:'waypoint'});h.run();
  if(reason==='timeout')h.run(15000);else if(reason==='cancel'){T.cancel(h.shared);h.run(1);}else if(reason==='changed'){h.s.ped=43;h.run(1);}else{h.s.sceneLoaded=true;h.s.ground=NaN;h.run(1);}
  assert.equal(T.status(h.shared).result,{timeout:-4,cancel:-5,changed:-9,ground:-7}[reason]);assert.equal(h.count('SetEntityCoordsNoOffset'),0);assert.equal(h.count('NewLoadSceneStop'),1);
 }
});
test('existing scene is never stopped or replaced',()=>{const h=harness();h.s.sceneActive=true;T.request(h.shared,{type:'waypoint'});h.run();assert.equal(T.status(h.shared).result,-10);assert.equal(h.count('NewLoadSceneStop'),0);assert.equal(h.s.sceneActive,true);});
test('model timeout without script defers cleanup and blocks a second request',()=>{const h=harness();h.s.model=false;T.request(h.shared,{type:'spawn',model:'sultan'});h.run();h.d.setUint16(15409712,0,true);h.run(30000);assert.equal(T.status(h.shared).result,-4);assert.equal(T.status(h.shared).cleanupPending,true);assert.throws(()=>T.request(h.shared,{type:'waypoint'}));assert.equal(h.count('SetModelAsNoLongerNeeded'),0);h.d.setUint16(15409712,2,true);h.run(1);assert.equal(T.status(h.shared).cleanupPending,false);assert.equal(h.count('SetModelAsNoLongerNeeded'),1);});
test('trap restores TLS and model cleanup; no script causes no allocation or native call',()=>{const h=harness();h.s.throwCreate=true;T.request(h.shared,{type:'spawn',model:'sultan'});h.run();assert.equal(T.status(h.shared).result,-3);assert.equal(h.count('SetModelAsNoLongerNeeded'),1);const other=harness();other.d.setUint16(15409712,0,true);T.request(other.shared,{type:'waypoint'});other.run();assert.equal(T.status(other.shared).phase,4);assert.equal(other.calls.length,0);other.run(15000);assert.equal(T.status(other.shared).result,-4);});
test('failed cleanup blocks admission until original owner can release it',()=>{const h=harness();h.s.rejectRelease=true;T.request(h.shared,{type:'spawn',model:'sultan'});h.run();assert.equal(T.status(h.shared).result,2);assert.equal(T.status(h.shared).cleanupPending,true);assert.throws(()=>T.request(h.shared,{type:'waypoint'}));h.s.rejectRelease=false;h.run(1);assert.equal(T.status(h.shared).cleanupPending,false);assert.equal(h.count('SetModelAsNoLongerNeeded'),2);});
test('two engine instances cannot move the waypoint entity twice',()=>{const h=harness();const other=T.create({memory:h.memory,exports:h.exports,shared:h.shared,mode:'lan',now:()=>h.s.time});T.request(h.shared,{type:'waypoint'});h.run();other.tick(T.PAD);assert.equal(h.count('SetEntityCoordsNoOffset'),1);assert.equal(h.count('NewLoadSceneStop'),1);});
test('LAN ignores offline main and waits for verified freemode before either action',()=>{
 for(const type of ['spawn','waypoint']){const h=harness();h.s.networkScript=false;T.request(h.shared,{type,model:'sultan'});h.run();assert.equal(T.status(h.shared).result,1);assert.equal(T.status(h.shared).phase,4);assert.equal(h.count('CreateVehicle'),0);assert.equal(h.count('RequestModel'),0);assert.equal(h.count('NewLoadSceneStartSphere'),0);h.s.networkScript=true;h.run(1);assert.equal(T.status(h.shared).result,2);assert.equal(h.count('CreateVehicle'),type==='spawn'?1:0);}
 const h=harness();h.d.setUint16(15409712,1,true);T.request(h.shared,{type:'spawn',model:'sultan'});h.run();assert.equal(T.status(h.shared).phase,4);assert.equal(h.calls.length,0);h.run(30000);assert.equal(T.status(h.shared).result,-4);
});
test('newest vehicle replaces an unstarted request without requesting old models',()=>{
 const h=harness();T.request(h.shared,{type:'spawn',model:'doesnotexist'});T.request(h.shared,{type:'spawn',model:'adder'});T.request(h.shared,{type:'spawn',model:'sultan'});
 assert.equal(h.calls.length,0);h.run();assert.equal(T.status(h.shared).result,2);assert.equal(h.count('CreateVehicle'),1);
 assert.deepEqual(h.calls.filter(c=>c.name==='RequestModel').map(c=>c.args[0]>>>0),[T.joaat('sultan')]);
});
test('newest streaming vehicle releases the old model before starting its replacement',()=>{
 const h=harness();h.s.model=false;T.request(h.shared,{type:'spawn',model:'doesnotexist'});h.run();
 T.request(h.shared,{type:'spawn',model:'adder'});T.request(h.shared,{type:'spawn',model:'sultan'});
 assert.throws(()=>T.request(h.shared,{type:'spawn',model:'bad input'}));assert.throws(()=>T.request(h.shared,{type:'spawn',model:'0x0'}));
 h.s.model=true;h.run(1);assert.equal(T.status(h.shared).result,2);assert.equal(h.count('CreateVehicle'),1);
 const steps=h.calls.filter(c=>['RequestModel','SetModelAsNoLongerNeeded'].includes(c.name)).map(c=>[c.name,c.args[0]>>>0]);
 assert.deepEqual(steps,[['RequestModel',T.joaat('doesnotexist')],['SetModelAsNoLongerNeeded',T.joaat('doesnotexist')],['RequestModel',T.joaat('sultan')],['SetModelAsNoLongerNeeded',T.joaat('sultan')]]);
});
test('replacement waits for owned cleanup after script loss and keeps accepting the latest choice',()=>{
 const h=harness();h.s.model=false;T.request(h.shared,{type:'spawn',model:'doesnotexist'});h.run();h.d.setUint16(15409712,0,true);
 T.request(h.shared,{type:'spawn',model:'adder'});h.run();assert.equal(h.count('CreateVehicle'),0);assert(T.status(h.shared).replacementPending);
 T.request(h.shared,{type:'spawn',model:'sultan'});assert.throws(()=>T.request(h.shared,{type:'waypoint'}));
 h.d.setUint16(15409712,2,true);h.s.model=true;h.run(1);assert.equal(T.status(h.shared).result,2);assert.equal(h.count('CreateVehicle'),1);
 assert.equal(h.calls.find(c=>c.name==='CreateVehicle').args[0]>>>0,T.joaat('sultan'));
});
test('failed model release cannot be bypassed by a replacement',()=>{
 const h=harness();h.s.model=false;T.request(h.shared,{type:'spawn',model:'doesnotexist'});h.run();h.s.rejectRelease=true;
 T.request(h.shared,{type:'spawn',model:'adder'});h.run();assert.equal(h.count('CreateVehicle'),0);
 T.request(h.shared,{type:'spawn',model:'sultan'});h.s.rejectRelease=false;h.s.model=true;h.run();assert.equal(T.status(h.shared).result,2);assert.equal(h.count('CreateVehicle'),1);
});
test('explicit cancel also clears a queued replacement',()=>{
 const h=harness();h.s.model=false;T.request(h.shared,{type:'spawn',model:'doesnotexist'});h.run();T.request(h.shared,{type:'spawn',model:'sultan'});T.cancel(h.shared);
 h.s.model=true;h.run();h.run();assert.equal(T.status(h.shared).result,-5);assert.equal(h.count('CreateVehicle'),0);assert.equal(h.count('SetModelAsNoLongerNeeded'),1);assert.equal(T.status(h.shared).replacementPending,false);
});
test('incomplete mailbox writes cannot create the old or partially written model',()=>{
 const h=harness();h.s.model=false;T.request(h.shared,{type:'spawn',model:'doesnotexist'});h.run();const w=new Int32Array(h.shared);
 Atomics.store(w,10,1);h.s.model=true;h.run();assert.equal(h.count('CreateVehicle'),0);
 Atomics.store(w,11,T.joaat('sultan')|0);Atomics.store(w,10,2);h.run();assert.equal(T.status(h.shared).result,2);assert.equal(h.count('CreateVehicle'),1);assert.equal(h.calls.find(c=>c.name==='CreateVehicle').args[0]>>>0,T.joaat('sultan'));
});

test('availability probes are read-only, loading-gated, cached per engine and missing spawn fails immediately',()=>{
 const h=harness();let probes=0;
 h.exports['zema:features:IsModelInCdImage']=hash=>{probes++;assert.equal(h.d.getBigUint64(103088,true),310000n);return (hash>>>0)!==T.joaat('oppressor2');};
 h.exports['zema:features:IsModelAVehicle']=()=>1;
 assert.equal(T.availability(h.shared,'oppressor2'),'unknown');h.run();
 assert.equal(T.availability(h.shared,'oppressor2'),'checking');const before=probes;
 assert.equal(T.availability(h.shared,'oppressor2'),'checking');assert.equal(probes,before,'UI never calls engine');
 h.run(1);assert.equal(T.availability(h.shared,'oppressor2'),'missing');assert.equal(h.count('RequestModel'),0);
 assert.equal(T.availability(h.shared,'sultan'),'checking');h.run(1);assert.equal(T.availability(h.shared,'sultan'),'available');
 h.d.setInt32(19473636,1,true);h.run(1);assert.equal(T.availability(h.shared,'oppressor2'),'unknown');
 h.d.setInt32(19473636,0,true);h.run(1);assert.equal(T.availability(h.shared,'oppressor2'),'missing');
 T.request(h.shared,{type:'spawn',model:'oppressor2'});h.run(1);assert.equal(T.status(h.shared).result,-13);assert.equal(h.count('RequestModel'),0);assert.equal(h.count('CreateVehicle'),0);
});

console.log(JSON.stringify({passed:checks,gameplayVerified:false}));
