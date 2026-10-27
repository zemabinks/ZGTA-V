'use strict';
// Exercise the real lobby controller with disposable DOM/storage/API boundaries.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{
 constructor(tag,text=''){this.tag=tag;this.textContent=text;this.children=[];this.hidden=false;this.disabled=false;this.style={};this.listeners={};this.open=false;this.attributes={};this.dataset={};this.value='';}
 append(...nodes){this.children.push(...nodes);}
 replaceChildren(...nodes){this.children=nodes;}
 setAttribute(name,value){this.attributes[name]=value;}
 addEventListener(name,fn){this.listeners[name]=fn;}
 show(){this.open=true;}
 showModal(){this.open=true;}
 close(){this.open=false;this.listeners.close?.();}
 focus(){this.focused=true;}
 querySelectorAll(){return [];}
}
const nodes=new Map();for(const id of ['lobby-dialog','lobby-content','servers-dialog','servers-content','home-host','lobby-title','configure-lobby','browse-lobbies','file-readiness','play'])nodes.set(id,new Element('div'));
const timers=[],events={},calls=[],memory=new Map(),storage={getItem:k=>memory.get(k),setItem:(k,v)=>memory.set(k,v)};
const S=require('../launch-settings.js');let settings={...S.defaults};
const relay='ws://192.168.1.11:47540/engine-lan';
const api=async(path,body)=>{calls.push({path,body});if(path==='launcher/status')return {networks:{},files_available:true};if(path==='host/status')return {owned:false};if(path==='lobbies/discover')return {available:false,addresses:[]};if(path==='lobbies/probe')return {hosts:body.addresses.includes(relay)?[{address:relay,state:'online',catalog:true,room_policy:'hosted',lobbies:[{room:'LIVE',players:1,slots:1,capacity:8}],latency_ms:3}]:[]};throw Error('Unexpected startup mutation: '+path);};
const context={document:{getElementById:id=>nodes.get(id),createElement:tag=>new Element(tag),hidden:false,addEventListener:(name,fn)=>{events[name]=fn;}},navigator:{clipboard:{writeText:async()=>{}}},confirm:()=>true,setInterval:fn=>{timers.push(fn);return timers.length;},clearInterval(){},setTimeout(){},addEventListener:(name,fn)=>{events[name]=fn;},localStorage:storage,TextEncoder,URL,URLSearchParams,console};context.globalThis=context;context.ZemaEngineLan=require('../browser.js');
vm.runInNewContext(fs.readFileSync(require.resolve('../lobby-model.js'),'utf8'),context);vm.runInNewContext(fs.readFileSync(require.resolve('../lobby-ui.js'),'utf8'),context);
const ui=context.ZemaLobbyUI.mount({getSettings:()=>settings,change:patch=>{settings={...settings,...patch};},api,storage});
const flush=()=>new Promise(r=>setImmediate(r));
function form(){return nodes.get('lobby-content').children[0];}
function field(title){return form().children.find(e=>e.tag==='label'&&e.children[0].textContent===title).children[1];}
function role(title){return form().children[0].children.find(e=>e.textContent===title);}
function text(node){return node.textContent+' '+node.children.map(text).join(' ');}
async function checkFinalLaunch(){
 const launcher=fs.readFileSync(require.resolve('../launcher.js'),'utf8');
 const source=launcher.slice(launcher.indexOf('async function launch(){'),launcher.indexOf('\nconst lobbyUI=ZemaLobbyUI.mount'));
 assert(source.startsWith('async function launch(){'));
 for(const mode of ['story','sandbox','join','host','invalid']){
  const log=[],status={className:'',textContent:''},play={disabled:false},target=[];
  const ctx={S,ZemaLobbyModel:context.ZemaLobbyModel,settings:S.normalize({mode:['join','host','invalid'].includes(mode)?'lan':mode,lobbyRole:mode==='host'?'host':'join',relay:'',player:'Tester'}),launchBusy:false,desktopUI:{active:true},lobbyUI:{prepareLaunch(){log.push('prepare');if(mode==='invalid')throw Error('Invalid draft');Object.assign(ctx.settings,{room:'CHOSEN',relay,player:'Tester'});}},document:{getElementById:id=>id==='play'?play:status},crossOriginIsolated:true,navigator:{gpu:{}},TextEncoder,localStorage:{setItem(){}},location:{assign:url=>target.push(url)},ZemaModsUI:{api:async(path,body)=>{log.push({path,body});if(path==='host/start')return {join:relay};if(path==='lobbies/probe')return {hosts:[{state:'online',catalog:true,room_policy:'hosted',lobbies:[{room:'CHOSEN'}]}]};if(path==='launch')return {prefix:''};throw Error('Unexpected mutation');}}};
  vm.createContext(ctx);vm.runInContext(source,ctx);const result=await ctx.launch();
  if(mode==='invalid'){assert.equal(result,false);assert.equal(log.length,1);assert.equal(target.length,0);assert.equal(status.className,'error');continue;}
  assert.equal(result,true);assert.equal(target.length,1);const url=new URL(target[0],'http://localhost');
  assert.equal(url.pathname,'/play/'+(['join','host'].includes(mode)?'lan':mode));
  if(['join','host'].includes(mode)){assert.equal(log[0],'prepare');assert.equal(url.searchParams.get('room'),'CHOSEN');assert.equal(url.searchParams.get('relay'),relay);}
  assert.equal(log.filter(x=>x.path==='host/start').length,mode==='host'?1:0);
  assert.equal(log.filter(x=>x.path==='launch').length,1);
 }
}
(async()=>{
 await flush();ui.setDesktop(true);ui.activateDesktop(true);await flush();
 assert(nodes.get('servers-dialog').open&&nodes.get('lobby-dialog').open);
 assert.equal(calls.some(x=>['launch','host/start'].includes(x.path)),false);
 role('Create a lobby').onclick();field('Room name').value='DESKTOP';field('Your player name').value='Tester';
 assert.notEqual(settings.room,'DESKTOP','Editing a setup cannot launch or commit it accidentally.');
 ui.prepareLaunch();assert.equal(settings.lobbyRole,'host');assert.equal(settings.room,'DESKTOP');assert.equal(settings.lanRoom,'DESKTOP');
 assert.equal(calls.some(x=>['launch','host/start'].includes(x.path)),false,'Only the launcher green button may start hosting.');
 ui.join('join');field('Host address or invite').value='';assert.throws(()=>ui.prepareLaunch());
 field('Host address or invite').value=relay;field('Room name').value='LIVE';field('Your player name').value='Tester';ui.prepareLaunch();
 assert.equal(settings.relay,relay);assert.equal(settings.lobbyRole,'join');assert.equal(settings.room,'LIVE');
 ui.join('join',null,true);field('Host address or invite').value=relay;field('Room name').value='LIVE';assert.throws(()=>ui.prepareLaunch(),/favorite/);await form().onsubmit({preventDefault(){}});assert.equal(context.ZemaLobbyModel.favorites(storage).length,1);assert.equal(nodes.get('lobby-dialog').dataset.setup,'join');
 ui.browse('LAN');await flush();await flush();
 const content=nodes.get('servers-content'),toolbar=content.children[0],list=content.children[2];
 assert(text(list).includes('LIVE'),'The existing live-room policy feeds the inline browser.');
 const search=toolbar.children.find(e=>e.type==='search');search.value='not-present';search.listeners.input();assert(text(list).includes('No matching lobbies'));search.value='live';search.listeners.input();assert(text(list).includes('LIVE'));
 ui.activateDesktop(false);const before=calls.filter(x=>x.path==='lobbies/probe').length;await timers[1]();await flush();assert.equal(calls.filter(x=>x.path==='lobbies/probe').length,before,'A hidden multiplayer page must not keep probing.');
 ui.setDesktop(false);assert(!nodes.get('servers-dialog').open&&!nodes.get('lobby-dialog').open);ui.browse('LAN');await flush();assert(!text(nodes.get('servers-content')).includes('No matching lobbies'),'A desktop search cannot silently filter the touch browser.');
 await checkFinalLaunch();
 console.log('PASS desktop inline join/host validation, configure-before-launch, real final launch paths for Story/Free Roam/Join/Host, invalid-draft gate, live-room search, hidden-page polling, and touch restoration');
})().catch(error=>{console.error(error);process.exitCode=1;});
