/* Bounded offline-profile saves. All restores include an atomic rollback copy. */
(function(root){'use strict';
 const LIMIT=16*1024*1024,COUNT=256;
 const STORY_FOLDER='/userdata/Documents/Rockstar Games/GTA V/Default/';
 function storyTitle(bytes){
  const invalid=()=>Error('Choose a compatible GTA V Story save (SGTA5…), between 64 KB and 8 MB.');
  if(!(bytes instanceof Uint8Array)||bytes.length<65536||bytes.length>8*1024*1024||bytes[0]||bytes[1]||bytes[2]||bytes[3]!==1)throw invalid();
  let end=4;for(;end<516;end+=2)if(bytes[end]===0&&bytes[end+1]===0)break;
  if(end===516)throw invalid();
  let title;try{title=new TextDecoder('utf-16le',{fatal:true}).decode(bytes.subarray(4,end));}catch(_){throw invalid();}
  if(title.includes('\ufffd')||/[\x00-\x1f\x7f-\x9f]/.test(title))throw invalid();
  title=title.trim();if(Array.from(title).length<3)throw invalid();return title;
 }
 function storyCandidates(filename,occupied){
  const names=new Set(Array.from(occupied,n=>String(n).toLowerCase())),order=Array.from({length:15},(_,n)=>n);
  const match=/^SGTA500(0[0-9]|1[0-4])(?:\.BAK)?$/i.exec(filename);
  if(match){const own=Number(match[1]);order.splice(order.indexOf(own),1);order.unshift(own);}
  return order.filter(n=>{const name='sgta500'+String(n).padStart(2,'0');return !names.has(name)&&!names.has(name+'.bak');});
 }
 function database(mode){if(!['story','sandbox'].includes(mode))throw Error('Select Story or Free Roam saves.');return 'zema-browser-'+mode+'-userdata-v1';}
 function safe(path){return typeof path==='string'&&path.length<1024&&path.startsWith('/userdata/Documents/')&&!/[\\\x00-\x1f\x7f-\x9f]/.test(path)&&path.split('/').slice(1).every(p=>p&&p!=='.'&&p!=='..')&&!path.toLowerCase().endsWith('/settings.xml');}
 async function digest(data){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data)),n=>n.toString(16).padStart(2,'0')).join('');}
 function encode(bytes){let out='';for(let i=0;i<bytes.length;i+=8192)out+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(out);}
 function decode(text){
  if(typeof text!=='string'||text.length>Math.ceil(LIMIT/3)*4||text.length%4||/[^A-Za-z0-9+/=]/.test(text))throw Error('Invalid save data.');
  // A repeated four-character regex exhausted the JS regex stack on larger
  // valid saves. Check padding and decoded size without recursive matching.
  const at=text.indexOf('='),padding=at<0?0:text.length-at;
  if(padding>2||(padding&&text.slice(at)!=='='.repeat(padding)))throw Error('Invalid save data.');
  if(text.length/4*3-padding>LIMIT)throw Error('Backup is too large.');
  const binary=atob(text),out=new Uint8Array(binary.length);for(let i=0;i<out.length;i++)out[i]=binary.charCodeAt(i);return out;
 }
 function nativePath(path){if(typeof path!=='string')return null;const match=/^(userdata|sandbox)(\/Documents\/.+)$/.exec(path);return match&&safe('/userdata'+match[2])?{mode:match[1]==='userdata'?'story':'sandbox',path:'/userdata'+match[2]}:null;}
 async function validate(archive,mode){
  database(mode);const phone=archive?.schema===1&&archive.format===undefined&&Number.isFinite(archive.created);
  if(!archive||(!phone&&(archive.format!=='zema-browser-save-v1'||archive.mode!==mode))||!Array.isArray(archive.entries)||!archive.entries.length||archive.entries.length>COUNT)throw Error('Choose an iPhone .mugoatsave or a browser backup for this save profile.');
  const seen=new Set(),entries=[];let total=0;
  for(const item of archive.entries){
   const mapped=phone?nativePath(item?.path):null,path=phone?mapped?.path:item?.path;
   if(!safe(path)||seen.has(item.path))throw Error('Invalid or duplicate save path.');seen.add(item.path);
   const data=decode(item.data);total+=data.byteLength;
   if(total>LIMIT||await digest(data)!==item.sha256)throw Error('Backup is too large or its checksum does not match.');
   // Validate the entire phone package before selecting one isolated profile.
   if(!phone||mapped.mode===mode)entries.push({path,data,mtime:Number.isFinite(item.mtime)?item.mtime:Date.now()});
  }
  if(!entries.length)throw Error('This iPhone backup has no '+(mode==='story'?'Story':'Free Roam')+' files. Select the other save profile.');
  return entries;
 }
 async function nativeArchive(mode,value){
  const entries=await validate(value,mode),seen=new Set();
  return {schema:1,created:Date.now()/1000-978307200,entries:await Promise.all(entries.map(async f=>{
   const path=(mode==='story'?'userdata':'sandbox')+f.path.slice('/userdata'.length),key=path.normalize('NFC').toLowerCase();
   if(new TextEncoder().encode(path).length>=1024)throw Error('A save path is too long for the iPhone backup format.');
   if(seen.has(key))throw Error('Two save paths differ only by case or Unicode spelling. Rename them before transferring to iPhone.');seen.add(key);
   return {path,data:encode(f.data),sha256:await digest(f.data)};
  }))};
 }
 async function lease(fn){if(!navigator.locks)throw Error('Chrome Web Locks are required to protect saves.');return navigator.locks.request('zema-browser-game-v1',{ifAvailable:true},lock=>{if(!lock)throw Error('Close the running game or wait for another save operation to finish.');return fn();});}
 async function open(mode,create=false){const name=database(mode);if(!create){if(!indexedDB.databases)throw Error('This browser cannot safely list existing save databases.');if(!(await indexedDB.databases()).some(d=>d.name===name))return null;}
  return new Promise((resolve,reject)=>{const r=indexedDB.open(name,1);r.onupgradeneeded=()=>{if(!create){r.transaction.abort();return;}r.result.createObjectStore('files');};r.onblocked=()=>reject(Error('Save database is in use.'));r.onerror=()=>reject(r.error||Error('Cannot open saves.'));r.onsuccess=()=>{if(!r.result.objectStoreNames.contains('files')){r.result.close();reject(Error('Unexpected save storage.'));}else resolve(r.result);};});}
 function collect(db){if(!db)return Promise.resolve([]);return new Promise((resolve,reject)=>{let total=0,entries=[];const tx=db.transaction('files','readonly'),r=tx.objectStore('files').openCursor();r.onsuccess=()=>{const c=r.result;if(!c)return;try{if(safe(c.key)){const data=new Uint8Array(c.value.data);total+=data.byteLength;if(total>LIMIT||entries.length>=COUNT)throw Error('Saves exceed the 16 MB / 256 file backup limit.');entries.push({path:c.key,data,mtime:c.value.mtime});}c.continue();}catch(error){tx.abort();reject(error);}};tx.oncomplete=()=>resolve(entries);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error||Error('Save read cancelled.'));});}
 async function list(mode){return lease(async()=>{const db=await open(mode);try{return await collect(db);}finally{db?.close();}});}
 async function importStory(bytes,filename){
  const title=storyTitle(bytes),snapshot=bytes.slice();
  return lease(async()=>{const db=await open('story',true);try{
   // Slot discovery and exclusive add share one transaction. A failed add or
   // aborted transaction cannot replace any existing save or autosave.
   return await new Promise((resolve,reject)=>{
    const tx=db.transaction('files','readwrite'),store=tx.objectStore('files'),r=store.openCursor();
    let count=0,total=snapshot.length,visited=0,result;const occupied=[];
    r.onsuccess=()=>{const c=r.result;try{
     if(c){
      if(++visited>4096)throw Error('The save database contains too many entries.');
      if(safe(c.key)){
       const data=new Uint8Array(c.value.data);total+=data.byteLength;count++;
       if(total>LIMIT||count>=COUNT)throw Error('Saves would exceed the 16 MB / 256 file backup limit.');
       if(c.key.slice(0,STORY_FOLDER.length).toLowerCase()===STORY_FOLDER.toLowerCase())occupied.push(c.key.slice(STORY_FOLDER.length));
      }
      c.continue();return;
     }
     const slot=storyCandidates(filename,occupied)[0];
     if(slot===undefined)throw Error('All 15 manual save slots are occupied. Existing saves and autosave were kept.');
     const path=STORY_FOLDER+'SGTA500'+String(slot).padStart(2,'0');
     store.add({data:snapshot,mtime:Date.now()},path);result={title,slot:slot+1,path};
    }catch(error){tx.abort();reject(error);}};
    tx.oncomplete=()=>resolve(result);tx.onerror=()=>reject(tx.error||Error('Could not add Story save.'));
    tx.onabort=()=>reject(tx.error||Error('Story import cancelled; existing saves were kept.'));
   });
  }finally{db.close();}});
 }
 async function archive(mode,files){const entries=[];for(const f of files)entries.push({path:f.path,data:encode(f.data),sha256:await digest(f.data),mtime:f.mtime});return {format:'zema-browser-save-v1',mode,created:new Date().toISOString(),entries};}
 async function exportSaves(mode,path){const files=await list(mode),selected=path?files.filter(f=>f.path===path):files;if(!selected.length)throw Error('No saved files yet. Save inside the game first.');return archive(mode,selected);}
 async function exportNative(mode){return nativeArchive(mode,await exportSaves(mode));}
 async function exportSafety(mode){return lease(async()=>{const db=await open(mode);if(!db)throw Error('No safety backup exists yet.');try{const backup=await new Promise((resolve,reject)=>{let latest=null;const tx=db.transaction('files','readonly'),r=tx.objectStore('files').openCursor();r.onsuccess=()=>{const c=r.result;if(!c)return;if(String(c.key).startsWith('__zema-save-backup__/')&&c.value?.format==='zema-browser-rollback-v1'&&(!latest||c.value.created>latest.created))latest=c.value;c.continue();};tx.oncomplete=()=>resolve(latest);tx.onerror=()=>reject(tx.error);});if(!backup||!backup.entries.length)throw Error('No nonempty safety backup exists yet.');return archive(mode,backup.entries);}finally{db.close();}});}
 async function restore(mode,raw){if(typeof raw!=='string'||raw.length>32*1024*1024)throw Error('Backup exceeds 32 MB.');const entries=await validate(JSON.parse(raw),mode);
  return lease(async()=>{const db=await open(mode,true);try{
   // Same readwrite transaction reads originals, stores their backup and applies replacements.
   return await new Promise((resolve,reject)=>{const tx=db.transaction('files','readwrite'),store=tx.objectStore('files'),r=store.openCursor();const originals=[];let total=0,backups=0;const key='__zema-save-backup__/'+Date.now()+'-'+crypto.randomUUID();
    r.onsuccess=()=>{const c=r.result;try{if(c){if(String(c.key).startsWith('__zema-save-backup__/'))backups++;else if(safe(c.key)){const data=new Uint8Array(c.value.data);total+=data.byteLength;if(total>LIMIT||originals.length>=COUNT)throw Error('Current saves exceed the backup limit.');originals.push({path:c.key,data,mtime:c.value.mtime});}c.continue();return;}if(backups>=16)throw Error('The 16 safety-backup limit has been reached. No save or backup was changed.');store.put({format:'zema-browser-rollback-v1',created:Date.now(),entries:originals},key);for(const e of entries)store.put({data:e.data,mtime:e.mtime},e.path);}catch(error){tx.abort();reject(error);}};
    tx.oncomplete=()=>resolve({restored:entries.length,backup:key});tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error||Error('Restore cancelled; previous files remain.'));
   });
  }finally{db.close();}});
 }
 async function lanStore(create=false){
  if(!root.ZemaOnline||!root.ZemaProfileRPC)throw Error('LAN profile tools are unavailable.');
  if(!create){if(!indexedDB.databases)throw Error('Cannot safely inspect existing LAN storage.');if(!(await indexedDB.databases()).some(d=>d.name==='zema-engine-lan-profiles-v1'))return null;}
  return root.ZemaProfileRPC.IndexedStore.open();
 }
 async function lanBytes(previous=false){return lease(async()=>{const store=await lanStore();if(!store)return null;try{
  const bytes=previous?await new Promise((resolve,reject)=>{const tx=store.db.transaction('profiles','readonly'),r=tx.objectStore('profiles').get('previous');r.onsuccess=()=>resolve(r.result===undefined?null:new Uint8Array(r.result));r.onerror=()=>reject(Error('Cannot read the previous LAN profile.'));}):await store.load();
  if(bytes!==null)root.ZemaOnline.Profile.decode(bytes);return bytes;
 }finally{store.db.close();}});}
 async function lanInfo(){const bytes=await lanBytes();if(bytes===null)return null;const p=root.ZemaOnline.Profile.decode(bytes);return {name:p.name,id:p.id,bytes:bytes.length,files:[...p.values.keys()].filter(k=>k.startsWith('f:')).map(k=>k.slice(2)),stats:[...p.values.keys()].filter(k=>!k.startsWith('f:')).length,sha256:await digest(bytes)};}
 async function restoreLan(bytes){
  if(!(bytes instanceof Uint8Array))throw Error('Choose a .zemapf profile backup.');const p=root.ZemaOnline.Profile.decode(bytes),snapshot=bytes.slice();
  return lease(async()=>{const store=await lanStore(true);try{const current=await store.load();if(current!==null)root.ZemaOnline.Profile.decode(current);if(await store.commit(snapshot)!==true)throw Error('LAN restore failed.');return {name:p.name,id:p.id};}finally{store.db.close();}});
 }
 const api={safe,database,validate,list,exportSaves,exportNative,nativeArchive,exportSafety,restore,digest,archive,lanInfo,lanBytes,restoreLan,storyTitle,storyCandidates,importStory};root.ZemaBrowserSaves=api;if(typeof module==='object')module.exports=api;
})(globalThis);
