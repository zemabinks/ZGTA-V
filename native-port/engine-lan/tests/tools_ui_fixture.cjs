'use strict';
const assert=require('node:assert/strict'),path=require('node:path'),root=process.argv[2];
class Element{constructor(tag,text=''){this.tag=tag;this.textContent=text;this.children=[];this.style={};this.disabled=false;this._value='';}get value(){if(this.tag==='select'&&!this._value){const first=e=>e.tag==='option'?e:e.children.map(first).find(Boolean);return this.children.map(first).find(Boolean)?.value||'';}return this._value;}set value(v){this._value=v;}append(...items){this.children.push(...items);}replaceChildren(...items){this.children=[...items];}setAttribute(name,value){this[name]=value;}}
global.document={createElement:tag=>new Element(tag)};global.addEventListener=()=>{};global.setInterval=()=>1;
global.ZemaTrainer=require(path.join(root,'browser-trainer.js'));require(path.join(root,'vehicle-catalog.js'));require(path.join(root,'vehicle-ui.js'));require(path.join(root,'trainer-ui.js'));
const shared=ZemaTrainer.createShared(),w=new Int32Array(shared);Atomics.store(w,6,1);global.ZemaGameReady=true;
const container=new Element('section'),runtime={features:{trainer:shared}},ui=ZemaTrainerUI.mount(container,{runtime,mode:()=> 'lan'});
const walk=e=>[e,...e.children.flatMap(walk)],all=walk(container),button=text=>all.find(e=>e.tag==='button'&&e.textContent===text),output=all.find(e=>e.tag==='output');
assert(button('Apply cheat').disabled);assert.equal(button('Spawn vehicle').disabled,false);assert.equal(button('Spawn to waypoint').disabled,false);
button('Apply cheat').onclick();assert.equal(ZemaTrainer.status(shared).sequence,0);assert.match(output.textContent,/disabled/);
button('Spawn vehicle').onclick();assert.equal(ZemaTrainer.status(shared).type,2);ui.refresh();assert(button('Spawn to waypoint').disabled);button('Spawn to waypoint').onclick();assert.equal(ZemaTrainer.status(shared).type,2);assert.match(output.textContent,/running|cleanup/);
ui.refresh();assert.match(output.textContent,/Waypoint teleport not queued/);
Atomics.store(w,4,Atomics.load(w,0));Atomics.store(w,3,-12);ui.refresh();assert.match(output.textContent,/Waypoint teleport not queued/);assert.doesNotMatch(output.textContent,/Vehicle creation failed|base-game model/);assert.equal(button('Spawn to waypoint').disabled,false);
button('Spawn to waypoint').onclick();assert.equal(ZemaTrainer.status(shared).type,3);button('Cancel current action').onclick();ui.refresh();assert.equal(ZemaTrainer.status(shared).result,-5);assert.match(output.textContent,/cancelled/);
Atomics.store(w,8,1);ui.refresh();assert(button('Spawn vehicle').disabled);assert.equal(button('Cancel current action').disabled,false);assert.match(output.textContent,/request/);
Atomics.store(w,8,0);ui.refresh();const model=all.find(e=>e.tag==='input');assert(model.maxLength>=64);
const previousSequence=ZemaTrainer.status(shared).sequence;model.value='a'.repeat(64);button('Spawn vehicle').onclick();
assert.equal(ZemaTrainer.status(shared).sequence,previousSequence);assert.match(output.textContent,/1–63/);
console.log('LAN_TOOLS_UI_QUEUES_REAL_BUFFER_WAYPOINT_SPAWN_AND_KEEPS_CHEATS_DISABLED_PASS');
