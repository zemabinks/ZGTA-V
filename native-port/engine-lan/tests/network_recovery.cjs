'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(process.argv[2],'network-worker.js'),'utf8');
function worker(Client){
 const messages=[];let now=0;
 const context={self:{postMessage:m=>messages.push(m)},importScripts:()=>{},performance:{now:()=>now},setTimeout:(fn,ms)=>{assert(ms>0&&ms<=2000);now+=ms;queueMicrotask(fn);},ZemaEngineLan:{PROTOCOL:'zema-engine-lan/1',Client,SharedLan:class{constructor(){this.buffer=new SharedArrayBuffer(4096);}}},SharedArrayBuffer};
 vm.runInNewContext(source,context);return {messages,context,send:type=>context.self.onmessage({data:{type}}),elapsed:()=>now};
}
async function scenario(failures,code){
 let attempts=0,disconnects=0;const timeouts=[];
 class Client {
  disconnect(){disconnects++;this.status?.('disconnected','Transport closed');}
  async connect(timeout){timeouts.push(timeout);if(++attempts===1)return {vip:1};if(failures-->0)throw Object.assign(Error('Host is not ready'),code?{code}:{});return {vip:1};}
 }
 const w=worker(Client);await w.send('connect');const initial=w.messages[0].context;
 await w.send('resume');assert.equal(w.messages.filter(m=>m.type==='joined').length,1);
 assert(!w.messages.some(m=>m.type==='status'&&m.state==='disconnected'),'Reconnect button must not flicker between internal retries');
 assert.equal(w.messages[0].context,initial,'Never replace the live engine adapter');
 assert(timeouts.slice(1).every(ms=>ms>=1&&ms<=15000));
 if(code){assert.equal(attempts,2);assert.equal(w.elapsed(),0);assert.equal(w.messages.at(-1).code,code);}
 else if(failures>0){assert.equal(w.elapsed(),60000);assert(attempts<40);assert.equal(w.messages.at(-1).type,'error');}
 else {assert.equal(w.messages.at(-1).type,'resumed');assert(disconnects>=1);assert(w.elapsed()<60000);if(attempts>15)assert(w.elapsed()>26000,'Recover across the observed 26-second host startup gap');}
}
(async()=>{
 await scenario(2);await scenario(18);await scenario(100);await scenario(1,'address-in-use');await scenario(1,'identity-changed');
 let complete,started=0,stopped=0;
 class PendingClient {disconnect(){stopped++;}connect(){started++;return started===1?Promise.resolve({vip:1}):new Promise(resolve=>complete=resolve);}}
 const pending=worker(PendingClient);await pending.send('connect');
 const one=pending.send('resume'),two=pending.send('resume');assert.equal(started,2);assert.equal(stopped,1);complete({vip:1});await Promise.all([one,two]);
 assert.equal(pending.messages.filter(m=>m.type==='resumed').length,1);assert.equal(pending.messages.filter(m=>m.type==='error').length,0);
 const cancelled=pending.send('resume');await pending.send('disconnect');complete({vip:1});await cancelled;
 assert.equal(pending.messages.filter(m=>m.type==='resumed').length,1,'Cancelled retries cannot reconnect later');assert.equal(pending.messages.at(-1).type,'disconnected');
 console.log('NETWORK_RECOVERY_OPERATION_AND_ENGINE_CONTEXT_GUARD_PASS bounded retry, restart delay, cancellation and no adapter replacement');
})().catch(e=>{console.error(e);process.exit(1);});
