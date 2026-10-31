'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const online=require('../online.js'),rpc=require('../profile-rpc.js'),lan=require('../browser.js');
function seed(){const p=new online.Profile(123456,'OldName');assert(p.put('f:GTA5/char0001.save',Uint8Array.from([0,255,128,0,42])));assert(p.setStat('p2:7',77n));return p;}
async function owner(saved,name,behavior='ok'){
 const buffer=new SharedArrayBuffer(rpc.SIZE),words=new Int32Array(buffer),record={ready:null,current:saved?.slice()??null,previous:null,commits:0};
 const storage={load:async()=>record.current?.slice()??null,commit:async bytes=>{record.commits++;if(behavior==='throw')throw Error('Storage failed');if(behavior==='false')return false;if(behavior==='external'){record.current=Uint8Array.from([99]);throw Error('Profile changed');}record.previous=record.current;record.current=bytes.slice();return true;}};
 try{await rpc.serve(buffer,storage,online.Profile,{id:654321,name},context=>{record.ready=context;Atomics.store(words,2,1);});}
 catch(error){record.error=error;}
 return record;
}
(async()=>{
 const original=seed(),before=original.encode(),values=[...original.values].map(([k,v])=>[k,[...v]]);
 for(const invalid of ['', '  ', 'name\n', '12345678901234567','é']){assert.equal(original.rename(invalid),false);assert.deepEqual(original.encode(),before);}
 const result=await owner(before,'New Name');assert(result.ready);assert.equal(result.ready.id,123456);assert.equal(result.ready.name,'New Name');assert.equal(result.commits,1);assert.deepEqual(result.previous,before);
 const renamed=online.Profile.decode(result.current);assert.equal(renamed.id,123456);assert.deepEqual([...renamed.values].map(([k,v])=>[k,[...v]]),values);assert(renamed.rename('OldName'));assert.deepEqual(renamed.encode(),before,'Only display header/checksum may change');
 const repeated=await owner(result.current,'New Name');assert(repeated.ready);assert.equal(repeated.commits,0,'An unchanged name must not replace the previous backup');assert.deepEqual(repeated.current,result.current);
 const context=new rpc.Proxy(result.ready),memory=new WebAssembly.Memory({initial:1});
 const hooks=online.hooks(memory,{},context,{commit:()=>true,prepareInterfaces:()=>true,allocate:()=>0n,release(){},networkUp:()=>1,transportReady:()=>true},lan.Memory);
 assert.equal(hooks.rl_offline_name(128n),1);assert.equal(Buffer.from(new Uint8Array(memory.buffer,128,9)).toString(),'New Name\0');assert.equal(hooks.rl_gamer_handle(200n),1);assert.equal(new DataView(memory.buffer).getBigUint64(200,true),123456n);
 // The ready context is fixed for this engine lifetime, including reconnect.
 original.rename('Later edit');assert.equal(context.name,'New Name');assert.equal(result.ready.name,'New Name');
 for(const behavior of ['throw','false','external']){const failed=await owner(before,'New Name',behavior);assert(failed.error);assert.equal(failed.ready,null,'No admission context after persistence failure');assert.deepEqual(failed.current,behavior==='external'?Uint8Array.from([99]):before);}
 for(const invalid of ['', '  ', 'name\n', '12345678901234567','é']){const failed=await owner(before,invalid);assert(failed.error);assert.equal(failed.ready,null);assert.equal(failed.commits,0);assert.deepEqual(failed.current,before);}
 const fresh=await owner(null,'First Name');assert.equal(fresh.ready.name,'First Name');assert.equal(fresh.ready.id,654321);assert.equal(fresh.commits,1);
 // Exercise the actual asynchronous launcher callback; a delayed saved read
 // cannot undo either an input edit or a submitted name change.
 const source=fs.readFileSync(require.resolve('../launcher.js'),'utf8'),line=source.split('\n').find(x=>x.startsWith('function showSavedLanProfile('));assert(line);
 for(const edited of [false,true]){const nodes=new Map(),box={settings:{player:'Initial'},initialPlayerName:'Initial',playerNameEdited:false,lobbyUI:{restorePlayerName(){}},document:{getElementById:id=>{if(!nodes.has(id))nodes.set(id,{});return nodes.get(id);}}};vm.runInNewContext(line,box);let resolve;const pending=new Promise(r=>resolve=r).then(p=>box.showSavedLanProfile(p));if(edited){box.playerNameEdited=true;box.settings.player='UserTyped';}resolve({name:'SavedName',files:['GTA5/char0001.save']});await pending;assert.equal(box.settings.player,edited?'UserTyped':'SavedName');}
 // Actual Join input signals an edit before form submission or async autofill.
 const nodes=new Map();class Element{constructor(tag){this.tag=tag;this.children=[];this.style={};this.dataset={};this.listeners={};this.open=false;}append(...v){this.children.push(...v);}replaceChildren(...v){this.children=v;}setAttribute(){}addEventListener(k,f){this.listeners[k]=f;}showModal(){this.open=true;}close(){this.open=false;}}
 for(const id of ['lobby-dialog','lobby-content','servers-dialog','servers-content','home-host','lobby-title','configure-lobby','browse-lobbies','file-readiness'])nodes.set(id,new Element('div'));
 let edits=0;const ui={document:{getElementById:id=>nodes.get(id),createElement:tag=>new Element(tag),addEventListener(){}},localStorage:{getItem(){return null;},setItem(){}},setInterval(){},clearInterval(){},setTimeout(){},addEventListener(){},ZemaLobbyModel:require('../lobby-model.js')};
 vm.runInNewContext(fs.readFileSync(require.resolve('../lobby-ui.js'),'utf8'),ui);
 const mounted=ui.ZemaLobbyUI.mount({getSettings:()=>({connection:'LAN',player:'Initial'}),change(){},play(){},nameEdited:()=>{edits++;},api:async()=>({owned:false,networks:{},files_available:true})});mounted.join();
 const form=nodes.get('lobby-content').children[0],row=form.children.find(e=>e.children[0]?.textContent==='Your player name');assert(row);mounted.restorePlayerName('SavedName');assert.equal(row.children[1].value,'SavedName');row.children[1].value='UserTyped';row.children[1].listeners.input();assert.equal(edits,1);mounted.restorePlayerName('LateRead');assert.equal(row.children[1].value,'UserTyped','Async autofill cannot overwrite a dirty Join field');
 console.log('PROFILE_RENAME_BROWSER_ID_PROGRESS_PERSISTENCE_GATE_ENGINE_NAME_AND_ASYNC_EDIT_PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
