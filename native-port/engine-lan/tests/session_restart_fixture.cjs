const assert=require('node:assert/strict');
const R=require('../session-restart.js');
const pin=R.pin;
const crypto=require('node:crypto');for(const n of [0,1,55,56,63,64,65,5189,65536]){const bytes=Buffer.alloc(n);for(let i=0;i<n;i++)bytes[i]=i%251;assert.equal(R.sha256(bytes),crypto.createHash('sha256').update(bytes).digest('hex'));}
function fixture({wrongHash=false,wrongStack=false,loaded=true,mode='lan'}={}){
 const memory=new WebAssembly.Memory({initial:512,maximum:512,shared:true}),shared=new SharedArrayBuffer(256),d=new DataView(memory.buffer),w=new Int32Array(shared),calls=[];
 const program=1000000n,initial=1100000n,pages=1200000n,code=1300000n,stack=2000000n,task=2100000n,freemode=2200000n,list=2300000n,tls=2400000n,session=2500000n;
 const s32=(p,n)=>d.setUint32(Number(p),n,true),s64=(p,n)=>d.setBigUint64(Number(p),n,true);let clock=0;
 s32(program+88n,pin.program_hash);s32(program+28n,pin.code_size);s32(program+36n,pin.statics);s32(program+32n,pin.argument_cells);s64(program+48n,initial);s64(program+16n,pages);s64(program+96n,program+600n);s32(initial+1399n*8n,4);s64(pages,code);s64(pages+8n,code+16384n);
 s64(tls+3088n,999n);s64(15409704n,list);d.setUint16(15409712,1,true);s64(list,freemode);s32(freemode+24n,5);s32(freemode+32n,0);new Uint8Array(memory.buffer,Number(freemode)+428,9).set(Buffer.from('freemode\0'));
 s64(29044456n,session);s32(session+99916n,5);
 const exports={'zema:features:tls-base':{value:tls}};
 const install=(name,fn)=>exports['zema:features:'+name]=(...args)=>{calls.push(name);return fn(...args);};
 install('NetworkGetThisScriptIsNetworkScript',()=>1);install('SessionRequestScript',()=>assert.equal(d.getBigUint64(Number(tls+3088n),true),freemode));install('SessionScriptLoaded',()=>loaded?1:0);install('SessionGetProgram',()=>program);
 install('SessionCreateTask',()=>{s32(task+24n,60);s32(task+28n,pin.program_hash);s32(task+32n,0);s32(task+36n,0);s32(task+104n,4096);s32(task+208n,1540);s32(task+44n,wrongStack?9:1545);s32(task+40n,1544);s64(task+192n,stack);s32(stack+1399n*8n,4);return 60;});
 install('SessionGetTask',()=>task);install('SessionKillTask',()=>s32(task+32n,2));
 const digest=()=>wrongHash?'00'.repeat(32):pin.entry_sha256;
 const core=R.create({memory,exports,shared,mode,digest,now:()=>clock});
 return {core,shared,d,w,calls,s32,task,freemode,stack,tls,setClock:x=>clock=x};
}
(async()=>{
 let f=fixture();assert(R.request(f.shared));assert(!R.request(f.shared));f.core.tick();await Promise.resolve();f.core.tick();assert.equal(f.d.getUint32(Number(f.task+36n),true),pin.entry);assert.equal(f.d.getUint32(Number(f.stack+1400n*8n),true),14);assert.equal(f.d.getUint32(Number(f.stack+1401n*8n),true),0);assert.equal(f.d.getBigUint64(Number(f.tls+3088n),true),999n);assert.equal(R.status(f.shared),3);assert.equal(f.d.getUint32(Number(f.freemode+36n),true),0);
 f.s32(f.task+32n,2);f.core.tick();assert.equal(R.status(f.shared),3,'task completion alone must not claim gameplay recovery');f.s32(f.freemode+24n,77);f.core.tick();assert.equal(R.status(f.shared),4);assert.equal(f.calls.filter(x=>x==='SessionCreateTask').length,1);
 f=fixture({wrongHash:true});R.request(f.shared);f.core.tick();await Promise.resolve();f.core.tick();assert.equal(R.status(f.shared),-4);assert(!f.calls.includes('SessionCreateTask'));
 f=fixture({wrongStack:true});R.request(f.shared);f.core.tick();await Promise.resolve();f.core.tick();assert.equal(R.status(f.shared),-5);assert(f.calls.includes('SessionKillTask'));
 f=fixture({mode:'story'});R.request(f.shared);f.core.tick();assert.equal(R.status(f.shared),-1);assert.equal(f.calls.length,0);
 f=fixture({loaded:false});R.request(f.shared);f.core.tick();f.setClock(30001);f.core.tick();await Promise.resolve();assert.equal(R.status(f.shared),-2);assert(!f.calls.includes('SessionCreateTask'));
 console.log('PASS: direct task, TLS restoration, duplicate admission, fresh-session completion, changed-resource refusal, owned-task cleanup, offline refusal and timeout.');
})().catch(error=>{console.error(error);process.exitCode=1;});
