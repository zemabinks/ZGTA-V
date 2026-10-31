/* One profile owner for all engine workers. No files/network on import. */
(function(root){'use strict';
  const LIMIT=8*1024*1024+36,DATA=4096,SIZE=DATA+LIMIT,PROTOCOL='zema-profile-rpc/1';
  const enc=new TextEncoder(),dec=new TextDecoder('utf-8',{fatal:true});
  class Proxy {
    constructor(context){if(!context||context.protocol!==PROTOCOL||!(context.buffer instanceof SharedArrayBuffer)||context.buffer.byteLength!==SIZE)throw Error('Shared profile context');
      this.buffer=context.buffer;this.words=new Int32Array(this.buffer,0,16);this.bytes=new Uint8Array(this.buffer);this.id=context.id;this.name=context.name;this.protocol=PROTOCOL;}
    call(op,key='',payload=new Uint8Array(),extra={}){
      if(typeof window!=='undefined')throw Error('Synchronous profile operations belong in an engine worker');
      const w=this.words,end=Date.now()+30000;let owned=false;
      try{
        while(Atomics.compareExchange(w,0,0,1)!==0){if(Atomics.load(w,2)||Date.now()>end)throw Error('Profile owner unavailable');Atomics.wait(w,0,1,10);}owned=true;
        if(Atomics.load(w,2))throw Error('Profile owner unavailable');
        const metadata=enc.encode(JSON.stringify({op,key,...extra}));if(metadata.length>2048||payload.length>LIMIT)throw Error('Profile request limit');
        this.bytes.set(metadata,64);this.bytes.set(payload,DATA);w[3]=metadata.length;w[4]=payload.length;Atomics.add(w,5,1);Atomics.store(w,1,1);Atomics.notify(w,1);
        while(Atomics.load(w,1)===1){const left=end-Date.now();if(left<=0){Atomics.store(w,2,1);Atomics.notify(w,1);throw Error('Profile operation timed out; restart the session');}Atomics.wait(w,1,1,left);}
        if(Atomics.load(w,1)!==2)throw Error('Profile storage refused the operation');
        const length=Atomics.load(w,6);if(length<0||length>LIMIT){Atomics.store(w,2,1);throw Error('Profile response limit');}
        return this.bytes.slice(DATA,DATA+length);
      }finally{if(owned){Atomics.store(w,1,0);Atomics.notify(w,1);Atomics.store(w,0,0);Atomics.notify(w,0,1);}}
    }
    newSlotMask(){return Atomics.load(this.words,7);}
    markNewSlot(slot,value){if(!Number.isInteger(slot)||slot<0||slot>=32)throw Error('Profile slot');if(value)Atomics.or(this.words,7,1<<slot);else Atomics.and(this.words,7,~(1<<slot));}
    get(key){const b=this.call('get',key);return b[0]===0?null:b.slice(1);}
    put(key,b){if(!(b instanceof Uint8Array)||b.length>1048576)return false;return this.call('put',key,b)[0]===1;}
    stat(key){const b=this.call('stat',key);return new DataView(b.buffer,b.byteOffset,8).getBigUint64(0,true);}
    setStat(key,value){return this.call('setStat',key,new Uint8Array(),{value:BigInt.asUintN(64,value).toString()})[0]===1;}
    deleteSlot(slot){this.call('deleteSlot','',new Uint8Array(),{slot});}
    encode(){return this.call('encode');}
    commit(){return this.call('commit')[0]===1;}
  }
  const equal=(a,b)=>a===null?b===null:b!==null&&a.length===b.length&&a.every((x,i)=>x===b[i]);
  class IndexedStore {
    constructor(db){this.db=db;this.expected=null;}
    static async open(){if(!root.indexedDB)throw Error('IndexedDB unavailable');const request=root.indexedDB.open('zema-engine-lan-profiles-v1',1);request.onupgradeneeded=()=>request.result.createObjectStore('profiles');
      const db=await new Promise((resolve,reject)=>{request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(Error('Profile database unavailable'));request.onblocked=()=>reject(Error('Profile database upgrade blocked'));});return new IndexedStore(db);}
    async load(){const t=this.db.transaction('profiles','readonly'),request=t.objectStore('profiles').get('current');const bytes=await new Promise((resolve,reject)=>{request.onsuccess=()=>resolve(request.result===undefined?null:new Uint8Array(request.result));request.onerror=()=>reject(Error('Profile read failed'));});this.expected=bytes;return bytes;}
    async commit(bytes){const prior=this.expected;
      await new Promise((resolve,reject)=>{const tx=this.db.transaction('profiles','readwrite',{durability:'strict'}),store=tx.objectStore('profiles'),read=store.get('current');
        read.onsuccess=()=>{const actual=read.result===undefined?null:new Uint8Array(read.result);if(!equal(actual,prior)){tx.abort();return;}if(prior!==null&&!equal(bytes,prior))store.put(prior,'previous');store.put(bytes,'current');};
        tx.oncomplete=resolve;tx.onabort=()=>reject(Error('Profile changed or write failed'));tx.onerror=()=>{};});this.expected=bytes.slice();return true;}
  }
  async function serve(buffer,storage,Profile,identity,ready,report=()=>{},control={}){
    if(!(buffer instanceof SharedArrayBuffer)||buffer.byteLength!==SIZE||typeof Atomics.waitAsync!=='function')throw Error('Shared profile worker unsupported');
    const w=new Int32Array(buffer,0,16),bytes=new Uint8Array(buffer);const saved=await storage.load();
    const profile=saved===null?new Profile(identity.id,identity.name):Profile.decode(saved);
    // The explicit Join name updates display metadata before any engine worker
    // receives its immutable context. The durable character ID/files/stats remain.
    const renamed=profile.name!==identity.name;
    if(!profile.rename(identity.name))throw Error('Profile name must be 1–16 English characters');
    if((saved===null||renamed)&&await storage.commit(profile.encode())!==true)throw Error('Profile name could not be saved');
    let requestedCheckpoint=0;
    // Control messages only wake the existing owner loop. They never start a
    // concurrent IndexedDB transaction or acknowledge data before commit.
    control.requestCheckpoint=id=>{if(!Number.isSafeInteger(id)||id<1)return;requestedCheckpoint=Math.max(requestedCheckpoint,id);Atomics.notify(w,1);};
    ready({protocol:PROTOCOL,buffer,id:profile.id,name:profile.name});
    // Fallback stats do not necessarily lead to a cloud-file save. Checkpoint
    // the complete shared profile even when the engine never calls commit().
    // Keep explicit cloud commits synchronous and retain the store's CAS guard.
    const isCharacter=key=>/(?:^|[_/:])char\d+\.save$/i.test(key);
    const fileKeys=new Set([...profile.values.keys()].filter(k=>k.startsWith('f:')));
    let characterFiles=[...fileKeys].filter(isCharacter).length;
    let savedRevision=profile.revision,lastAttempt=Date.now(),lastStatus=null,saveState='saved',loadedFiles=0,missingFiles=0,characterReads=0;
    const notify=state=>{saveState=state;
      const status={type:'profile-status',state,files:fileKeys.size,characterFiles,loadedFiles,missingFiles,characterReads};
      const key=JSON.stringify(status);if(key===lastStatus)return;lastStatus=key;try{report({...status,at:Date.now()});}catch{}};
    async function checkpoint(){lastAttempt=Date.now();if(await storage.commit(profile.encode())!==true)throw Error('Profile checkpoint refused');savedRevision=profile.revision;notify('saved');}
    notify('saved');
    while(!Atomics.load(w,2)){
      if(requestedCheckpoint){
        const id=requestedCheckpoint;requestedCheckpoint=0;
        try{if(profile.revision!==savedRevision)await checkpoint();report({type:'profile-checkpoint',id,state:'saved'});}
        catch{notify('error');report({type:'profile-checkpoint',id,state:'error'});}
        continue; // Recheck requests received while the transaction was awaited.
      }
      if(profile.revision!==savedRevision&&Date.now()-lastAttempt>=1000){try{await checkpoint();}catch{notify('error');}}
      if(requestedCheckpoint)continue; // A lifecycle request can arrive during the periodic disk await too.
      const state=Atomics.load(w,1);if(state!==1){await Atomics.waitAsync(w,1,state,profile.revision===savedRevision?Infinity:Math.max(1,1000-(Date.now()-lastAttempt))).value;continue;}
      try{
        const n=w[3],size=w[4];if(n<1||n>2048||size<0||size>LIMIT)throw Error('Profile request limit');
        const message=JSON.parse(dec.decode(bytes.slice(64,64+n))),payload=bytes.slice(DATA,DATA+size);let response;
        switch(message.op){
          case 'get':{const b=profile.get(message.key);response=b===null?new Uint8Array([0]):new Uint8Array(b.length+1);if(b!==null){response[0]=1;response.set(b,1);}if(message.key.startsWith('f:')){if(b===null)missingFiles++;else{loadedFiles++;if(isCharacter(message.key))characterReads++;}notify(saveState);}break;}
          case 'put':{const ok=profile.put(message.key,payload);if(ok&&message.key.startsWith('f:')&&!fileKeys.has(message.key)){fileKeys.add(message.key);if(isCharacter(message.key))characterFiles++;}response=new Uint8Array([ok?1:0]);break;}
          case 'stat':{response=new Uint8Array(8);new DataView(response.buffer).setBigUint64(0,profile.stat(message.key),true);break;}
          case 'setStat':response=new Uint8Array([profile.setStat(message.key,BigInt(message.value))?1:0]);break;
          case 'deleteSlot':profile.deleteSlot(message.slot);response=new Uint8Array();break;
          case 'encode':response=profile.encode();break;
          case 'commit':await checkpoint();response=new Uint8Array([1]);break;
          default:throw Error('Unsupported profile operation');
        }
        if(profile.revision!==savedRevision&&saveState!=='error')notify('pending');
        if(response.length>LIMIT||Atomics.load(w,2))throw Error('Profile response unavailable');bytes.set(response,DATA);Atomics.store(w,6,response.length);Atomics.store(w,1,2);
      }catch{notify('error');if(Atomics.load(w,2))return;Atomics.store(w,1,3);}Atomics.notify(w,1);
    }
  }
  const api={Proxy,IndexedStore,serve,SIZE,PROTOCOL};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ZemaProfileRPC=api;
})(globalThis);
