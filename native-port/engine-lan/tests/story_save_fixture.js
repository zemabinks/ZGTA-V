'use strict';
document.getElementById('run').onclick=async()=>{
 const output=document.getElementById('result'),button=document.getElementById('run'),S=ZemaBrowserSaves;
 const name=S.database('story'),folder='/userdata/Documents/Rockstar Games/GTA V/Default/',checks=[];
 button.disabled=true;output.textContent='Running…';
 const check=(condition,message)=>{if(!condition)throw Error(message);checks.push('PASS: '+message);output.textContent=checks.join('\n');};
 const reject=async(fn,message)=>{let failed=false;try{await fn();}catch(_){failed=true;}check(failed,message);};
 const reset=()=>new Promise((resolve,reject)=>{const r=indexedDB.deleteDatabase(name);r.onsuccess=resolve;r.onerror=()=>reject(r.error);r.onblocked=()=>reject(Error('Test database unexpectedly in use.'));});
 const edit=async(fn)=>{const db=await new Promise((resolve,reject)=>{const r=indexedDB.open(name,1);r.onupgradeneeded=()=>r.result.createObjectStore('files');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});try{await new Promise((resolve,reject)=>{const tx=db.transaction('files','readwrite');fn(tx.objectStore('files'));tx.oncomplete=resolve;tx.onabort=tx.onerror=()=>reject(tx.error);});}finally{db.close();}};
 const bytes=new Uint8Array(65536);bytes[3]=1;const text='QA synthetic Story save';for(let n=0;n<text.length;n++){bytes[4+n*2]=text.charCodeAt(n)&255;bytes[5+n*2]=text.charCodeAt(n)>>8;}
 try{
  await reset();
  const concurrent=await Promise.allSettled([S.importStory(bytes,'SGTA50007'),S.importStory(bytes,'SGTA50007')]);
  check(concurrent.filter(r=>r.status==='fulfilled').length===1,'Concurrent import is blocked by the exclusive save lease');
  const a=concurrent.find(r=>r.status==='fulfilled').value,b=await S.importStory(bytes,'SGTA50007');
  check(a.slot===8&&b.slot===1,'Repeated import selects a different empty slot');
  await edit(store=>{for(const file of ['SGTA50001.BAK','SGTA50015','SGTA50015.bak'])store.add({data:new Uint8Array([21,22,23]),mtime:1},folder+file);});
  const c=await S.importStory(bytes,'SGTA50001');check(c.slot===3,'Backup-only slot is preserved');
  const files=await S.list('story');check(files.filter(f=>f.path.endsWith('15')||f.path.endsWith('15.bak')||f.path.endsWith('01.BAK')).every(f=>f.data.join(',')==='21,22,23'),'Autosave and existing backup bytes are unchanged');
  await navigator.locks.request('zema-browser-game-v1',async()=>{await reject(()=>S.importStory(bytes,'SGTA50000'),'Active game lease blocks import');});
  const before=await S.list('story'),add=IDBObjectStore.prototype.add;
  try{IDBObjectStore.prototype.add=function(...args){const result=add.apply(this,args);this.transaction.abort();return result;};await reject(()=>S.importStory(bytes,'SGTA50005'),'Aborted write rejects import');}finally{IDBObjectStore.prototype.add=add;}
  const after=await S.list('story');check(JSON.stringify(after)===JSON.stringify(before),'Aborted transaction preserves all existing bytes and filenames');
  const invalid=bytes.slice();invalid[3]=2;await reject(()=>S.importStory(invalid,'SGTA50005'),'Invalid save is rejected before writing');
  await reset();
  await edit(store=>{for(let n=0;n<15;n++)store.add({data:new Uint8Array([n]),mtime:1},folder+'sgta500'+String(n).padStart(2,'0'));});
  await reject(()=>S.importStory(bytes,'SGTA50000'),'All fifteen case-insensitive manual slots are protected');
  check((await S.list('story')).length===15,'Full-slot rejection adds no file');
  await reset();
  await edit(store=>{for(let n=0;n<256;n++)store.add({data:new Uint8Array([n]),mtime:1},'/userdata/Documents/qa-'+n);});
  await reject(()=>S.importStory(bytes,'SGTA50000'),'File-count limit protects backup compatibility');
  await reset();
  await edit(store=>store.add({data:new Uint8Array(16*1024*1024-65535),mtime:1},'/userdata/Documents/qa-large'));
  await reject(()=>S.importStory(bytes,'SGTA50000'),'Combined-size limit protects backup compatibility');
  await reset();check((await S.list('story')).length===0,'Synthetic test database removed');
  output.textContent=checks.join('\n')+'\nALL '+checks.length+' CHECKS PASSED';
 }catch(error){output.textContent=checks.join('\n')+'\nFAILED: '+error.message;try{await reset();}catch(_){} }
 finally{button.disabled=false;}
};
