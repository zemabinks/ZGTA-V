'use strict';
const assert=require('node:assert/strict'),{Worker,isMainThread,parentPort,workerData}=require('node:worker_threads');
const rpc=require('../profile-rpc.js'),online=require('../online.js');
if(!isMainThread){
 let current=null,fail=false,hold=false,release=null,writes=0,active=0,maximum=0;
 const control={},buffer=workerData.buffer;
 const storage={load:async()=>current,commit:async bytes=>{
  writes++;active++;maximum=Math.max(maximum,active);
  try{if(hold){parentPort.postMessage({type:'blocked'});await new Promise(resolve=>release=resolve);}if(fail)throw Error('fixture disk failure');current=bytes.slice();return true;}
  finally{active--;}
 }};
 parentPort.on('message',m=>{
  if(m.type==='checkpoint')control.requestCheckpoint(m.id);
  else if(m.type==='configure'){fail=!!m.fail;hold=!!m.hold;parentPort.postMessage({type:'configured'});}
  else if(m.type==='release'){hold=false;release?.();release=null;}
  else if(m.type==='snapshot')parentPort.postMessage({type:'snapshot',current,writes,active,maximum});
 });
 rpc.serve(buffer,storage,online.Profile,{id:123456,name:'Lifecycle'},context=>parentPort.postMessage({type:'ready',context}),m=>parentPort.postMessage(m),control).catch(error=>parentPort.postMessage({type:'fatal',message:String(error)}));
}else(async()=>{
 const buffer=new SharedArrayBuffer(rpc.SIZE),worker=new Worker(__filename,{workerData:{buffer}}),messages=[],waiting=[];
 worker.on('message',m=>{messages.push(m);for(const w of [...waiting])if(w.match(m)){waiting.splice(waiting.indexOf(w),1);clearTimeout(w.timer);w.resolve(m);}});
 const wait=(type,predicate=()=>true)=>new Promise((resolve,reject)=>{const match=m=>m.type===type&&predicate(m),found=messages.find(match);if(found){resolve(found);return;}const w={match,resolve,timer:setTimeout(()=>reject(Error('Missing '+type)),5000)};waiting.push(w);});
 const configure=async value=>{messages.splice(0,messages.length,...messages.filter(m=>m.type!=='configured'));worker.postMessage({type:'configure',...value});await wait('configured');};
 const snapshot=async()=>{messages.splice(0,messages.length,...messages.filter(m=>m.type!=='snapshot'));worker.postMessage({type:'snapshot'});return wait('snapshot');};
 try{
  const ready=await wait('ready'),proxy=new rpc.Proxy(ready.context);assert(proxy.setStat('hdeadbeef',111n));
  await configure({hold:true});worker.postMessage({type:'checkpoint',id:1});await wait('blocked');
  worker.postMessage({type:'checkpoint',id:2});await new Promise(resolve=>setTimeout(resolve,30));
  assert(!messages.some(m=>m.type==='profile-checkpoint'),'No saved acknowledgement while durable write is blocked');
  worker.postMessage({type:'release'});assert.equal((await wait('profile-checkpoint',m=>m.id===1)).state,'saved');assert.equal((await wait('profile-checkpoint',m=>m.id===2)).state,'saved');
  let result=await snapshot();assert.equal(result.maximum,1);assert.equal(online.Profile.decode(result.current).stat('hdeadbeef'),111n);
  await configure({fail:true});assert(proxy.setStat('hdeadbeef',222n));worker.postMessage({type:'checkpoint',id:3});assert.equal((await wait('profile-checkpoint',m=>m.id===3)).state,'error');
  result=await snapshot();assert.equal(online.Profile.decode(result.current).stat('hdeadbeef'),111n,'Failed checkpoint keeps prior disk data');
  worker.postMessage({type:'checkpoint',id:4});assert.equal((await wait('profile-checkpoint',m=>m.id===4)).state,'error');
  await configure({fail:false});worker.postMessage({type:'checkpoint',id:5});assert.equal((await wait('profile-checkpoint',m=>m.id===5)).state,'saved');
  result=await snapshot();assert.equal(online.Profile.decode(result.current).stat('hdeadbeef'),222n,'Failure must not clear the dirty revision');
  const writes=result.writes;worker.postMessage({type:'checkpoint',id:6});assert.equal((await wait('profile-checkpoint',m=>m.id===6)).state,'saved');result=await snapshot();assert.equal(result.writes,writes,'Clean lifecycle request does not rewrite storage');assert.equal(result.maximum,1);
  // A request can also arrive during the automatic one-second disk await,
  // after its last notification but before the owner registers another wait.
  messages.splice(0,messages.length,...messages.filter(m=>m.type!=='blocked'));
  await configure({hold:true});assert(proxy.setStat('hdeadbeef',333n));await wait('blocked');
  worker.postMessage({type:'checkpoint',id:7});await new Promise(resolve=>setTimeout(resolve,30));assert(!messages.some(m=>m.type==='profile-checkpoint'&&m.id===7));
  worker.postMessage({type:'release'});assert.equal((await wait('profile-checkpoint',m=>m.id===7)).state,'saved');result=await snapshot();assert.equal(result.maximum,1);assert.equal(online.Profile.decode(result.current).stat('hdeadbeef'),333n);
  console.log('BROWSER_LIFECYCLE_ACTUAL_COMMIT_ACK_SERIALIZATION_DIRTY_FAILURE_RETRY_PASS');
 }finally{Atomics.store(new Int32Array(buffer),2,1);Atomics.notify(new Int32Array(buffer),1);await worker.terminate();}
})().catch(error=>{console.error(error);process.exitCode=1;});
