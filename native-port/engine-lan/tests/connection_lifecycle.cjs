'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let now=0,serial=0;const intervals=new Map(),timeouts=new Map();
class ClockDate extends Date { static now(){return now;} }
const sandbox={module:{exports:{}},SharedArrayBuffer,Atomics,Int32Array,Uint8Array,DataView,URL,Date:ClockDate,
  performance:{now:()=>now},
  setTimeout:(fn,delay)=>{timeouts.set(++serial,{fn,delay});return serial;},clearTimeout:id=>timeouts.delete(id),
  setInterval:fn=>{intervals.set(++serial,fn);return serial;},clearInterval:id=>intervals.delete(id)};
vm.runInNewContext(fs.readFileSync(require.resolve('../browser.js'),'utf8'),sandbox);
const api=sandbox.module.exports;
class Socket {
  static all=[];
  constructor(){this.readyState=0;this.bufferedAmount=0;this.sent=[];Socket.all.push(this);}
  open(){this.readyState=1;this.onopen();}
  send(data){if(this.throwSend)throw Error('fixture send refused');this.sent.push(data);}
  close(){this.readyState=3;if(this.onclose)this.onclose();}
  joined(){this.onmessage({data:JSON.stringify({type:'joined',protocol:api.PROTOCOL,build:api.BUILD,vip:api.NET|1,epoch:'0000000000000009',resume:'x'.repeat(32)})});}
  pong(){this.onmessage({data:'{"type":"pong"}'});}
}
function tick(time){now=time;for(const fn of [...intervals.values()])fn();}
async function main(){
  const lan=new api.SharedLan(),client=new api.Client('ws://127.0.0.1:47540/engine-lan','audit','Audit',lan,Socket),states=[];
  client.status=(state,message)=>states.push({state,message});
  if(process.argv[2]==='cancel'){
    let settled=false;
    const pending=client.connect().then(()=>{throw Error('Cancelled admission resolved');},()=>{settled=true;});
    const old=Socket.all.at(-1);client.disconnect('Cancelled by user');
    await Promise.resolve();assert(settled,'Disconnect must reject pending admission, rather than leave it waiting forever');await pending;
    assert.equal(timeouts.size,0);assert.equal(intervals.size,0);
    const next=client.connect();const socket=Socket.all.at(-1);socket.open();old.onclose();socket.joined();await next;
    assert(lan.connected);client.disconnect();
    console.log('BROWSER_CANCELLED_JOIN_SETTLED_AND_STALE_CLOSE_IGNORED_PASS');return;
  }
  if(process.argv[2]==='join-send-failure'){
    const pending=client.connect(),socket=Socket.all.at(-1);socket.throwSend=true;
    assert.doesNotThrow(()=>socket.open());await assert.rejects(pending,/join send failed/);
    assert(!lan.connected);assert.equal(socket.readyState,3);assert.equal(client.resume,null);assert.equal(timeouts.size,0);assert.equal(intervals.size,0);
    console.log('BROWSER_JOIN_SEND_THROW_SETTLES_IMMEDIATELY_PASS');return;
  }
  if(process.argv[2]==='initial-error'){
    const pending=client.connect(),socket=Socket.all.at(-1);socket.onerror();await assert.rejects(pending,/connection failed/);
    assert(!/resume/.test(states.at(-1).message));assert.equal(client.resume,null);assert.equal(timeouts.size,0);
    console.log('BROWSER_INITIAL_FAILURE_DOES_NOT_CLAIM_RESUME_PASS');return;
  }
  const pending=client.connect(),socket=Socket.all.at(-1);socket.open();socket.joined();await pending;
  if(process.argv[2]==='active-error'){
    socket.onerror();assert(!lan.connected);assert.match(states.at(-1).message,/LAN disconnected/);
    assert(!/resume failed/.test(states.at(-1).message));assert.equal(client.resume,'x'.repeat(32));assert.equal(intervals.size,0);
    console.log('BROWSER_ACTIVE_CONNECTION_ERROR_IS_NOT_FAILED_RESUME_PASS');return;
  }
  if(process.argv[2]==='resume-timeout'){
    client.disconnect();const next=client.connect(),socket=Socket.all.at(-1);socket.open();
    assert.equal(timeouts.size,1);[...timeouts.values()][0].fn();await assert.rejects(next,/resume failed: admission timed out/);
    assert.match(states.at(-1).message,/retry Reconnect/);assert(!/reopen|restart/i.test(states.at(-1).message));assert.equal(client.resume,'x'.repeat(32));assert.equal(lan.vip,api.NET|1);assert.equal(timeouts.size,0);
    console.log('BROWSER_RESUME_TIMEOUT_RETAINS_IDENTITY_AND_RECOVERY_REASON_PASS');return;
  }

  if(process.argv[2]==='resume-failure'){
    client.disconnect();const resumed=client.connect(),next=Socket.all.at(-1);next.open();next.close();
    await assert.rejects(resumed,/retry Reconnect/);
    assert.match(states.at(-1).message,/resume failed/);
    assert.equal(client.resume,'x'.repeat(32));assert.equal(lan.vip,api.NET|1);assert.equal(intervals.size,0);assert.equal(timeouts.size,0);
    console.log('BROWSER_FAILED_RESUME_REASON_PRESERVED_WITHOUT_NEW_IDENTITY_PASS');return;
  }
  assert(lan.connected);tick(10001);assert(socket.sent.includes('{"type":"ping"}'));
  if(process.argv[2]==='healthy'){
    for(const time of [10001,20002,30003,40004,50005]){now=time;socket.pong();tick(time);assert(lan.connected);}
    client.disconnect();assert.equal(intervals.size,0);console.log('BROWSER_RESPONSIVE_RELAY_KEEPS_SESSION_PASS');return;
  }
  if(process.argv[2]==='traffic'){
    lan.bind(6672);
    for(const time of [20002,30003,40004,50005]){
      now=time;const frame=api.encode(api.NET|2,6672,lan.vip,6672,new Uint8Array([7]));
      socket.onmessage({data:frame.buffer});tick(time);assert(lan.connected);assert.equal(lan.receive(6672).data[0],7);
    }
    socket.onmessage({data:new Uint8Array(16).buffer});
    assert(!lan.connected);assert.match(states.at(-1).message,/datagram/i);
    assert.equal(intervals.size,0);console.log('BROWSER_VALID_TRAFFIC_LIVENESS_AND_MALFORMED_FRAME_REFUSED_PASS');return;
  }
  tick(30001);
  assert(!lan.connected,'A relay that accepts sends but never responds must stop showing connected');
  assert.equal(socket.readyState,3);assert.match(states.at(-1).message,/respond|heartbeat/i);
  assert.equal(client.resume,'x'.repeat(32));assert.equal(intervals.size,0);
  const next=client.connect(),resumed=Socket.all.at(-1);resumed.open();assert.equal(JSON.parse(resumed.sent[0]).resume,'x'.repeat(32));resumed.joined();await next;
  assert(lan.connected);assert.equal(lan.vip,api.NET|1);client.disconnect();
  console.log('BROWSER_SILENT_RELAY_DETECTED_AND_SAME_IDENTITY_RESUME_PASS');
}
main().catch(error=>{console.error(error.stack);process.exit(1);});
