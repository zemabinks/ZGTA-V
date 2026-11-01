/* Bounded voice queues and wire codec shared by the network/game/audio workers.
 * Voice is ordinary room-scoped DATA on reserved virtual port 65534. Existing
 * relays authenticate its sender and isolate rooms without a protocol change. */
(function(root){'use strict';
 const PORT=65534,LENGTH=356,SLOT=360,IN=64,OUT=8,SIZE=64+(IN+OUT)*SLOT;
 const clock=()=>Date.now()>>>0,age=(now,then)=>(now-then)>>>0;
 const NEAR=2,RANGE=35;
 function distanceGain(d){if(d<=NEAR)return 1;if(d>=RANGE)return 0;const remaining=(RANGE-d)/(RANGE-NEAR);return remaining*remaining;}
 const valid=p=>p&&p.length===3&&p.every(Number.isFinite)&&Math.abs(p[0])<=20000&&Math.abs(p[1])<=20000&&Math.abs(p[2])<=5000;
 function encode(input){let n=Number.isFinite(input)?Math.trunc(Math.max(-1,Math.min(1,input))*32767):0;const mask=n<0?127:255;if(n<0)n=-n;n=Math.min(n,32635)+132;let s=0;for(let limit=255;n>limit&&s<7;limit=(limit<<1)|1)s++;return ((s<<4)|((n>>(s+3))&15))^mask;}
 function decode(code){const u=(~code)&255,n=((((u&15)<<3)+132)<<((u>>4)&7))-132;return (u&128?-n:n)/32768;}
 function envelope(b){return b?.length>=16&&b[0]===71&&b[1]===53&&b[2]===1&&b[3]===3&&b[8]===255&&b[9]===254&&b[14]===255&&b[15]===254;}
 function packet(b){
  if(!envelope(b)||b.length!==LENGTH||b[16]!==90||b[17]!==86||b[18]!==48||b[19]!==49||b[22]||b[23])return null;
  const v=new DataView(b.buffer,b.byteOffset,b.byteLength),from=v.getUint32(4),slot=from&65535,pos=[v.getFloat32(24),v.getFloat32(28),v.getFloat32(32)];
  return from>>>16===0x0a4d&&slot>=1&&slot<=32&&valid(pos)?{from,to:v.getUint32(10),sequence:v.getUint16(20),pos}:null;
 }
 function frame(target,vip,sequence,pos,audio){
  const v=new DataView(target.buffer,target.byteOffset,target.byteLength);target.set([71,53,1,3]);v.setUint32(4,vip);v.setUint16(8,PORT);v.setUint32(10,0xffffffff);v.setUint16(14,PORT);target.set([90,86,48,49],16);v.setUint16(20,sequence);v.setUint16(22,0);for(let i=0;i<3;i++)v.setFloat32(24+i*4,pos[i]);target.set(audio,36);return target;
 }
 class Shared {
  constructor(buffer=new SharedArrayBuffer(SIZE)){if(!(buffer instanceof SharedArrayBuffer)||buffer.byteLength!==SIZE)throw Error('Invalid voice buffer');this.buffer=buffer;this.words=new Int32Array(buffer,0,16);this.bytes=new Uint8Array(buffer);this.view=new DataView(buffer);}
  get vip(){return Atomics.load(this.words,0)>>>0;}get connected(){return Atomics.load(this.words,1)===1;}get mic(){return Atomics.load(this.words,2)===1;}get speaker(){return Atomics.load(this.words,3)===1;}
  connection(value,vip=this.vip){Atomics.store(this.words,0,vip|0);Atomics.store(this.words,1,value?1:0);Atomics.store(this.words,9,0);if(!value)Atomics.store(this.words,2,0);Atomics.add(this.words,14,1);}
  setMic(value){Atomics.store(this.words,2,value&&this.connected?1:0);Atomics.add(this.words,15,1);}
  setSpeaker(value){Atomics.store(this.words,3,value?1:0);Atomics.add(this.words,14,1);}
  publish(pos,now=clock()){Atomics.add(this.words,4,1);for(let i=0;i<3;i++)this.view.setFloat32(20+i*4,pos?.[i]||0,true);Atomics.store(this.words,8,now|0);Atomics.store(this.words,9,valid(pos)?1:0);Atomics.add(this.words,4,1);}
  position(target,now=clock()){
   const version=Atomics.load(this.words,4);if(version&1||!Atomics.load(this.words,9)||age(now,Atomics.load(this.words,8)>>>0)>1000)return false;
   for(let i=0;i<3;i++)target[i]=this.view.getFloat32(20+i*4,true);return version===Atomics.load(this.words,4)&&valid(target);
  }
  push(outgoing,bytes,now=clock()){
   if(!this.connected||outgoing&&!this.mic||!outgoing&&!this.speaker||bytes.length!==LENGTH)return false;
   const r=outgoing?12:10,w=r+1,cap=outgoing?OUT:IN,write=Atomics.load(this.words,w)>>>0,read=Atomics.load(this.words,r)>>>0;
   if(((write-read)>>>0)>=cap)return false;const at=64+(outgoing?IN*SLOT:0)+(write%cap)*SLOT;
   this.view.setUint32(at,now,true);this.bytes.set(bytes,at+4);Atomics.store(this.words,w,(write+1)|0);return true;
  }
  pull(outgoing,target,now=clock()){
   const r=outgoing?12:10,w=r+1,cap=outgoing?OUT:IN;
   for(let n=0;n<cap;n++){
    const read=Atomics.load(this.words,r)>>>0,write=Atomics.load(this.words,w)>>>0;if(read===write)return false;
    const at=64+(outgoing?IN*SLOT:0)+(read%cap)*SLOT,stale=age(now,this.view.getUint32(at,true))>100;
    if(!stale)target.set(this.bytes.subarray(at+4,at+4+LENGTH));Atomics.store(this.words,r,(read+1)|0);
    if(!stale&&this.connected&&(!outgoing||this.mic))return true;
   }return false;
  }
 }
 class Mixer {
  constructor(){this.peers=Array.from({length:32},()=>({samples:new Float32Array(4096),read:0,write:0,phase:0,heard:0,sequence:0,seen:false,playing:false,pos:[0,0,0],gain:0,gainValid:false}));this.smoothingRate=0;this.gainSlew=0;}
  clear(){for(const q of this.peers){q.read=q.write=0;q.playing=q.seen=q.gainValid=false;q.phase=0;}}
  receive(bytes,local,vip,now=clock()){
   const p=packet(bytes);if(!p||p.from===vip||p.to!==0xffffffff&&p.to!==vip||!valid(local))return false;
   const q=this.peers[(p.from&65535)-1],delta=(p.sequence-q.sequence)&65535;
   if(q.seen&&age(now,q.heard)<1000&&(delta===0||delta>=32768))return false;
   if(!q.seen||age(now,q.heard)>250){q.read=q.write=0;q.phase=0;q.playing=q.gainValid=false;}
   q.seen=true;q.sequence=p.sequence;q.heard=now;q.pos=p.pos;
   if(Math.hypot(...p.pos.map((n,i)=>n-local[i]))>=RANGE){q.read=q.write;q.playing=q.gainValid=false;return false;}
   if(q.write-q.read+320>4096)return false;
   for(let i=0;i<320;i++)q.samples[q.write++&4095]=decode(bytes[36+i]);return true;
  }
  render(left,right,local,rate,now=clock()){
   if(!valid(local)){this.clear();return;}
   if(this.smoothingRate!==rate){this.smoothingRate=rate;this.gainSlew=-Math.expm1(-1/(rate*.05));}
   for(const q of this.peers){
    const dx=q.pos[0]-local[0],dy=q.pos[1]-local[1],dz=q.pos[2]-local[2],d=Math.sqrt(dx*dx+dy*dy+dz*dz);
    if(!q.seen||age(now,q.heard)>250||d>=RANGE){q.read=q.write;q.playing=q.gainValid=false;continue;}
    if(!q.playing){if(q.write-q.read<640)continue;q.playing=true;}
    if(q.write-q.read>2400){q.read=q.write-1600;q.phase=0;}
    const target=distanceGain(d);
    if(!q.gainValid){q.gain=target;q.gainValid=true;}
    for(let i=0;i<left.length;i++){
     if(q.read>=q.write){q.playing=false;break;}
     q.gain+=(target-q.gain)*this.gainSlew;
     const a=q.samples[q.read&4095],b=q.read+1<q.write?q.samples[(q.read+1)&4095]:a,v=(a+(b-a)*q.phase)*q.gain;
     left[i]+=v;right[i]+=v;q.phase+=16000/rate;const advance=Math.floor(q.phase);q.phase-=advance;q.read=Math.min(q.write,q.read+advance);
    }
   }
   for(let i=0;i<left.length;i++){left[i]=Math.max(-1,Math.min(1,left[i]));right[i]=Math.max(-1,Math.min(1,right[i]));}
  }
 }
 const api={PORT,LENGTH,SIZE,clock,age,valid,encode,decode,envelope,packet,frame,Shared,Mixer};root.ZemaVoiceCore=api;if(typeof module==='object')module.exports=api;
})(globalThis);
