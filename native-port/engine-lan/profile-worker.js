'use strict';
importScripts('online.js','profile-rpc.js');
let started=false;
self.onmessage=async event=>{
  if(started)return;started=true;
  try{
    const {buffer,name}=event.data;if(typeof name!=='string')throw Error('Profile name required');
    const random=new Uint32Array(1);crypto.getRandomValues(random);const id=65536+random[0]%(2147483647-65536);
    const storage=await ZemaProfileRPC.IndexedStore.open();
    await ZemaProfileRPC.serve(buffer,storage,ZemaOnline.Profile,{id,name},context=>postMessage({type:'ready',context}),status=>postMessage(status));
  }catch{postMessage({type:'error',message:'Isolated profile storage unavailable; existing data preserved.'});}
};
