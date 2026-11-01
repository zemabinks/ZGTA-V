(function(root){'use strict';
 function mount(buffer,panel,base){
  const s=new ZemaVoiceCore.Shared(buffer),region=document.createElement('section'),controls=document.createElement('div'),mic=document.createElement('button'),speaker=document.createElement('button'),status=document.createElement('small');
  region.className='connection-voice';controls.className='connection-actions';mic.type=speaker.type='button';mic.className=speaker.className='connection-secondary';status.className='connection-detail';status.setAttribute('role','status');controls.append(mic,speaker);region.append(controls,status);panel.querySelector('.connection-panel').append(region);
  s.setSpeaker(true);
  let context=null,node=null,source=null,stream=null,preparing=null,request=0,closed=false;
  function render(){mic.textContent=s.mic?'Microphone on':'Microphone off';speaker.textContent=s.speaker?'Nearby voice on':'Nearby voice off';mic.setAttribute('aria-pressed',String(s.mic));speaker.setAttribute('aria-pressed',String(s.speaker));mic.disabled=!s.connected;}
  async function audio(){
   if(preparing)return preparing;
   preparing=(async()=>{if(!context){context=new AudioContext({latencyHint:'interactive'});await context.audioWorklet.addModule(base+'voice-worklet.js');node=new AudioWorkletNode(context,'zgta-proximity-voice',{numberOfInputs:1,numberOfOutputs:1,outputChannelCount:[2],processorOptions:{buffer}});node.connect(context.destination);}await context.resume();})();
   try{await preparing;}catch(error){node?.disconnect();node=null;if(context)await context.close().catch(()=>{});context=null;throw error;}finally{preparing=null;}
  }
  function stopMic(){++request;s.setMic(false);source?.disconnect();source=null;stream?.getTracks().forEach(t=>t.stop());stream=null;render();}
  const errorText=e=>e.name==='NotAllowedError'?'Microphone access is off. Allow it for this ZGTA V page in browser settings.':e.name==='NotFoundError'?'No microphone found. Connect one and try again.':'Voice audio could not start. Check your audio device and try again.';
  mic.onclick=async()=>{
   if(s.mic){stopMic();status.textContent='Microphone off · nearby players within 35 m';return;}
   const token=++request;mic.disabled=true;
   try{
    await audio();if(closed||token!==request||!s.connected||document.hidden)return;
    const captured=await navigator.mediaDevices.getUserMedia({video:false,audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true,channelCount:1}});
    if(closed||token!==request||!s.connected||document.hidden){captured.getTracks().forEach(t=>t.stop());return;}
    stream=captured;source=context.createMediaStreamSource(stream);source.connect(node);s.setMic(true);status.textContent='Speaking to nearby players · up to 35 m';
    stream.getAudioTracks().forEach(t=>t.addEventListener('ended',()=>{stopMic();status.textContent='Microphone disconnected';},{once:true}));
   }catch(error){stopMic();status.textContent=errorText(error);}finally{render();}
  };
  speaker.onclick=async()=>{try{await audio();if(closed||document.hidden)return;s.setSpeaker(!s.speaker);status.textContent=s.speaker?'Hearing nearby players · up to 35 m':'Nearby voice muted · game audio unchanged';}catch(error){status.textContent=errorText(error);}render();};
  const unlock=()=>{if(!closed&&s.connected)audio().then(()=>{status.textContent='Nearby voice · up to 35 m';}).catch(error=>{status.textContent=errorText(error);});};
  const background=()=>{if(document.hidden){stopMic();s.setSpeaker(false);status.textContent='Voice paused while this tab is hidden. Enable it when you return.';}};
  document.addEventListener('pointerdown',unlock,{once:true});document.addEventListener('visibilitychange',background);
  let wasConnected=s.connected;const timer=setInterval(()=>{if(wasConnected&&!s.connected){stopMic();status.textContent='Voice disconnected · reconnect to your lobby';}wasConnected=s.connected;render();},250);
  status.textContent='Nearby voice · up to 35 m';render();
  return {destroy(){closed=true;clearInterval(timer);stopMic();node?.disconnect();context?.close();document.removeEventListener('pointerdown',unlock);document.removeEventListener('visibilitychange',background);region.remove();}};
 }
 root.ZemaVoiceUI={mount};
})(globalThis);
