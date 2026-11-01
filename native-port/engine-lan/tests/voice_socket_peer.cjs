'use strict';
const V=require('../voice-core.js'),LAN=require('../browser.js');
const lan=new LAN.SharedLan(),voice=new V.Shared(),client=new LAN.Client(process.argv[2],'VOICE108','BrowserVoice',lan);
client.voice=voice;client.voiceFrame=new Uint8Array(356);voice.setSpeaker(true);
(async()=>{
 await client.connect();voice.publish([100,100,20]);voice.setMic(true);
 const audio=new Uint8Array(320).fill(V.encode(.3)),frame=new Uint8Array(356),incoming=new Uint8Array(356),mixer=new V.Mixer();let ticks=0,sequence=0,heard=false;
 const timer=setInterval(()=>{
  ticks++;voice.publish([100,100,20]);voice.push(true,V.frame(frame,voice.vip,++sequence&65535,[100,100,20],audio));
  while(voice.pull(false,incoming))mixer.receive(incoming,[100,100,20],voice.vip);
  const l=new Float32Array(960),r=new Float32Array(960);mixer.render(l,r,[100,100,20],48000);if(l.reduce((a,b)=>a+b)/960>.2)heard=true;
  if(ticks>90&&heard){console.log('BROWSER_VOICE_WEBSOCKET_PASS');clearInterval(timer);client.disconnect();process.exit(0);}
  if(ticks>400){clearInterval(timer);client.disconnect();throw Error('Voice timeout');}
 },20);
})().catch(error=>{console.error(error);process.exit(1);});
