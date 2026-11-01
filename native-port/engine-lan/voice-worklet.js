import './voice-core.js';
/* Voice alone runs here. This node never receives or controls GTA game audio. */
class ZemaVoiceProcessor extends AudioWorkletProcessor {
 constructor(options){super();const V=globalThis.ZemaVoiceCore;this.shared=new V.Shared(options.processorOptions.buffer);this.mixer=new V.Mixer();this.pos=[0,0,0];this.packet=new Uint8Array(V.LENGTH);this.capture=new Uint8Array(320);this.count=this.sum=this.weight=this.sequence=0;this.playEpoch=this.micEpoch=-1;}
 process(inputs,outputs){
  const V=globalThis.ZemaVoiceCore,s=this.shared,w=s.words,now=V.clock(),out=outputs[0];if(!out?.[0])return true;
  const epoch=Atomics.load(w,14),micEpoch=Atomics.load(w,15);
  if(epoch!==this.playEpoch){this.mixer.clear();this.playEpoch=epoch;Atomics.store(w,10,Atomics.load(w,11));}
  if(micEpoch!==this.micEpoch){this.count=this.sum=this.weight=0;this.micEpoch=micEpoch;}
  if(!s.connected||!s.position(this.pos,now)){this.mixer.clear();this.count=this.sum=this.weight=0;return true;}
  if(s.speaker){for(let i=0;i<64&&s.pull(false,this.packet,now);i++)this.mixer.receive(this.packet,this.pos,s.vip,now);this.mixer.render(out[0],out[1]||out[0],this.pos,sampleRate,now);}
  const input=inputs[0]?.[0];
  if(s.mic&&input){
   /* Area resampling preserves phase across 128-frame render quanta and routes
    * at 44.1/48 kHz. No per-quantum arrays, messages or AudioBuffer nodes. */
   const width=sampleRate/16000;
   for(let i=0;i<input.length;i++){
    let remaining=1;
    while(remaining>1e-9){const take=Math.min(remaining,width-this.weight);this.sum+=(Number.isFinite(input[i])?input[i]:0)*take;this.weight+=take;remaining-=take;
     if(this.weight>=width-1e-9){this.capture[this.count++]=V.encode(this.sum/width);this.sum=this.weight=0;
      if(this.count===320){this.count=0;V.frame(this.packet,s.vip,++this.sequence&65535,this.pos,this.capture);s.push(true,this.packet,now);}
     }
    }
   }
  }else this.count=this.sum=this.weight=0;
  return true;
 }
}
registerProcessor('zgta-proximity-voice',ZemaVoiceProcessor);
