'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),S=require('../launch-settings.js'),F=require('../browser-features.js'),T=require('../browser-trainer.js');
assert.equal(S.defaults.preset,'performance');assert.equal(S.defaults.fps,30);assert.equal(S.defaults.cores,4);
// Old saved settings and deep links must reach the runtime with a working pool.
for(const mode of ['lan','story','sandbox']){const saved=S.read({getItem:()=>JSON.stringify({mode,cores:2,room:'KEEP-ROOM',player:'KeepName',relay:'ws://192.168.1.2:47540/engine-lan'})});const restored=S.decode(new URL(S.url(saved),'http://localhost').search);assert.equal(S.query(restored,{width:1920,height:1080}).get('cores'),'4');assert.equal(restored.room,'KEEP-ROOM');assert.equal(restored.player,'KeepName');assert.equal(restored.relay,'ws://192.168.1.2:47540/engine-lan');assert.equal(restored.preset,'performance');assert.equal(restored.fps,30);}
assert.equal(S.decode('?mode=lan&cores=2').cores,4);
let q=S.query({}, {width:1920,height:1080});assert.equal(q.get('res'),'960x540');assert.equal(q.get('fixed'),'1');assert.equal(q.get('low'),'1');assert.equal(q.get('fps'),'30');
for(const preset of Object.keys(S.presets)){q=S.query({preset},{width:1920,height:1080});assert(q.get('args').includes('-shaderQuality=1'));assert.equal(q.get('args').split(',').length,12);assert(q.get('res').endsWith('x'+S.presets[preset].height));}
assert.equal(S.query({mode:'sandbox',newgame:true},{width:1,height:1}).has('newgame'),false);assert.equal(S.query({mode:'story',newgame:true},{width:1,height:1}).get('newgame'),'1');
assert.equal(S.normalize({preset:'__proto__',height:99999,fps:120,mouseSpeed:Infinity,fill:'true'}).preset,'performance');assert.deepEqual(S.read({getItem(){throw Error('blocked')}}),S.defaults);
assert.equal(S.decode('?mode=evil&args=-lan&height=2160&fps=999&controller=false').controller,false);assert.equal(S.decode('?mode=evil').mode,'sandbox');
for(const mode of ['story','sandbox','lan'])assert.equal(new URL(S.url({mode}),'http://localhost').pathname,'/play/'+mode);
const pad={connected:true,mapping:'standard',axes:[0,0,0,0],buttons:Array.from({length:17},()=>({pressed:false,value:0}))};
// Run the real input adapter against a disposable shared-memory block.
const events={},canvasEvents={},callbacks=[];let focused=true,gamepad=pad;
const memory={buffer:new SharedArrayBuffer(2048)},keys=new Uint8Array(memory.buffer,0,256),w=new Int32Array(memory.buffer,256,10);
const document={hidden:false,hasFocus:()=>focused,pointerLockElement:null,createElement:()=>({style:{},append(){}}),body:{append(){}},addEventListener:(k,f)=>events[k]=f};
const ctx={globalThis:null,document,addEventListener:(k,f)=>events[k]=f,navigator:{getGamepads:()=>gamepad?[gamepad]:[]},requestAnimationFrame:f=>{callbacks.push(f);return callbacks.length;},cancelAnimationFrame(){},ZemaBrowserFeatures:F,ZemaTrainer:T,performance:{now:()=>0},Atomics,Uint8Array,Uint16Array,Int32Array,Set,Number,Math,module:{exports:{}}};ctx.globalThis=ctx;
const features={pad:F.createPad(),trainer:T.createShared()};vm.runInNewContext(fs.readFileSync(root+'/controller.js','utf8'),ctx);const canvas={addEventListener:(k,f)=>canvasEvents[k]=f,getBoundingClientRect:()=>({left:0,top:0,width:960,height:540})};ctx.ZemaController.install(memory,0,canvas,[960,540],2,S.defaults,features);
assert.equal(new Int32Array(memory.buffer,440,1)[0],2);
const key=(code,key)=>({code,key,preventDefault(){}});events.keydown(key('KeyW','w'));callbacks.shift()(16);assert.equal(keys[87],128);gamepad=null;callbacks.shift()(32);assert.equal(keys[87],128);events.keyup(key('KeyW','w'));assert.equal(keys[87],0);
gamepad=pad;pad.buttons[7].value=.8;pad.axes[0]=.4;pad.axes[2]=-.6;callbacks.shift()(48);const analog=F.read(features.pad);assert(analog.active);assert(Math.abs(analog.triggers[1]-.8)<.0001);assert(Math.abs(analog.axes[0]-.4)<.0001);assert(analog.axes[2]<0);assert.equal(w[5],0);assert(keys.every(v=>v===0));focused=false;events.blur();assert(!F.read(features.pad).active);assert.equal(w[5],0);assert(keys.every(v=>v===0));callbacks.shift()(64);assert.equal(w[5],0);
focused=true;events.focus();document.pointerLockElement=canvas;events.mousemove({movementX:12,movementY:-7});assert.equal(w[0],492);assert.equal(w[1],263);assert.equal(w[2],12);assert.equal(w[3],-7);document.pointerLockElement=null;events.mousemove({clientX:492,clientY:263});assert.equal(w[2],12);assert.equal(w[3],-7);document.pointerLockElement=canvas;events.mousemove({movementX:5000,movementY:-5000});assert.equal(w[0],959);assert.equal(w[1],0);document.pointerLockElement=null;
ctx.ZemaInputSuspended=true;events.keydown(key('KeyW','w'));assert.equal(keys[87],0);ctx.ZemaInputSuspended=false;
for(const [code,value]of [['NumpadAdd',107],['NumpadDivide',111],['IntlBackslash',226],['CapsLock',20]]){events.keydown(key(code,''));assert.equal(keys[value],128);events.keyup(key(code,''));assert.equal(keys[value],0);}
events.pagehide();assert(keys.every(v=>v===0));assert(!F.read(features.pad).active);assert.deepEqual(Array.from(w.slice(2,5)),[0,0,0]);events.keydown(key('KeyW','w'));assert.equal(keys[87],0);
// The launcher cannot instantiate the game, even before the Play event handler.
const html=fs.readFileSync(root+'/launcher.html','utf8'),js=fs.readFileSync(root+'/launcher.js','utf8');assert(!html.includes('canvas'));assert(!/new Worker|WebAssembly\.|transferControlToOffscreen/.test(js));
assert(!/gyro|controlOpacity|controlScale/.test(js));
console.log('LAUNCH_SETTINGS_MODES_PRESETS_CONTROLLER_RELEASE_PASS');
