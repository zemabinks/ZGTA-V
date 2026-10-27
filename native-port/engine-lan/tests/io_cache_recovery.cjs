'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const payload=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const source=Uint8Array.from({length:1048576},(_,i)=>(i*17+(i>>>9))&255);
async function run(arm,kind){
 const messages=[],requests=[],timers=[];let writes=0,reads=0,storeBytes=0;
 const disk=new Uint8Array(4*1048576);
 class Channel{constructor(name){this.name=name;}postMessage(data){messages.push({name:this.name,data});}close(){}}
 const handle={write(data,{at}){writes++;if(kind==='quota'||kind==='parallel-quota'){const e=Error('No space left for browser data');e.name='QuotaExceededError';throw e;}if(kind==='short-write')return data.length-1;disk.set(data,at);storeBytes=Math.max(storeBytes,at+data.length);return data.length;},read(data,{at}){reads++;if(kind==='read-throw')throw Error('Cache read unavailable');if(kind==='short-read')return Math.max(0,data.length-1);data.set(disk.subarray(at,at+data.length));return data.length;},flush(){},close(){},getSize:()=>storeBytes};
 const context={self:{postMessage(){}},navigator:{},indexedDB:{open(){throw Error('Userdata must not be touched')}},BroadcastChannel:Channel,ZemaLaunchChannels:{name:n=>n+'-fixture'},fetch:async(url,init={})=>{
  if(url==='/log')return{};
  requests.push({url,range:init.headers?.Range});
  if(kind==='source-missing')return{status:404};
  const m=/bytes=(\d+)-(\d+)/.exec(init.headers?.Range||'');const start=m?Number(m[1]):0,end=m?Number(m[2])+1:source.length;
  let pos=start;
  return{status:m?206:200,body:{getReader(){return{async read(){await Promise.resolve();if(pos>=end)return{done:true};const next=Math.min(end,pos+32768),value=source.slice(pos,next);pos=next;return{done:false,value};},async cancel(){}};}}};
 },setTimeout(fn){timers.push(fn);return timers.length;},clearTimeout(){},setInterval(){throw Error('Unrequested stats timer')},performance,console,Map,Set,Math,Number,String,Error,Array,ArrayBuffer,DataView,Uint8Array,Int32Array,SharedArrayBuffer,Atomics};
 vm.createContext(context);
 vm.runInContext(payload[arm]+`\nself.audit={configure(buffer,handle){mem={buffer};HEAP32=new Int32Array(buffer);HEAPU8=new Uint8Array(buffer);table=0;files=[{path:'fixture.rpf',size:${source.length}}];base='/data/';sh=handle;jh={write(){throw Error('Cache journal must not be written by this test')},flush(){},close(){}};bc=new BroadcastChannel('game-progress');},serve,failed:()=>typeof cacheFailed!=='undefined'&&cacheFailed,entries:()=>index.size,memoryPending:()=>typeof memInflight!=='undefined'?memInflight.size:inflight.size,pending:()=>pendingJournal.length,flush:writeJournal};`,context);
 const memory=new SharedArrayBuffer(2*1048576),words=new Int32Array(memory),bytes=new Uint8Array(memory);const memoryOnly=kind==='parallel-memory';context.self.audit.configure(memory,memoryOnly?null:handle);
 const parallel=kind==='parallel-quota'||memoryOnly;const count=parallel?3:1;
 for(let i=0;i<count;i++){const w=16+16*i;words[w]=1;words[w+1]=0;words[w+2]=4096+i*8192;words[w+4]=65536+i*200000;words[w+6]=131072;}
 await Promise.all(Array.from({length:count},(_,i)=>context.self.audit.serve(i)));
 for(let i=0;i<count;i++){
  const w=16+16*i,result=Atomics.load(words,w+7);assert.equal(Atomics.load(words,w),2);
  const silentCorruption=arm==='original'&&kind==='short-write';
  const successful=kind!=='source-missing'&&(arm==='proposed'||kind==='normal'||silentCorruption||memoryOnly);
  assert.equal(result,successful?131072:-1,arm+' '+kind);
  if(successful){const actual=bytes.slice(words[w+4],words[w+4]+result),expected=source.slice(words[w+2],words[w+2]+result);if(silentCorruption)assert.notDeepEqual(actual,expected,'Baseline publishes unwritten cache bytes');else assert.deepEqual(actual,expected,arm+' '+kind+' exact bytes');}
 }
 assert.equal(context.self.audit.memoryPending(),0);
 if(arm==='proposed'){
  if(kind==='normal'){assert.equal(context.self.audit.failed(),false);assert(context.self.audit.entries()>0);}
  else if(memoryOnly){assert.equal(context.self.audit.failed(),false);assert.equal(writes,0);assert.equal(context.self.audit.entries(),0);const n=requests.length;await context.self.audit.serve(0);assert.equal(requests.length,n,'Repeated direct reads must reuse the bounded memory cache');assert.equal(requests.length,1,'Concurrent direct reads must share the actual source fetch');}
  else{assert.equal(context.self.audit.failed(),true);assert.equal(messages.filter(x=>String(x.data).includes('[io] cache bypass')).length,1);const before=writes;await context.self.audit.serve(0);assert.equal(writes,before,'Failed cache must not receive more writes');context.self.audit.flush();}
  if(kind==='quota'||kind==='parallel-quota'||kind==='short-write')assert.equal(context.self.audit.entries(),0,'Failed writes must not be indexed');
  if(kind==='source-missing'){assert(messages.some(x=>x.data?.error?.includes('HTTP 404')));assert(messages.some(x=>String(x.data).includes('fixture.rpf at 4096')));}
 }
 return{arm,kind,requests:requests.length,writes,reads};
}
(async()=>{const receipts=[];for(const kind of ['normal','parallel-memory','quota','short-write','short-read','read-throw','parallel-quota','source-missing'])for(const arm of ['original','proposed'])receipts.push(await run(arm,kind));console.log(JSON.stringify(receipts));console.log('IO_CACHE_EXACT_SOURCE_FALLBACK_CONCURRENCY_FAILURE_PASS');})().catch(e=>{console.error(e);process.exitCode=1;});
