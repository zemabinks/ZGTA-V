'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{Worker}=require('node:worker_threads');
const lan=require('../browser.js');global.ZemaOnline=require('../online.js');global.ZemaProfileRPC=require('../profile-rpc.js');
(async()=>{
  const fixture=JSON.parse(fs.readFileSync(process.argv[2])),buffer=new SharedArrayBuffer(ZemaProfileRPC.SIZE);
  const owner=new Worker(path.join(__dirname,'profile_rpc.cjs'),{workerData:{role:'owner',buffer,file:process.argv[3]}});
  try{
    const profile=await new Promise((resolve,reject)=>{owner.once('message',m=>m.error?reject(Error(m.error)):resolve(m));owner.once('error',reject);});
    const shared=new lan.SharedLan();assert(shared.configure(lan.NET|1,'0123456789abcdef'));shared.connection(true);
    const metadata=fixture.metadata,memory=new WebAssembly.Memory({initial:256,maximum:256,shared:true});
    const instance=lan.instance(new WebAssembly.Module(Buffer.from(fixture.wasm,'base64')),{env:{memory}},{version:lan.PROTOCOL,buffer:shared.buffer,profile},metadata);
    const m=new lan.Memory(memory),base=BigInt(metadata.social.base);
    assert.equal(instance.exports['test:sign'](20000n,base+2n),1);
    assert.equal(instance.exports['test:info'](20000n,10000n,base+3n),0n);assert.equal(m.u64(10008n),123456n);
    assert.equal(Buffer.from(m.bytes(10016n,4)).toString(),'Mac\0');
    assert.equal(instance.exports['test:float'](3.5,base+1n),0);
    assert.throws(()=>instance.exports['test:float'](3.5,base+2n),WebAssembly.RuntimeError);
    assert.throws(()=>instance.exports['test:sign'](20000n,0n),WebAssembly.RuntimeError);
    console.log('BROWSER_TYPED_SOCIAL_INFO_FLOAT_AND_ORDINARY_TRAPS_PASS');
  }finally{await owner.terminate();}
})().catch(error=>{console.error(error);process.exitCode=1;});
