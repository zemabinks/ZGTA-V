/* Read-only native loading state: a character menu need not draw a 3D world. */
(function(root){'use strict';
 class Tracker{
  constructor(buffer){this.w=new Int32Array(buffer);this.sequence=0;this.lastUpdate=-Infinity;this.inactiveSince=null;this.done=false;}
  sample(firstFrame,now){const w=this.w,seq=Atomics.load(w,18);if(seq!==this.sequence){this.sequence=seq;this.lastUpdate=now;}const active=Atomics.load(w,14),seen=Atomics.load(w,15)===1;
   if(!firstFrame||!seq||!seen||active!==0||now-this.lastUpdate>500){this.inactiveSince=null;return false;}
   if(this.inactiveSince===null)this.inactiveSince=now;if(!this.done&&now-this.inactiveSince>=1500){this.done=true;return true;}return false;
  }
 }
 if(typeof window!=='undefined')addEventListener('DOMContentLoaded',()=>{
  if(root.ZemaRuntime?.settings.mode!=='lan')return;const tracker=new Tracker(root.ZemaRuntime.features.pad),queue=[],channels=[];let firstFrame=false,blocked=false,stopped=false,sending=false,lastState='',lastSnapshot=-Infinity,timer;
  const noisy=new Map();let noiseTime=performance.now(),lastSession='';
  // Coalesce every exact repeated line, including GTA's per-frame joining spinner.
  // Keep its first occurrence and a bounded five-second repeat count so errors
  // and lock/session observations cannot be evicted by one repeated message.
  function note(text){text=String(text);let key=/\[HEAD BLEND\]/.test(text)?'[HEAD BLEND]':/NetStallDetect/.test(text)?'NetStallDetect':/\[Audio_NorthAudio\]/.test(text)?text.replace(/Logging script bank info @ Time.*$/,'Logging script bank info').slice(0,512):text.slice(0,512);if(key){if(!noisy.has(key)&&noisy.size>=128)noisy.delete(noisy.keys().next().value);const count=noisy.get(key)||0;noisy.set(key,Math.min(count+1,Number.MAX_SAFE_INTEGER));if(count)return;}queue.push(text.slice(0,512));if(queue.length>256)queue.splice(0,queue.length-256);}
  function listen(name,fn){const channel=new BroadcastChannel(root.ZemaLaunchChannels.name(name));channel.onmessage=e=>fn(e.data);channels.push(channel);return channel;}
  const progress=listen('game-progress',m=>{const gpuLost=Object.prototype.hasOwnProperty.call(m,'gpuLost')&&m.gpuLost!==false;if(m.pct>=76)firstFrame=true;if(m.error||gpuLost||m.gpuInitFailed){blocked=true;note('[progress] '+(m.error?String(m.error):gpuLost?'Graphics device disconnected':'Graphics initialization failed'));}else if(m.label)note('[progress] '+m.label);});
  listen('game-log',text=>{for(const line of String(text).split('\n'))if(/error|fail|warn|abort|online|network|script|transition|freemode|cloud|stats|gpu|pipeline|shader|loading|readback|frame|text-missing|blip-missing|blip-fallback|world-tools|freeze|mutex|semaphore|thread|waits on/i.test(line))note(line);});
  listen('game-crash',m=>{blocked=true;const text=String(m.text).split('\n')[0].slice(0,240);note('[crash] '+String(m.kind)+' '+String(m.text));progress.postMessage({error:'Game worker stopped: '+text+' Return to the launcher before retrying.'});});
  async function flush(){if(sending||!queue.length||stopped)return;sending=true;try{await fetch('/zema-lab/runtime',{method:'POST',headers:{'Content-Type':'application/json','X-Zema-Lab':'1'},body:JSON.stringify({lines:queue.splice(0,24)})});}catch(_){}finally{sending=false;}}
  timer=setInterval(()=>{if(stopped)return;if(performance.now()-noiseTime>=5000){for(const [key,count]of noisy)if(count>1)queue.push(('[diagnostic repeats] '+(count-1)+' '+key).slice(0,512));noisy.clear();noiseTime=performance.now();}const w=tracker.w,state=[Atomics.load(w,14),Atomics.load(w,15),Atomics.load(w,18)>0,firstFrame].join('/');if(state!==lastState||performance.now()-lastSnapshot>=5000){lastState=state;lastSnapshot=performance.now();note('[loading] native-active/seen/ticks/first-frame '+[Atomics.load(w,14),Atomics.load(w,15),Atomics.load(w,18),firstFrame].join('/'));}
   const seq=Atomics.load(w,21);if(seq&&!(seq&1)){const session=[Atomics.load(w,19),Atomics.load(w,20)].join('/');if(seq===Atomics.load(w,21)&&session!==lastSession){lastSession=session;note('[session] native-state/players '+session+' (observation only)');}}
   if(tracker.sample(firstFrame&&!blocked,performance.now())){note('[loading] native loading screen ended; reveal multiplayer frontend');progress.postMessage({frontend:true,label:'Multiplayer screen ready'});}flush();
  },250);
  addEventListener('pagehide',()=>{stopped=true;clearInterval(timer);for(const channel of channels)channel.close();},{once:true});
 });
 const api={Tracker};root.ZemaLanLoading=api;if(typeof module==='object')module.exports=api;
})(globalThis);
