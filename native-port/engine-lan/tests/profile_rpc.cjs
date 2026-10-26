'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {Worker,isMainThread,parentPort,workerData}=require('node:worker_threads');
const rpc=require('../profile-rpc.js'),online=require('../online.js');
if(!isMainThread){
  if(workerData.role==='owner'){
    const target=workerData.file;let expected=null;const keep=setInterval(()=>{},1000);
    const storage={async load(){try{expected=new Uint8Array(fs.readFileSync(target));return expected;}catch(e){if(e.code==='ENOENT')return null;throw e;}},async commit(bytes){let actual=null;try{actual=new Uint8Array(fs.readFileSync(target));}catch(e){if(e.code!=='ENOENT')throw e;}
      if((expected===null)!==(actual===null)||(expected&&Buffer.compare(Buffer.from(expected),Buffer.from(actual))))throw Error('Changed');
      if(expected)fs.writeFileSync(target+'.previous',expected,{mode:0o600});const tmp=target+'.tmp';fs.writeFileSync(tmp,bytes,{mode:0o600,flag:'wx'});fs.renameSync(tmp,target);expected=bytes.slice();return true;}};
    rpc.serve(workerData.buffer,storage,online.Profile,{id:123456,name:'Mac'},context=>parentPort.postMessage(context),status=>parentPort.postMessage(status)).catch(e=>parentPort.postMessage({error:e.message}));
    parentPort.on('message',m=>{if(m==='stop'){clearInterval(keep);process.exit(0);}});
  }else{
    const p=new rpc.Proxy(workerData.context);
    for(let i=0;i<64;i++)assert(p.setStat('p'+workerData.slot+':'+i,BigInt(workerData.slot*1000+i)));
    assert(p.put('f:char'+workerData.slot+'.save',Uint8Array.from([0,255,workerData.slot,128])));
    parentPort.postMessage('done');
  }
}else{
  const directory=process.argv[2],file=path.join(directory,'profile.zemapf');
  const start=()=>new Promise((resolve,reject)=>{const buffer=new SharedArrayBuffer(rpc.SIZE),owner=new Worker(__filename,{workerData:{role:'owner',buffer,file}});const statuses=[];owner.on('message',m=>{if(m.type==='profile-status')statuses.push(m);});owner.once('error',reject);owner.once('message',m=>m.error?reject(Error(m.error)):resolve({owner,context:m,statuses}));});
  (async()=>{
    let {owner,context,statuses}=await start();
    const children=Array.from({length:4},(_,i)=>new Worker(__filename,{workerData:{role:'writer',slot:i+1,context}}));
    await Promise.all(children.map(w=>new Promise((resolve,reject)=>{w.once('message',resolve);w.once('error',reject);})));
    const p=new rpc.Proxy(context),peer=new rpc.Proxy(context);p.markNewSlot(31,true);assert.equal(peer.newSlotMask(),-2147483648);peer.markNewSlot(31,false);assert.equal(p.newSlotMask(),0);for(let slot=1;slot<=4;slot++)for(let i=0;i<64;i++)assert.equal(p.stat('p'+slot+':'+i),BigInt(slot*1000+i));
    // No cloud-file commit: fallback character stats must reach disk on their own.
    const deadline=Date.now()+5000;let checkpointed=false;
    while(Date.now()<deadline){const saved=online.Profile.decode(fs.readFileSync(file));if(saved.stat('p3:7')===3007n&&saved.get('f:char3.save')){checkpointed=true;break;}await new Promise(resolve=>setTimeout(resolve,25));}
    assert(checkpointed,'Fallback stats were lost without an engine cloud commit');await new Promise(resolve=>setImmediate(resolve));assert(statuses.some(s=>s.state==='saved'&&s.characterFiles===4&&s.characterReads===0),'Saving storage must not claim the game loaded a character');
    const first=fs.readFileSync(file);owner.postMessage('stop');await new Promise(resolve=>owner.once('exit',resolve));
    ({owner,context,statuses}=await start());const resumed=new rpc.Proxy(context);
    assert.deepEqual(Buffer.from(resumed.encode()),first);assert.deepEqual([...resumed.get('f:char3.save')],[0,255,3,128]);await new Promise(resolve=>setImmediate(resolve));assert(statuses.some(s=>s.characterFiles===4&&s.characterReads===1),'Character load must reflect a real file read');
    assert(resumed.setStat('h12345678',7n));fs.writeFileSync(file,Buffer.from('external-change'));
    await new Promise(resolve=>setTimeout(resolve,1500));assert.equal(fs.readFileSync(file,'utf8'),'external-change');
    assert.throws(()=>resumed.commit());assert.equal(fs.readFileSync(file,'utf8'),'external-change');
    owner.postMessage('stop');await new Promise(resolve=>owner.once('exit',resolve));console.log('SHARED_PROFILE_4_WRITERS_DISK_RESUME_EXTERNAL_GUARD_PASS');
  })().catch(e=>{console.error(e);process.exit(1);});
}
