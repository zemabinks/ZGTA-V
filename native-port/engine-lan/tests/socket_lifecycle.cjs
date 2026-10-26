'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),{Worker}=require('node:worker_threads'),api=require('../browser.js');
async function main(){
 const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),memory=new WebAssembly.Memory({initial:256,maximum:256,shared:true}),m=new api.Memory(memory),lan=new api.SharedLan();
 assert(lan.configure(api.NET|2,'0000000000000009'));lan.connection(true);
 const {instance}=await api.instantiate(Buffer.from(fixture.wasm,'base64'),{env:{memory}},{version:api.PROTOCOL,buffer:lan.buffer},fixture.metadata),e=instance.exports;
 const bind=(at,port)=>{m.set16(at+188n,port);assert.equal(e['test:socket_bind'](at),1);return Number(m.u64(at+8n));};
 const close=at=>{assert.equal(e['test:socket_close'](at),undefined);assert.equal(m.u64(at+8n),0xffffffffffffffffn);};
 for(let i=0;i<4096;i++){const h=bind(128n,0);assert(h>0&&h<1024);close(128n);close(128n);}
 assert.equal(lan.ports().length,0);
 const one=bind(128n,6672),shared=bind(640n,6672);assert.notEqual(one,shared);
 const packet=port=>api.encode(api.NET|1,6672,lan.vip,port,Buffer.from('keep'));
 assert(lan.deliver(packet(6672)));const count=lan.ports().length;
 assert.equal(e['test:socket_bind'](128n),1);assert.equal(Number(m.u64(136n)),one);m.set16(316n,0);assert.equal(e['test:socket_bind'](128n),1);assert.equal(Number(m.u64(136n)),one);
 m.set16(316n,7788);assert.equal(e['test:socket_bind'](128n),0);assert.equal(Number(m.u64(136n)),one);assert.equal(lan.ports().length,count);close(128n);
 assert.equal(e['test:socket_receive'](128n,0n,5000n,32,0n),0);assert.equal(e['test:socket_receive'](640n,0n,5000n,32,0n),4);
 assert(lan.deliver(packet(6672)));close(640n);const fresh=bind(128n,6672);assert.equal(lan.receive(6672),null);
 lan.connection(false);assert.equal(lan.port(fresh),6672);assert.equal(e['test:socket_bind'](128n),0);lan.connection(true);assert.equal(e['test:socket_bind'](128n),1);assert.equal(lan.port(fresh),6672);assert(lan.deliver(packet(6672)));assert.equal(lan.receive(6672).data.length,4);
 m.bytes(3000n,128).fill(0);m.set64(3000n+BigInt(Math.floor(fresh/64)*8),1n<<BigInt(fresh%64));
 const worker=new Worker(`const {workerData,parentPort}=require('node:worker_threads'),api=require(workerData.path);const lan=new api.SharedLan(workerData.buffer);parentPort.postMessage('ready');setTimeout(()=>{if(!lan.close(workerData.handle))throw Error('Close failed');},30);`,{eval:true,workerData:{path:require.resolve('../browser.js'),buffer:lan.buffer,handle:fresh}});
 await new Promise(resolve=>worker.once('message',resolve));const start=performance.now();assert.equal(e['test:socket_select'](1024,3000n,0n,0n,0n)>>>0,0xffffffff);assert(performance.now()-start<2000);await worker.terminate();close(128n);
 for(let port=1000;port<1100;port++){bind(128n,port);close(128n);}
 /* Closing the final port drops only that port's pending datagrams. */
 const a=lan.bind(1111),b=lan.bind(2222);assert(lan.deliver(packet(1111)));assert(lan.deliver(packet(2222)));assert(lan.close(a.handle));assert.equal(lan.receive(1111),null);assert.equal(lan.receive(2222).data.length,4);assert(lan.close(b.handle));
 /* Reusing a vacant record must not overwrite another live record. */
 const x=lan.bind(3333),y=lan.bind(4444);assert(lan.close(x.handle));const z=lan.bind(5555);assert.equal(lan.port(y.handle),4444);assert.equal(lan.port(z.handle),5555);
 assert(!lan.close(0));assert(!lan.close(Number.MAX_SAFE_INTEGER));
 console.log('BROWSER_SOCKET_LIFECYCLE_PASS');
}
main().catch(error=>{console.error(error.stack);process.exit(1);});
