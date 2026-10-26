'use strict';
const assert=require('node:assert/strict'),api=require('../browser.js');
class Socket {
 static latest;
 constructor(){Socket.latest=this;this.readyState=1;this.sent=[];this.bufferedAmount=0;}
 send(data){this.sent.push(JSON.parse(data));}
 close(){this.readyState=3;}
 message(value){this.onmessage({data:JSON.stringify({protocol:api.PROTOCOL,build:api.BUILD,...value})});}
}
async function test(mode){
 const lan=new api.SharedLan(),client=new api.Client('ws://127.0.0.1:47540/engine-lan','RECOVERY','SameCharacter',lan,Socket);
 let pending=client.connect(),s=Socket.latest;s.onopen();
 s.message({type:'joined',vip:api.NET|2,epoch:'0000000000000009',resume:'a'.repeat(32)});await pending;
 const handle=lan.bind(6672).handle;
 assert(lan.send(6672,api.NET|1,6672,Buffer.from('stale')));
 client.disconnect();assert.equal(lan.takeOutgoing(),null);
 pending=client.connect();s=Socket.latest;s.onopen();assert.equal(s.sent[0].resume,'a'.repeat(32));
 const epoch='0000000000000010';
 s.message({type:'resume-unavailable',epoch,recovery:'same-address-v1'});
 assert.deepEqual(s.sent[1].rejoin,{vip:api.NET|2,epoch});assert.equal(s.sent[1].name,'SameCharacter');assert(!('resume' in s.sent[1]));
 if(mode==='occupied'){
  s.message({type:'rejoin-unavailable'});await assert.rejects(pending,/occupied/);assert(!lan.connected);
 }else if(mode==='wrong-address'){
  s.message({type:'joined',vip:api.NET|3,epoch,resume:'b'.repeat(32)});await assert.rejects(pending,/session changed/);assert(!lan.connected);
 }else if(mode==='wrong-epoch'){
  s.message({type:'joined',vip:api.NET|2,epoch:'0000000000000020',resume:'b'.repeat(32)});await assert.rejects(pending,/session changed/);assert(!lan.connected);
 }else{
  s.message({type:'joined',vip:api.NET|2,epoch,resume:'b'.repeat(32)});await pending;
  assert(lan.connected);assert.equal(lan.port(handle),6672);
  assert(lan.send(6672,api.NET|1,6672,Buffer.from('new')));assert.equal(api.decode(lan.takeOutgoing()).from,api.NET|2);
  assert(lan.deliver(api.encode(api.NET|1,6672,lan.vip,6672,Buffer.from('reply'))));assert.equal(Buffer.from(lan.receive(6672).data).toString(),'reply');
 }
 assert.equal(lan.vip,api.NET|2);assert.equal(lan.port(handle),6672);client.disconnect();
}
(async()=>{for(const mode of ['restart','occupied','wrong-address','wrong-epoch'])await test(mode);console.log('BROWSER_REJOIN_PRESERVES_IDENTITY_HANDLES_QUEUES_AND_CONFLICTS_PASS');})().catch(e=>{console.error(e);process.exit(1);});
