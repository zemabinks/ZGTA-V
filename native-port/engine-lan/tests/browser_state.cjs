'use strict';
const assert=require('node:assert/strict'),{Worker}=require('node:worker_threads');
const api=require('../browser.js');
class Fake {
  static all=[];
  constructor(){this.readyState=0;this.bufferedAmount=0;this.sent=[];Fake.all.push(this);}
  send(data){this.sent.push(data);}
  close(){this.readyState=3;if(this.onclose)this.onclose();}
  open(){this.readyState=1;this.onopen();}
  joined(epoch='0000000000000009'){this.onmessage({data:JSON.stringify({type:'joined',protocol:api.PROTOCOL,build:api.BUILD,vip:api.NET|2,epoch,resume:'x'.repeat(32)})});}
}
async function main(){
  for(const bad of ['ws://8.8.8.8:47540/engine-lan','ws://127.0.0.1:47540/ws','ws://user@127.0.0.1/engine-lan','wss://127.0.0.1/engine-lan'])assert.throws(()=>api.localURL(bad));
  for(const args of [[api.NET|1,65536,api.NET|2,1],[api.NET+2**32+1,1,api.NET|2,1],[api.NET|1,1,0,1]])assert.throws(()=>api.encode(...args,Buffer.from('x')));
  const lan=new api.SharedLan();assert(lan.configure(api.NET|2,'0000000000000009'));lan.connection(true);lan.bind(6672);
  for(let i=0;i<256;i++)assert(lan.send(6672,api.NET|1,6672,Buffer.from('x')));
  assert(!lan.send(6672,api.NET|1,6672,Buffer.from('overflow')));lan.connection(false);assert.equal(lan.takeOutgoing(),null);lan.connection(true);
  assert(!lan.configure(api.NET|3,'0000000000000009'));assert(!lan.configure(api.NET|2,'0000000000000010'));
  const memory=new WebAssembly.Memory({initial:256,maximum:256,shared:true});const m=new api.Memory(memory);
  const hooks=api.engineHooks(memory,lan,{socket_select:()=>{throw Error('Original select must not run for virtual handles');}});
  const set=(at,bits)=>{m.bytes(at,128).fill(0);m.set64(at,bits);}, timeout=(seconds,micros)=>{m.set64(4000n,seconds);m.set32(4008n,micros);};
  assert.equal(hooks.socket_send(0n,0n,0n,-1,0n),0);assert.equal(hooks.socket_select(-1,0n,0n,0n,0n),0xffffffff);
  assert.equal(lan.bind(7788).handle,2);assert.equal(lan.bind(6672).handle,3);
  for(let i=0;i<256;i++)assert(lan.send(6672,api.NET|1,6672,Buffer.from('full')));
  assert(!lan.send(6672,api.NET|1,6672,Buffer.from('overflow')));
  set(3200n,2n);timeout(0n,0);assert.equal(hooks.socket_select(4,0n,3200n,0n,4000n),0);assert.equal(m.u64(3200n),0n);
  set(3200n,2n);timeout(1n,0);
  const drain=new Worker(`const {parentPort,workerData}=require('node:worker_threads');const api=require(workerData.path);const lan=new api.SharedLan(workerData.buffer);parentPort.postMessage('ready');setTimeout(()=>{if(!lan.takeOutgoing())throw Error('No queued frame to drain');},30);`,{eval:true,workerData:{path:require.resolve('../browser.js'),buffer:lan.buffer}});
  await new Promise(resolve=>drain.once('message',resolve));const drainStart=performance.now();assert.equal(hooks.socket_select(4,0n,3200n,0n,4000n),1);assert(performance.now()-drainStart>=15&&performance.now()-drainStart<2000);assert.equal(m.u64(3200n),2n);await drain.terminate();
  timeout(0n,10000);let before=performance.now();assert.equal(hooks.socket_select(0,0n,0n,0n,4000n),0);assert(performance.now()-before>=5);
  set(3000n,2n);timeout(0n,30000);before=performance.now();assert.equal(hooks.socket_select(4,3000n,0n,0n,4000n),0);assert(performance.now()-before>=15);assert.equal(m.u64(3000n),0n);
  assert(lan.deliver(api.encode(api.NET|1,6672,lan.vip,6672,Buffer.from('first'))));
  set(3000n,14n);set(3200n,4n);set(3400n,14n);timeout(0n,0);
  assert.equal(hooks.socket_select(4,3000n,3200n,3400n,4000n),3);assert.equal(m.u64(3000n),10n);assert.equal(m.u64(3200n),4n);assert.equal(m.u64(3400n),0n);
  for(let i=4;i<=70;i++)assert.equal(lan.bind(6672).handle,i);
  set(3000n,2n);m.set64(3008n,1n<<6n);assert.equal(hooks.socket_select(71,3000n,0n,0n,4000n),2);assert.equal(m.u64(3008n),1n<<6n);
  // An unrelated queued port cannot make handle2 readable; actual delivery wakes it.
  set(3000n,4n);timeout(1n,0);
  const worker=new Worker(`const {parentPort,workerData}=require('node:worker_threads');const api=require(workerData.path);const lan=new api.SharedLan(workerData.buffer);parentPort.postMessage('ready');setTimeout(()=>{lan.deliver(api.encode(api.NET|1,6672,lan.vip,7788,Buffer.from('wake')));},30);`,{eval:true,workerData:{path:require.resolve('../browser.js'),buffer:lan.buffer}});
  await new Promise(resolve=>worker.once('message',resolve));assert.equal(hooks.socket_select(4,3000n,0n,0n,4000n),1);assert.equal(m.u64(3000n),4n);await worker.terminate();
  set(3000n,4n);set(3200n,4n);assert.equal(hooks.socket_select(4,3000n,3200n,0n,4000n),2);
  assert.equal(Buffer.from(lan.receive(7788).data).toString(),'wake');assert.equal(Buffer.from(lan.receive(6672).data).toString(),'first');
  set(3000n,1n<<7n); // bit outside nfds is discarded, rather than reported readable.
  timeout(0n,0);assert.equal(hooks.socket_select(4,3000n,0n,0n,4000n),0);assert.equal(m.u64(3000n),0n);
  set(3000n,1n<<7n); // handle7 exists; handle100 does not.
  m.set64(3008n,1n<<36n);assert.equal(hooks.socket_select(101,3000n,0n,0n,4000n),0xffffffff);assert.equal(m.u64(3008n),1n<<36n);
  set(3000n,2n);timeout(0xffffffffffffffffn,0);assert.equal(hooks.socket_select(4,3000n,0n,0n,4000n),0xffffffff);assert.equal(m.u64(3000n),2n);
  timeout(0n,1000000);assert.equal(hooks.socket_select(4,3000n,0n,0n,4000n),0xffffffff);
  assert.equal(hooks.socket_select(1025,3000n,0n,0n,0n),0xffffffff);assert.equal(hooks.socket_select(4,BigInt(memory.buffer.byteLength-64),0n,0n,0n),0xffffffff);
  // A disconnect wakes an unlimited receive wait, with no fictitious readable bits.
  set(3000n,2n);set(3200n,0n);
  const disconnect=new Worker(`const {parentPort,workerData}=require('node:worker_threads');const api=require(workerData.path);const lan=new api.SharedLan(workerData.buffer);parentPort.postMessage('ready');setTimeout(()=>lan.connection(false),30);`,{eval:true,workerData:{path:require.resolve('../browser.js'),buffer:lan.buffer}});
  await new Promise(resolve=>disconnect.once('message',resolve));before=performance.now();assert.equal(hooks.socket_select(4,3000n,3200n,0n,0n),0);assert(performance.now()-before<2000);assert.equal(m.u64(3000n),0n);await disconnect.terminate();
  const client=new api.Client('ws://127.0.0.1:47540/engine-lan','fixture','Fixture',lan,Fake);
  const statuses=[];client.status=(state,message)=>statuses.push({state,message});
  let pending=client.connect(),old=Fake.all.at(-1);old.open();old.joined();await pending;assert(lan.connected);
  assert.equal(statuses.at(-1).state,'connected');client.disconnect();assert(!lan.connected);assert.equal(statuses.at(-1).state,'disconnected');pending=client.connect();const newer=Fake.all.at(-1);newer.open();old.onclose();assert.equal(client.socket,newer);
  assert(JSON.parse(newer.sent[0]).resume);newer.joined();await pending;assert(lan.connected);assert.equal(lan.vip,api.NET|2);client.disconnect();pending=client.connect();const third=Fake.all.at(-1);third.open();third.joined('0000000000000010');await assert.rejects(pending,/session changed/);assert(!lan.connected);assert.equal(client.socket,null);assert.equal(client.timer,null);
  console.log('BROWSER_SHARED_STATE_PASS');
}
main().catch(error=>{console.error(error.stack);process.exit(1);});
