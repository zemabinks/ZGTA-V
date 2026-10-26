'use strict';
const assert=require('node:assert/strict'),path=require('node:path');
const online=require(process.argv[2]?path.resolve(process.argv[2]):'../online.js'),lan=require('../browser.js');
const memory=new WebAssembly.Memory({initial:512,maximum:512}),m=new lan.Memory(memory),profile=new online.Profile(123456,'SaveAudit');
let hooks,originalResult=0n,up=true,prepared=true,committed=null,commits=0,explode=false;
const filename=Buffer.from('GTA5/saves/mpstats/save_char0001.save\0');m.bytes(512n,filename.length).set(filename);m.bytes(1024n,4).set([10,20,30,40]);
const active=()=>hooks.active_gamer_info?hooks.active_gamer_info():originalResult;
const originals={active_gamer_info:()=>originalResult,mpstats_load_update:()=>active(),mpstats_save_update:()=>{
 // Exact pinned save-operation state 4: no active gamer sets error 499 before
 // reaching PostMemberFile. That call is our local writer, not a remote API.
 if(active()===0n){m.set32(23159968n,499);return 0;}
 if(explode)throw Error('fixture save exception');
 hooks.post_member_file(0,0,512n,1024n,4,0n,0n,4096n);return m.u32(4096n)===3?1:0;
}};
const host={commit:()=>{committed=profile.encode();commits++;return true;},prepareInterfaces:()=>true,interfacesReady:()=>prepared,allocate:()=>0n,release(){},networkUp(){},transportReady:()=>up};
hooks=online.hooks(memory,originals,profile,host,lan.Memory);
assert.equal(active(),0n);assert.equal(hooks.mpstats_load_update(0n),0n);assert.equal(commits,0);
prepared=false;assert.equal(hooks.mpstats_save_update(0n),0);prepared=true;
m.set32(6713864n,1);assert.equal(hooks.mpstats_save_update(0n),0);m.set32(6713864n,0);
profile.setStat('p1:7',123n);const signIn=m.bytes(15219188n,1)[0];
assert.equal(hooks.mpstats_save_update(0n),1,'Offline queued save must reach the durable local writer');
assert.equal(commits,1);const restored=online.Profile.decode(committed);assert.deepEqual([...restored.get('f:GTA5/saves/mpstats/save_char0001.save')],[10,20,30,40]);assert.equal(restored.stat('p1:7'),123n);
up=false;assert.equal(hooks.mpstats_save_update(0n),1,'Local saving must survive a relay interruption');assert.equal(commits,2);up=true;
assert.equal(active(),0n);assert.equal(m.bytes(15219188n,1)[0],signIn,'Do not change external-service sign-in state');
explode=true;assert.throws(()=>hooks.mpstats_save_update(0n),/fixture save exception/);assert.equal(active(),0n);explode=false;
originalResult=12345678n;assert.equal(active(),originalResult);assert.equal(hooks.mpstats_load_update(0n),originalResult);
console.log('LOCAL_SAVE_GAMER_SCOPE_DURABLE_CHARACTER_AND_SIGNIN_STATE_PASS');
