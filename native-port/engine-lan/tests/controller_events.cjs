'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(process.argv[2]),scenario=process.argv[3],F=require(path.join(root,'browser-features.js')),T=require(path.join(root,'browser-trainer.js'));
function target(){const events=new Map();return {style:{},append(){},addEventListener(name,fn){if(!events.has(name))events.set(name,[]);events.get(name).push(fn);},fire(name,event={}){for(const fn of events.get(name)||[])fn(event);}};}
const main=target(),document=target(),canvas=target();let focused=true,serial=0;const frames=new Map();
Object.assign(document,{hidden:false,pointerLockElement:null,hasFocus:()=>focused,createElement:()=>target(),body:target()});
canvas.getBoundingClientRect=()=>({left:0,top:0,width:800,height:600});canvas.requestPointerLock=()=>undefined;
const settings={keyboardMouse:true,controller:true,mouseSpeed:1,invertY:false,lookSensitivity:2.5,aimSensitivity:2.5,targetingMode:1},features={pad:F.createPad(),trainer:T.createShared()};
const pad={connected:true,mapping:'standard',axes:[.5,0,0,0],buttons:Array.from({length:16},()=>({pressed:false,value:0}))};pad.buttons[0].pressed=true;
const context={module:{exports:{}},document,navigator:{getGamepads:()=>[pad]},ZemaBrowserFeatures:F,ZemaTrainer:T,SharedArrayBuffer,Atomics,Int32Array,Uint8Array,Uint16Array,Promise,console,
 addEventListener:main.addEventListener.bind(main),requestAnimationFrame:fn=>{frames.set(++serial,fn);return serial;},cancelAnimationFrame:id=>frames.delete(id)};
vm.runInNewContext(fs.readFileSync(path.join(root,'controller.js'),'utf8'),context);
const memory=new WebAssembly.Memory({initial:1,maximum:2,shared:true}),block=4096,keys=new Uint8Array(memory.buffer,block,256),w=new Int32Array(memory.buffer,block+256,10);
const controller=context.module.exports.install(memory,block,canvas,[800,600],0,settings,features);
function frame(){const [id,fn]=frames.entries().next().value;frames.delete(id);fn();}
function event(extra={}){return {code:'KeyW',key:'w',button:0,movementX:12,movementY:-7,clientX:400,clientY:300,deltaY:-200,deltaMode:0,preventDefault(){this.prevented=true;},...extra};}
function prime(){document.pointerLockElement=canvas;document.fire('pointerlockchange');main.fire('keydown',event());canvas.fire('mousedown',event());main.fire('mousemove',event());main.fire('wheel',event());frame();assert.equal(keys[87],128);assert.equal(w[5],1);assert.equal(w[2],12);assert.equal(w[4],2);assert(F.read(features.pad).active);}
function released(){assert.equal(keys[87],0);assert.equal(w[5],0);assert.deepEqual(Array.from(w.slice(2,5)),[0,0,0]);assert.equal(F.read(features.pad).active,false);}
(async()=>{
 if(scenario==='release'){
  prime();controller.release();released();main.fire('wheel',event({deltaY:-50}));assert.equal(w[4],0);controller.release();main.fire('wheel',event({deltaY:-60}));assert.equal(w[4],0,'Fractional wheel input must also reset');
 }else if(scenario==='hidden'){
  prime();document.hidden=true;document.fire('visibilitychange');released();assert.equal(w[6],0,'Visibility loss must clear focus even without blur');
  const key=event();main.fire('keydown',key);main.fire('mousemove',event());main.fire('wheel',event());frame();released();assert.equal(key.prevented,undefined);
  document.hidden=false;document.fire('visibilitychange');frame();assert.equal(w[6],1);assert.equal(keys[87],0);assert(F.read(features.pad).active);
 }else if(scenario==='suspended'){
  prime();context.ZemaInputSuspended=true;frame();released();assert.equal(w[6],0);main.fire('keydown',event());assert.equal(keys[87],0);
  context.ZemaInputSuspended=false;frame();assert.equal(w[6],1);assert.equal(keys[87],0);
 }else if(scenario==='pointer-loss'){
  prime();document.pointerLockElement=null;document.fire('pointerlockchange');released();assert.equal(w[7],0);
 }else if(scenario==='unload'){
  prime();main.fire('pagehide');released();assert.equal(w[6],0);assert.equal(frames.size,0);main.fire('keydown',event());main.fire('mousemove',event());released();
 }else if(scenario==='pointer-rejection'){
  let calls=0;canvas.requestPointerLock=()=>{calls++;return Promise.reject(Error('fixture pointer lock denied'));};canvas.fire('mousedown',event());await new Promise(setImmediate);assert.equal(calls,2);
  calls=0;canvas.requestPointerLock=()=>{calls++;throw Error('fixture old API');};assert.doesNotThrow(()=>canvas.fire('mousedown',event()));assert.equal(calls,2);controller.release();
 }else if(scenario==='ordinary-input'){
  main.fire('keydown',event({code:'KeyI',key:'i'}));assert.equal(keys[73],128);assert.equal(keys[104],128);main.fire('keyup',event({code:'KeyI'}));assert.equal(keys[73],0);assert.equal(keys[104],0);
  main.fire('keydown',event({code:'F12',key:'F12'}));assert.equal(keys[123],0);frame();const state=F.read(features.pad);assert(state.active&&state.axes[0]>.49&&state.buttons&64);
  memory.grow(1);main.fire('keydown',event());assert.equal(new Uint8Array(memory.buffer,block,256)[87],128);focused=false;main.fire('blur');released();assert.equal(w[6],0);
 }else throw Error('Unknown scenario');
 console.log('BROWSER_CONTROLLER_EVENTS_PASS '+scenario);
})().catch(error=>{console.error(error);process.exitCode=1;});
