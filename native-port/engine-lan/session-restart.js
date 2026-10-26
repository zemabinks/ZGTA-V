/* Calls GTA's own zero-argument Public Session transition on a new script task.
 * No input synthesis, frontend navigation, live-thread stack edits or globals writes.
 */
(function(root){'use strict';
 const PIN={program_hash:1392012650,code_size:889405,statics:1544,argument_cells:4,entry:15844,end:21033,entry_sha256:'5c6be1369a9ff41d9ccfa3f0beea3e0a68c374a5ccb17ea200515c0121fcbd64',route_static:1399,route_count:4,category:14,subcategory:0,stack_capacity:4096};
 // This worker stays inside the game loop: Promise callbacks cannot advance a
 // queued engine action. Hash the bounded 5189-byte function synchronously.
 function sha256(bytes){
  const K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
  const n=bytes.length;if(n>65536)throw Error('Session digest limit');const data=new Uint8Array(Math.ceil((n+9)/64)*64);data.set(bytes);data[n]=128;const v=new DataView(data.buffer);v.setUint32(data.length-4,n*8);const h=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19],w=new Uint32Array(64),rr=(x,n)=>(x>>>n)|(x<<(32-n));
  for(let off=0;off<data.length;off+=64){for(let i=0;i<16;i++)w[i]=v.getUint32(off+i*4);for(let i=16;i<64;i++){const x=w[i-15],y=w[i-2];w[i]=(w[i-16]+(rr(x,7)^rr(x,18)^(x>>>3))+w[i-7]+(rr(y,17)^rr(y,19)^(y>>>10)))>>>0;}let[a,b,c,d,e,f,g,j]=h;for(let i=0;i<64;i++){const t1=(j+(rr(e,6)^rr(e,11)^rr(e,25))+((e&f)^(~e&g))+K[i]+w[i])>>>0,t2=((rr(a,2)^rr(a,13)^rr(a,22))+((a&b)^(a&c)^(b&c)))>>>0;j=g;g=f;f=e;e=(d+t1)>>>0;d=c;c=b;b=a;a=(t1+t2)>>>0;}for(const[i,x]of[a,b,c,d,e,f,g,j].entries())h[i]=(h[i]+x)>>>0;}
  return h.map(x=>x.toString(16).padStart(8,'0')).join('');
 }
 const REQUEST=60,ACK=61,STATUS=62;
 function request(shared){const w=new Int32Array(shared);if(shared.byteLength!==256)throw Error('Session protocol mismatch');if([1,2,3].includes(Atomics.load(w,STATUS)))return false;Atomics.store(w,STATUS,1);Atomics.add(w,REQUEST,1);return true;}
 function status(shared){return Atomics.load(new Int32Array(shared),STATUS);}
 function create({memory,exports,shared,mode,pin=PIN,now=()=>performance.now(),digest=sha256,note=()=>{}}){
  if(JSON.stringify(pin)!==JSON.stringify(PIN))throw Error('Session restart contract changed');
  const w=new Int32Array(shared);let job=null,epoch=0,ownedTask=0;
  const d=()=>new DataView(memory.buffer),p=(at,size)=>{if(typeof at!=='bigint'||at<=0n||at+BigInt(size)>BigInt(memory.buffer.byteLength))throw Error('Session pointer bounds');return Number(at);};
  const u32=at=>d().getUint32(p(at,4),true),u64=at=>d().getBigUint64(p(at,8),true),set32=(at,n)=>d().setUint32(p(at,4),n,true),fn=name=>{const f=exports['zema:features:'+name];if(typeof f!=='function')throw Error('Session command absent: '+name);return f;};
  function finish(result,message){if(result<0&&ownedTask){fn('SessionKillTask')(ownedTask);ownedTask=0;}epoch++;job=null;Atomics.store(w,STATUS,result);note(message);}
  function withScript(call){
   const tls=exports['zema:features:tls-base']?.value;if(typeof tls!=='bigint')throw Error('Session TLS unavailable');
   const active=p(tls+3088n,8),previous=d().getBigUint64(active,true),count=d().getUint16(15409712,true),list=u64(15409704n);if(count>1024)throw Error('Session script list changed');
   for(let i=0;i<count;i++){const t=u64(list+BigInt(i*8));if(!t)continue;p(t,648);if(u32(t+32n)>1)continue;let name='';for(let n=0;n<32;n++){const c=d().getUint8(Number(t)+428+n);if(!c)break;name+=String.fromCharCode(c);}if(name!=='freemode')continue;
    d().setBigUint64(active,t,true);try{if(!fn('NetworkGetThisScriptIsNetworkScript')())return false;if(job&&!job.oldFreemode)job.oldFreemode=u32(t+24n);call();return true;}finally{d().setBigUint64(active,previous,true);}
   }return false;
  }
  function inspect(program){
   p(program,128);if(u32(program+88n)!==PIN.program_hash||u32(program+28n)!==PIN.code_size||u32(program+36n)!==PIN.statics||u32(program+32n)!==PIN.argument_cells)throw Error('Session resource identity changed');
   const pages=u64(program+16n),bytes=new Uint8Array(PIN.end-PIN.entry);
   for(let n=0;n<bytes.length;){const off=PIN.entry+n,count=Math.min(bytes.length-n,16384-off%16384),base=u64(pages+BigInt(Math.floor(off/16384)*8))+BigInt(off%16384);bytes.set(new Uint8Array(memory.buffer,p(base,count),count),n);n+=count;}
   const initial=u64(program+48n);if(u32(initial+BigInt(PIN.route_static*8))!==PIN.route_count)throw Error('Session route array changed');return bytes;
  }
  function tick(){
   const seq=Atomics.load(w,REQUEST);
   if(!job&&seq!==Atomics.load(w,ACK)){Atomics.store(w,ACK,seq);if(mode!=='lan'){finish(-1,'Session restart is available in multiplayer.');return;}job={sequence:seq,started:now(),phase:'request',epoch:++epoch};}
   if(!job)return;
   try{
    if(now()-job.started>((job.phase==='task'||job.phase==='rejoin')?120000:30000)){finish(-2,'Session restart timed out. Use Find New Session manually.');return;}
    if(job.phase==='rejoin'){const count=d().getUint16(15409712,true),list=u64(15409704n);if(count>1024)throw Error('Session script list changed');for(let i=0;i<count;i++){const t=u64(list+BigInt(i*8));if(!t||u32(t+32n)>1||u32(t+24n)===job.oldFreemode)continue;const bytes=new Uint8Array(memory.buffer,p(t+428n,9),9);if(Array.from(bytes).join(',')!=='102,114,101,101,109,111,100,101,0')continue;const session=u64(29044456n);if(session&&u32(session+99916n)===5){finish(4,'GTA returned to the multiplayer session.');return;}}return;}
    if(job.phase==='task'){
     const t=fn('SessionGetTask')(job.id);if(!t||u32(t+32n)===2){job.phase='rejoin';note('GTA accepted the session restart; waiting for the new freemode task.');}else if(u32(t+32n)>2)finish(-3,'GTA rejected the restart task.');return;
    }
    withScript(()=>{
     if(job.phase==='request'){fn('SessionRequestScript')(PIN.program_hash);job.phase='load';Atomics.store(w,STATUS,2);}
     if(job.phase==='load'&&fn('SessionScriptLoaded')(PIN.program_hash)){
      const program=fn('SessionGetProgram')(PIN.program_hash),bytes=inspect(program);
      if(digest(bytes)!==PIN.entry_sha256){finish(-4,'Session restart resource changed.');return;}job.program=program;job.phase='create';
     }
     if(job.phase==='create'){
      const program=fn('SessionGetProgram')(PIN.program_hash);if(program!==job.program)throw Error('Session resource was replaced');
      const id=fn('SessionCreateTask')(PIN.program_hash,0n,0,PIN.stack_capacity,u64(program+96n));if(!id)throw Error('No session script task available');ownedTask=id;
      const t=fn('SessionGetTask')(id);p(t,648);if(u32(t+28n)!==PIN.program_hash||u32(t+32n)!==0||u32(t+36n)!==0)throw Error('New session task state changed');
      const stack=u64(t+192n),sp=u32(t+44n),fp=u32(t+40n);p(stack,PIN.stack_capacity*8);
      if(u32(t+104n)!==PIN.stack_capacity||u32(t+208n)!==PIN.statics-PIN.argument_cells||sp!==PIN.statics+1||fp!==PIN.statics||u32(stack+BigInt(PIN.route_static*8))!==PIN.route_count)throw Error('New session task stack changed');
      set32(stack+BigInt((PIN.route_static+1)*8),PIN.category);set32(stack+BigInt((PIN.route_static+2)*8),PIN.subcategory);set32(t+36n,PIN.entry);
      ownedTask=0;job.id=id;job.phase='task';job.started=now();Atomics.store(w,STATUS,3);note('Direct Public Session restart scheduled.');
     }
    });
   }catch(error){finish(-5,'Session restart refused: '+String(error));}
  }
  return {tick};
 }
 root.ZemaSessionRestart={pin:PIN,request,status,create,sha256};if(typeof module==='object')module.exports=root.ZemaSessionRestart;
})(globalThis);
