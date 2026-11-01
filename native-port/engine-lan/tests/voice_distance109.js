'use strict';
const V=require('../voice-core.js');
const local=[100,100,20], audio=new Uint8Array(320).fill(V.encode(.3)), wire=new Uint8Array(356);
function send(m,sequence,listener){m.receive(V.frame(wire,0x0a4d0001,sequence,local,audio),listener,0x0a4d0002,1000);}
function render(m,listener,rate){const l=new Float32Array(Math.round(rate*.02)),r=new Float32Array(l.length);m.render(l,r,listener,rate,1000);return l;}
function mean(l){return l.reduce((a,b)=>a+b,0)/l.length;}
const distances=[0,2,5,10,20,30,34,35], levels={};
for(const rate of [44100,48000,96000]){
 levels[rate]=distances.map(d=>{const m=new V.Mixer(),listener=[100+d,100,20];send(m,1,listener);send(m,2,listener);return mean(render(m,listener,rate));});
}
const m=new V.Mixer();send(m,1,local);send(m,2,local);const near=render(m,local,48000),trace=[];
for(let i=0;i<15;i++){send(m,i+3,[120,100,20]);trace.push(...render(m,[120,100,20],48000));}
const far=render(m,[135,100,20],48000);
send(m,100,[120,100,20]);send(m,101,[120,100,20]);const returned=render(m,[120,100,20],48000);
console.log(JSON.stringify({distances,levels,near:near[near.length-1],trace,far:mean(far),returned:mean(returned)}));
