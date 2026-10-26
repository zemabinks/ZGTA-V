'use strict';
const assert=require('node:assert/strict'),path=require('node:path'),O=require(process.argv[2]?path.resolve(process.argv[2]):'../online.js'),L=require('../browser.js');
const memory=new WebAssembly.Memory({initial:512,maximum:512}),m=new L.Memory(memory),profile=new O.Profile(123456,'InlineSave');
const block=23158104n,op=4096n;let h,threads=0,serialized=0,committed=null,throwWorker=false,failWorker=false,prepared=true;
m.bytes(512n,43).set(new TextEncoder().encode('GTA5/saves/mpstats/save_char0001.save\0'));m.bytes(1024n,4).set([1,2,3,4]);
const originals={
 active_gamer_info:()=>0n,
 save_thread_create:()=>{threads++;return 12345n;},
 save_block_worker:p=>{serialized++;if(throwWorker)throw Error('fixture serializer failure');m.bytes(1024n,4).set([10,20,30,40]);m.set32(p+68n,failWorker?2:3);},
 mpstats_save_update:()=>{
   if(m.u32(op+20n)===2){const handle=h.save_thread_create(41759n,block,16384,-1,2080798n,2080798n);m.set64(2048n,handle);m.set32(op+20n,3);return 0;}
   if(m.u32(op+20n)===3&&m.u32(block+68n)===3){assert.equal(m.u64(2048n),1n,'Pinned completed-thread sentinel is used only after original serializer returns');if(h.active_gamer_info()===0n)return 0;h.post_member_file(0n,0n,512n,1024n,4,0n,0n,8192n);return m.u32(8192n)===3?1:0;}
   return 0;
 }
};
const host={inlineMemberSave:true,commit:()=>{committed=profile.encode();return true;},prepareInterfaces:()=>true,interfacesReady:()=>prepared,allocate:()=>0n,release(){},networkUp(){},transportReady:()=>false};
h=O.hooks(memory,originals,profile,host,L.Memory);
function reset(){committed=null;throwWorker=false;failWorker=false;prepared=true;m.set32(6713864n,0);m.set32(op+20n,2);m.set32(block+68n,1);m.set8(block+72n,1);m.set32(block+64n,4);m.set64(block+32n,1024n);}
reset();profile.setStat('p0:7',99n);assert.equal(h.mpstats_save_update(op),0);assert.equal(threads,0);assert.equal(serialized,1);assert.equal(m.u32(block+68n),3);assert.equal(h.mpstats_save_update(op),1);
const restored=O.Profile.decode(committed);assert.deepEqual([...restored.get('f:GTA5/saves/mpstats/save_char0001.save')],[10,20,30,40]);assert.equal(restored.stat('p0:7'),99n);
// Failure remains failure; no manufactured completion or file commit.
reset();failWorker=true;h.mpstats_save_update(op);assert.equal(m.u32(block+68n),2);assert.equal(h.mpstats_save_update(op),0);assert.equal(committed,null);
reset();throwWorker=true;assert.throws(()=>h.mpstats_save_update(op),/fixture serializer failure/);assert.equal(m.u32(op+20n),2);assert.equal(committed,null);
// Ordinary calls, old stages, other gamers and invalid/unprepared blocks keep
// their existing asynchronous path. No global sign-in byte is changed.
for(const change of [()=>{host.inlineMemberSave=false;},()=>{prepared=false;},()=>{m.set32(6713864n,1);},()=>{m.set32(block+64n,1048577);},()=>{m.set8(block+72n,0);}]){
 reset();host.inlineMemberSave=true;change();const before=serialized,n=threads;h.mpstats_save_update(op);assert.equal(serialized,before);assert.equal(threads,n+1);
}
reset();host.inlineMemberSave=true;const n=threads;h.save_thread_create(41759n,block,16384,-1,0n,0n);assert.equal(threads,n+1,'Ordinary caller is never made inline');
assert.equal(m.bytes(15219188n,1)[0],0);
console.log('INLINE_MEMBER_SAVE_ORIGINAL_SERIALIZER_DURABLE_COMMIT_FAILURE_AND_SCOPE_PASS');
