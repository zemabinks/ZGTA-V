'use strict';
const assert=require('assert'),fs=require('fs'),vm=require('vm'),path=require('path');
const root=path.dirname(__dirname),V=require('../voice-core.js');
const s=new V.Shared();assert.equal(s.buffer.byteLength,25984);s.setSpeaker(true);s.connection(true,0x0a4d0001);s.publish([5000,7000,20]);s.setMic(true);
let Processor;const sandbox={globalThis:{ZemaVoiceCore:V},AudioWorkletProcessor:class{},registerProcessor:(name,p)=>Processor=p,Int32Array,SharedArrayBuffer,DataView,Uint8Array,Float32Array,Atomics,Date,Math,Number,sampleRate:48000};
vm.runInNewContext(fs.readFileSync(path.join(root,'voice-worklet.js'),'utf8').replace("import './voice-core.js';",''),sandbox);
const processor=new Processor({processorOptions:{buffer:s.buffer}}),input=new Float32Array(128).fill(.25),l=new Float32Array(128),r=new Float32Array(128),packet=new Uint8Array(356);
for(let i=0;i<200;i++)processor.process([[input]],[[l,r]]);
let count=0;while(s.pull(true,packet)){count++;const p=V.packet(packet);assert.equal(p.from,0x0a4d0001);assert.deepEqual(p.pos,[5000,7000,20]);assert(packet.subarray(36).every(n=>n===V.encode(.25)));}
assert.equal(count,8);assert(l.every(n=>n===0),'No local microphone feedback');
const wire=new Uint8Array(356),audio=new Uint8Array(320).fill(V.encode(.3));
for(let i=0;i<100;i++)s.push(false,V.frame(wire,0x0a4d0002,i,[5001,7000,20],audio));
count=0;while(s.pull(false,packet))count++;assert.equal(count,64);
const m=new V.Mixer();assert(m.receive(V.frame(wire,0x0a4d0002,1,[5001,7000,20],audio),[5000,7000,20],s.vip,1000));assert(!m.receive(wire,[5000,7000,20],s.vip,1000));m.receive(V.frame(wire,0x0a4d0002,2,[5001,7000,20],audio),[5000,7000,20],s.vip,1000);
const out=new Float32Array(960);m.render(out,new Float32Array(960),[5000,7000,20],48000,1000);assert(out[0]>.28);m.render(new Float32Array(960),new Float32Array(960),[5040,7000,20],48000,1000);assert.equal(m.peers[1].read,m.peers[1].write);
s.setMic(false);for(let i=0;i<20;i++)processor.process([[input]],[[l,r]]);assert(!s.pull(true,packet));s.connection(false);assert(!s.mic);s.connection(true);s.publish([5000,7000,20]);processor.process([[input]],[[l,r]]);assert(l.every(n=>n===0));
const pos=[0,0,0];s.publish([1,2,3],123);assert(s.position(pos,124));assert(!s.position(pos,1124));
console.log('VOICE108_WORKLET_PASS');
