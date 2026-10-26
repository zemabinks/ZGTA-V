/* Disposable browser fixture. Never loads game code or user data. */
'use strict';
importScripts('/profile-rpc.js');
self.onmessage=async event=>{
  try{
    const {action,context,slot}=event.data,p=new ZemaProfileRPC.Proxy(context);let result;
    if(action==='write'){
      for(let i=0;i<64;i++)if(!p.setStat('p'+slot+':'+i,BigInt(slot*1000+i)))throw Error('Stat write failed');
      if(!p.put('f:audit'+slot+'.save',Uint8Array.from([0,255,slot,128])))throw Error('File write failed');
      p.markNewSlot(slot,true);if(!p.commit())throw Error('Durable commit failed');result={written:slot};
    }else if(action==='fallback'){
      if(!p.setStat('h12345678',98765n))throw Error('Fallback write failed');result={fallback_written:true};
    }else if(action==='inspect'){
      const bytes=p.encode(),digest=await crypto.subtle.digest('SHA-256',bytes);
      result={id:p.id,name:p.name,sha256:Array.from(new Uint8Array(digest),x=>x.toString(16).padStart(2,'0')).join(''),stat:p.stat('p3:7').toString(),fallback:p.stat('h12345678').toString(),file:[...p.get('f:audit3.save')],mask:p.newSlotMask()};
    }else if(action==='stale'){
      p.setStat('p0:1',999n);let refused=false;try{p.commit();}catch{refused=true;}if(!refused)throw Error('Stale owner overwrote the profile');result={stale_refused:true};
    }else throw Error('Unknown fixture action');
    postMessage({ok:true,...result});
  }catch(error){postMessage({ok:false,error:String(error.stack||error)});}
};
