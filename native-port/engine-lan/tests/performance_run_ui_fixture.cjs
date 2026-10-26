'use strict';
// Exercise the real unified Mod Manager + measurement DOMContentLoaded listeners,
// not a hand-created legacy panel that could conceal an integration mismatch.
const a=require('node:assert/strict'),path=require('node:path'),root=process.argv[2];
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.style={};this.hidden=false;this.disabled=false;this._value='';this.textContent='';this.events={};}
 append(...items){this.children.push(...items);}replaceChildren(...items){this.children=[...items];}
 setAttribute(name,value){this[name]=value;}removeAttribute(name){delete this[name];}
 addEventListener(name,fn){(this.events[name]??=[]).push(fn);}
 focus(){document.activeElement=this;}
 click(){if(!this.disabled)this.onclick?.();if(this.tag==='a')downloads.push(this);}
 get value(){if(this.tag==='select'&&!this._value){const find=e=>e.tag==='option'?e:e.children.map(find).find(Boolean);return this.children.map(find).find(Boolean)?.value||'';}return this._value;}
 set value(v){this._value=v;}
}
const walk=e=>[e,...e.children.flatMap(walk)],events={},body=new Element('body'),timers=new Map(),channels=[],downloads=[],blobs=[],timeouts=[];
let now=0,nextTimer=0,closed=0;
const canvas=new Element('canvas');canvas.id='canvas';canvas.width=768;canvas.height=432;body.append(canvas);
global.window={};global.document={body,hidden:false,createElement:tag=>new Element(tag),getElementById:id=>walk(body).find(e=>e.id===id)||null,exitPointerLock:()=>{}};
global.addEventListener=(name,fn)=>{(events[name]??=[]).push(fn);};
document.addEventListener=global.addEventListener;document.dispatchEvent=event=>{for(const fn of events[event.type]||[])fn(event);return true;};
global.setInterval=fn=>{const id=++nextTimer;timers.set(id,fn);return id;};global.clearInterval=id=>timers.delete(id);
global.setTimeout=fn=>{timeouts.push(fn);return timeouts.length;};
global.performance={now:()=>now};global.innerWidth=1280;global.innerHeight=720;
if(!global.crypto)global.crypto=require('node:crypto').webcrypto;
global.BroadcastChannel=class {constructor(name){this.name=name;channels.push(this);}close(){closed++;}};
const revoked=[];URL.createObjectURL=blob=>{blobs.push(blob);return 'blob:performance-'+blobs.length;};URL.revokeObjectURL=url=>revoked.push(url);
global.fetch=async()=>a.fail('LAN performance measurement must not read or upload mod data');
global.ZemaTrainer=require(path.join(root,'browser-trainer.js'));
global.ZemaRuntime={settings:{mode:'lan',preset:'performance',height:432,fps:60,cores:4},features:{trainer:ZemaTrainer.createShared()}};
global.ZemaBenchmarkEngine='pinned-test-engine';global.ZemaGameReady=false;
global.ZemaGameInput={release:()=>{}};Atomics.store(new Int32Array(ZemaRuntime.features.trainer),6,1);
for(const name of ['browser-mods-ui.js','vehicle-catalog.js','vehicle-ui.js','trainer-ui.js','performance-run.js'])require(path.join(root,name));
a.equal(walk(body).length,2,'No manager or measurement before DOMContentLoaded');
for(const fn of events.DOMContentLoaded)fn();
const named=text=>walk(body).find(e=>e.tag==='button'&&e.textContent===text),panel=document.getElementById('zema-mod-manager');
a.ok(panel,'The actual trainer module must create the shared panel');a.equal(document.getElementById('zema-trainer-panel'),null);
a.equal(walk(panel).filter(e=>e.tag==='h3'&&e.textContent==='Performance check').length,1);
const sustained=named('Measure 3min FPS'),measure=named('Measure 30s FPS'),cancel=named('Cancel measurement'),save=named('Save performance report'),status=walk(panel).find(e=>e.tag==='output'&&e.textContent==='No measurement yet.');
a.ok(sustained&&measure&&cancel&&save&&status,'All measurement controls mount inside the actual unified manager');
a.ok(measure.disabled);a.ok(cancel.hidden);a.ok(save.hidden);a.equal(channels.length,1);a.equal(channels[0].name,global.ZemaFPSChannel);
const sample=(time,fps=60)=>{now=time;channels[0].onmessage({data:{fps}});};
measure.onclick();sample(500);a.equal(status.textContent,'No measurement yet.');a.equal(blobs.length,0);
global.ZemaGameReady=true;sample(1000);a.equal(measure.disabled,false);
const manager=walk(body).find(e=>e.tag==='button'&&e['aria-label']==='Mod Manager');manager.click();a.equal(panel.hidden,false);a.equal(global.ZemaInputSuspended,true);
document.dispatchEvent(new CustomEvent('zema-ui-panel-open',{detail:'connection'}));a.equal(panel.hidden,true);a.equal(global.ZemaInputSuspended,false,'Opening Connection must release the manager input owner');manager.click();
measure.click();a.equal(panel.hidden,true);a.equal(global.ZemaInputSuspended,false);a.ok(measure.disabled);a.equal(cancel.hidden,false);a.ok(save.hidden);a.equal(blobs.length,0,'Starting must not save or upload');
for(let t=1500;t<=33000;t+=500)sample(t);
a.match(status.textContent,/Average 60\.0 FPS/);a.ok(cancel.hidden);a.equal(save.hidden,false);a.equal(measure.disabled,false);a.equal(downloads.length,0,'Completion must not download automatically');
// Save is explicitly requested and exports only the completed run/context.
save.click();a.equal(downloads.length,1);a.equal(downloads[0].download,'ZGTA-performance.json');a.equal(blobs.length,1);a.equal(blobs[0].type,'application/json');
// Restart invalidates the old result and leaves no downloadable partial report.
now=34000;measure.click();a.ok(save.hidden);cancel.click();a.match(status.textContent,/cancelled/);save.onclick();a.equal(blobs.length,1);
now=35000;measure.click();document.hidden=true;for(const fn of events.visibilitychange)fn();a.match(status.textContent,/hidden/);a.ok(save.hidden);document.hidden=false;
now=36000;measure.click();for(const fn of events.keydown)fn({code:'Escape'});a.match(status.textContent,/menu key/);a.ok(save.hidden);
now=37000;measure.click();now=39000;for(const fn of [...timers.values()])fn();a.match(status.textContent,/samples stopped/);a.ok(save.hidden);
now=40000;sustained.click();a.ok(sustained.disabled);a.ok(measure.disabled);
for(let t=40500;t<=222000;t+=500)sample(t,t<=132000?60:30);
a.match(status.textContent,/Average 45\.0 FPS/);a.equal(sustained.disabled,false);save.click();a.equal(blobs.length,2);
now=223000;measure.click();for(const fn of events.pagehide)fn();a.equal(closed,1);a.equal(timers.size,0);a.equal(ZemaTrainer.status(ZemaRuntime.features.trainer).sequence,0,'FPS controls never queue game actions');
(async()=>{const report=JSON.parse(await blobs[0].text());a.equal(report.durationMS,30000);a.equal(report.averageFPS,60);a.equal(report.context.mode,'lan');a.equal(report.context.height,432);a.equal(report.context.engineSHA,'pinned-test-engine');a.equal(report.format,'zgta-performance-v2');a.equal(report.conditions.canvasWidth.minimum,768);a.equal(report.conditions.canvasHeight.observations,31);a.deepEqual(report.comparisonWarnings,[]);a.equal(report.conditions.appFootprintBytes,undefined);a.equal(report.conditions.thermalState,undefined);const sustainedReport=JSON.parse(await blobs[1].text());a.equal(sustainedReport.durationMS,180000);a.equal(sustainedReport.timeline.length,180);a.equal(sustainedReport.timeline.at(-1).fps,30);for(const fn of timeouts)fn();a.deepEqual(revoked,['blob:performance-1','blob:performance-2']);console.log('PASS real unified-manager FPS mount, readiness/explicit start, completed save, restart/manual/visibility/menu/stale cancellation and page cleanup');})().catch(error=>{console.error(error);process.exitCode=1;});
