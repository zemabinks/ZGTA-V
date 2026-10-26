'use strict';
const a=require('node:assert/strict'),path=require('node:path'),root=process.argv[2];
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.style={};this.hidden=false;this._value='';this.textContent='';this.events={};}
 append(...items){this.children.push(...items);}
 replaceChildren(...items){this.children=[...items];}
 setAttribute(name,value){this[name]=value;}
 addEventListener(name,fn){this.events[name]=fn;}
 focus(){document.activeElement=this;}
 get value(){if(this.tag==='select'&&!this._value){const find=e=>e.tag==='option'?e:e.children.map(find).find(Boolean);return this.children.map(find).find(Boolean)?.value||'';}return this._value;}
 set value(v){this._value=v;}
}
const events={},body=new Element('body');let reads=0,releases=0;
global.window={};global.document={body,createElement:tag=>new Element(tag),exitPointerLock:()=>{}};
global.addEventListener=(name,fn)=>{(events[name]??=[]).push(fn);};global.document.addEventListener=global.addEventListener;global.document.dispatchEvent=event=>{for(const fn of events[event.type]||[])fn(event);};global.CustomEvent=class{constructor(type,init){this.type=type;this.detail=init.detail;}};global.setInterval=()=>1;global.clearInterval=()=>{};
global.fetch=async(url,opts)=>{a.equal(url,'/zema-lab/mods');a.equal(opts.method,'GET');reads++;return {ok:true,json:async()=>({packs:[],launchNote:'Next launch'})};};
global.ZemaTrainer=require(path.join(root,'browser-trainer.js'));
global.ZemaRuntime={settings:{mode:'lan'},features:{trainer:ZemaTrainer.createShared()}};
global.ZemaGameReady=true;Atomics.store(new Int32Array(ZemaRuntime.features.trainer),6,1);
global.ZemaGameInput={release:()=>releases++};
require(path.join(root,'browser-mods-ui.js'));require(path.join(root,'vehicle-catalog.js'));require(path.join(root,'vehicle-ui.js'));require(path.join(root,'trainer-ui.js'));
for(const fn of events.DOMContentLoaded)fn();
const walk=e=>[e,...e.children.flatMap(walk)],all=walk(body),panel=all.find(e=>e.id==='zema-mod-manager'),button=all.find(e=>e.tag==='button'&&e['aria-label']==='Mod Manager');
const named=name=>walk(body).find(e=>e.tag==='button'&&e.textContent===name);
a.ok(panel.hidden);a.equal(panel.role,'dialog');a.equal(reads,0);a.equal(ZemaTrainer.status(ZemaRuntime.features.trainer).sequence,0);
button.onclick();a.equal(panel.hidden,false);a.equal(global.ZemaInputSuspended,true);a.equal(releases,1);
a.equal(named('Apply cheat').disabled,true);a.equal(named('Spawn vehicle').disabled,false);
named('Installed mods').onclick();a.equal(reads,1);a.equal(named('Installed mods')['aria-pressed'],'true');
named('Play tools').onclick();a.equal(named('Play tools')['aria-pressed'],'true');
named('Spawn vehicle').onclick();a.equal(ZemaTrainer.status(ZemaRuntime.features.trainer).type,2);
named('Done').onclick();a.equal(panel.hidden,true);a.equal(global.ZemaInputSuspended,false);a.equal(document.activeElement,button);
global.ZemaInputSuspended=true;button.onclick();named('Done').onclick();a.equal(global.ZemaInputSuspended,true,'Restore suspension owned by a different screen');
a.equal(walk(body).filter(e=>e.id==='zema-mod-manager').length,1);
console.log('PASS unified entry, real world-tool queue, LAN cheat restriction, lazy mod API and input restoration');
