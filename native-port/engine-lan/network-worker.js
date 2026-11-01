/* The game blocks its runtime worker. Keep all WebSocket I/O in this separate
 * worker, sharing bounded queues with the engine and every pthread. */
'use strict';
importScripts('voice-core.js','engine-lan-browser.js');
let client=null,lan=null,resuming=null;
self.onmessage=async function(event){
  const m=event.data;
  try{
    if(!m||typeof m!=='object')throw Error('Invalid LAN worker message');
    if(m.type==='connect'){
      if(client)throw Error('LAN worker already configured');
      lan=new ZemaEngineLan.SharedLan();client=new ZemaEngineLan.Client(m.url,m.room,m.name,lan);
      client.voice=new ZemaVoiceCore.Shared(m.voice);client.voiceFrame=new Uint8Array(ZemaVoiceCore.LENGTH);
      client.status=(state,message)=>{if(resuming&&state==='disconnected')return;self.postMessage({type:"status",state,message});};
      const result=await client.connect();
      self.postMessage({type:'joined',vip:result.vip,context:{version:ZemaEngineLan.PROTOCOL,buffer:lan.buffer}});
    }else if(m.type==='resume'){
      if(!client)throw Error('No LAN session');if(resuming)return;const retry={cancelled:false};resuming=retry;
      try{
        // launchd and the host can take tens of seconds to become ready under
        // game load. Keep the existing engine alive through that startup gap.
        const deadline=performance.now()+60000;let attempt=0;
        while(!retry.cancelled){
          // Retain this adapter, its engine handles and its virtual address.
          // A host being switched back on may refuse the first connection.
          client.disconnect('Reconnecting to the same session…');client.status('connecting',attempt?'Waiting for the host. Retrying for up to one minute; your game stays open.':'Reconnecting. The host may take up to one minute to become ready.');
          try{
            const result=await client.connect(Math.max(1,Math.min(15000,Math.ceil(deadline-performance.now()))));
            if(!retry.cancelled)self.postMessage({type:'resumed',vip:result.vip});return;
          }catch(error){
            if(retry.cancelled)return;
            const remaining=deadline-performance.now();
            if((error.code&&error.code!=='transport')||remaining<=0)throw error;
            client.status('connecting','Waiting for the host. Your running game is kept.');
            await new Promise(resolve=>setTimeout(resolve,Math.min(remaining,Math.min(250*2**attempt++,2000))));
          }
        }
      }finally{if(resuming===retry)resuming=null;}
    }else if(m.type==='disconnect'){
      if(resuming){resuming.cancelled=true;resuming=null;}
      if(client)client.disconnect();self.postMessage({type:'disconnected'});
    }else throw Error('Unsupported LAN worker message');
  }catch(error){self.postMessage({type:'error',operation:m?.type,code:error.code||'transport',message:String(error.message)});}
};
