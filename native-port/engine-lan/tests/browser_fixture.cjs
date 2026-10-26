'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const api=require('../browser.js');
async function main(){
  const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
  const memory=new WebAssembly.Memory({initial:256,maximum:256,shared:true});
  const lan=new api.SharedLan();let client;
  if(process.argv[3]){client=new api.Client(process.argv[3],'fixture-cross-language','BrowserFixture',lan);await client.connect();}
  else{assert(lan.configure(api.NET|2,'0000000000000009'));lan.connection(true);}
  const metadata=fixture.metadata,bytes=Buffer.from(fixture.wasm,'base64');
  const result=await api.instantiate(bytes,{env:{memory}},{version:api.PROTOCOL,buffer:lan.buffer},metadata);
  const exports=result.instance.exports,m=new api.Memory(memory);
  assert.equal(exports.starts.value,1); // Original WASM start ran after callback installation.
  assert.throws(()=>api.requireGameReady(metadata),/not ready/);
  m.set16(316n,6672);assert.equal(exports['test:socket_bind'](128n),1);
  assert.equal(m.u32(264n),lan.vip);assert.equal(m.u16(284n),6672);
  const send=(to,text)=>{const data=Buffer.from(text);m.set32(1024n,to);m.set16(1044n,6672);m.bytes(2048n,data.length).set(data);
    assert.equal(exports['test:socket_send'](128n,1024n,2048n,data.length,1100n),1);};
  const receive=()=>{const n=exports['test:socket_receive'](128n,1200n,4096n,256,1100n);return n?Buffer.from(m.bytes(4096n,n)):null;};
  if(client){
    console.log('BROWSER_ENGINE_LAN_READY');
    await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>{clearInterval(timer);reject(Error('Native datagram timeout'));},12000);
      const timer=setInterval(()=>{const data=receive();if(!data)return;
        try{assert.deepEqual(data,Buffer.concat([Buffer.from([0,255,128,66]),Buffer.from('native-to-browser')]));send(m.u32(1200n),Buffer.concat([Buffer.from([0,254,129,67]),Buffer.from('browser-to-native')]));clearInterval(timer);clearTimeout(timeout);setTimeout(resolve,150);}catch(error){clearInterval(timer);clearTimeout(timeout);reject(error);}},5);
    });client.disconnect();console.log('BROWSER_ENGINE_LAN_WASM_REPLY_PASS');
  }else{
    send(api.NET|1,'browser-to-native');const wire=lan.takeOutgoing();assert.equal(Buffer.from(api.decode(wire).data).toString(),'browser-to-native');
    assert(lan.deliver(api.encode(api.NET|1,6672,lan.vip,6672,Buffer.from('native-to-browser'))));assert.equal(receive().toString(),'native-to-browser');
    assert.equal(exports['test:public_ip_address'](1500n),1);assert.equal(m.u32(1500n),lan.vip);
    lan.connection(false);assert.equal(exports['test:socket_send'](128n,1024n,2048n,1,1100n),0);
    console.log('BROWSER_TYPED_WASM_FIXTURE_PASS');
  }
}
main().catch(error=>{console.error(error.stack);process.exit(1);});
