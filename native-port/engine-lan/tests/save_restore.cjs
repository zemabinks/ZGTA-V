'use strict';
const assert=require('node:assert/strict');
if(!globalThis.crypto)globalThis.crypto=require('node:crypto').webcrypto;
const S=require(process.argv[2]||'../browser-saves.js');
const PREFIX='/userdata/Documents/';
let files=new Map(), puts=0, aborts=0, failPut=0, gets=0;
// Asynchronous transaction fixture: writes become visible only at oncomplete;
// abort discards every staged write, including the rollback snapshot. No real
// browser database, game data or profile path is opened by this fixture.
function transaction(){
 const staged=new Map(files),tx={closed:false,error:null};
 tx.abort=()=>{if(tx.closed)return;tx.closed=true;aborts++;setImmediate(()=>tx.onabort?.());};
 tx.objectStore=()=>({
  openCursor(){const request={},keys=[...staged.keys()].sort();let at=0;
   const advance=()=>setImmediate(()=>{if(tx.closed)return;const key=keys[at++];request.result=key===undefined?null:{key,value:staged.get(key),continue:advance};request.onsuccess?.();
    if(key===undefined&&!tx.closed)setImmediate(()=>{if(tx.closed)return;tx.closed=true;files=staged;tx.oncomplete?.();});});advance();return request;},
  get(key){gets++;const request={};setImmediate(()=>{if(tx.closed)return;request.result=staged.get(key);request.onsuccess?.();setImmediate(()=>{if(tx.closed)return;tx.closed=true;files=staged;tx.oncomplete?.();});});return request;},
  put(value,key){puts++;if(failPut&&puts===failPut)throw Error('Synthetic write failure');staged.set(key,structuredClone(value));}
 });return tx;
}
const db={objectStoreNames:{contains:name=>name==='files'},transaction,close(){}};
globalThis.indexedDB={open(){const request={result:db};setImmediate(()=>request.onsuccess?.());return request;},databases:async()=>[{name:S.database('story')}]};
Object.defineProperty(globalThis,'navigator',{configurable:true,value:{locks:{request:async(name,options,fn)=>{assert.equal(name,'zema-browser-game-v1');assert.deepEqual(options,{ifAvailable:true});return fn({});}}}});
function reset(entries){files=new Map(entries.map(([name,bytes])=>[PREFIX+name,{data:new Uint8Array(bytes),mtime:1}]));puts=0;aborts=0;failPut=0;gets=0;}
function state(){return structuredClone([...files]);}
async function incoming(entries){return JSON.stringify(await S.archive('story',entries.map(([name,bytes])=>({path:PREFIX+name,data:new Uint8Array(bytes),mtime:2}))));}
async function rejectsUnchanged(raw){const before=state();await assert.rejects(S.restore('story',raw),/Restored saves would exceed/);assert.deepEqual(state(),before);assert.equal(puts,0,'Limit rejection happens before rollback or replacement writes');assert.equal(aborts,1);}
async function main(){
 reset([['old',new Uint8Array(9*1024*1024)]]);await rejectsUnchanged(await incoming([['new',new Uint8Array(8*1024*1024)]]));
 reset(Array.from({length:256},(_,n)=>['old-'+n,[n&255]]));await rejectsUnchanged(await incoming([['new',[1]]]));
 reset([['old',new Uint8Array(9*1024*1024)]]);let raw=await incoming([['old',new Uint8Array(8*1024*1024)],['new',new Uint8Array(8*1024*1024)]]);await S.restore('story',raw);
 assert.equal((await S.list('story')).length,2);assert.equal((await S.exportSaves('story')).entries.length,2,'Exactly 16MB combined state remains exportable');assert.equal([...files.keys()].filter(k=>k.startsWith('__zema-save-backup__/')).length,1);
 reset(Array.from({length:256},(_,n)=>['old-'+n,[n&255]]));await S.restore('story',await incoming([['old-0',[99]]]));assert.equal((await S.exportSaves('story')).entries.length,256,'Replacement at count limit is allowed');assert.deepEqual([...files.get(PREFIX+'old-0').data],[99]);
 reset([['old',[1,2,3]]]);const before=state();failPut=2;await assert.rejects(S.restore('story',await incoming([['old',[4,5,6]]])),/Synthetic write failure/);assert.deepEqual(state(),before,'Later write failure also rolls back safety-backup insertion');
 reset([['large',new Uint8Array(17*1024*1024)],['small',[7,8,9]]]);const oversized=state();
 const info=await S.listInfo('story');assert.equal(info.length,2);assert.equal(info.find(f=>f.path.endsWith('/large')).size,17*1024*1024);assert(info.every(f=>f.data===undefined),'Listing retains metadata only');
 await assert.rejects(S.exportSaves('story'),/16 MB/);
 const one=await S.exportSaves('story',PREFIX+'small');assert.equal(one.entries.length,1);assert.deepEqual(Buffer.from(one.entries[0].data,'base64'),Buffer.from([7,8,9]));assert.equal(gets,1,'Individual export issues one targeted get');
 await assert.rejects(S.exportSaves('story',PREFIX+'large'),/selected save exceeds/);assert.equal(gets,2);
 await assert.rejects(S.exportSaves('story','/userdata/Documents/../escape'),/Invalid save path/);assert.equal(gets,2,'Invalid target is rejected before DB access');
 assert.deepEqual(state(),oversized);assert.equal(puts,0,'Recovery listing/export never mutate storage');
 reset(Array.from({length:257},(_,n)=>['entry-'+n,[n&255]]));assert.equal((await S.listInfo('story')).length,257);await assert.rejects(S.exportSaves('story'),/256 file/);assert.equal((await S.exportSaves('story',PREFIX+'entry-256')).entries.length,1);
 reset(Array.from({length:4097},(_,n)=>['entry-'+n,[0]]));await assert.rejects(S.listInfo('story'),/too many entries/);assert.equal(puts,0);
 reset([['keep',[3,4,5]]]);
 for(const [first,second]of [['σ','ς'],['ss','ß'],['ff','ﬀ'],['A','a'],['é','e\u0301']]){
  const archive=JSON.parse(await incoming([[first,[1]],[second,[2]]]));
  const phone={schema:1,created:0,entries:archive.entries.map(e=>({...e,path:e.path.slice(1)}))},before=state();
  await assert.rejects(S.restore('story',JSON.stringify(phone)),/duplicate/);
  assert.deepEqual(state(),before);assert.equal(puts,0);assert.equal(aborts,0,'Native alias rejection precedes write transaction');
 }
 console.log('PASS: union restore stays atomic/exportable; oversized-profile recovery lists metadata and exports only selected bounded files.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
