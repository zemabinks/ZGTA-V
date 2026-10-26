/* Shared launcher invitation and saved-lobby contract. Never stores resume tokens. */
(function(root){'use strict';
 const key='zgta-lobbies-v1',limit=12;
 function room(value){if(typeof value!=='string'||!value.trim()||new TextEncoder().encode(value).length>64||/[\x00-\x1f\x7f-\x9f]/.test(value))throw Error('Enter a room name of 1–64 bytes.');return value;}
 function address(text){
  if(typeof text!=='string'||text.length>128)throw Error('Enter the host address or paste an invite.');
  let value=text.trim();if(!value.includes('://')){if(!/^[0-9.]+(?::[1-9][0-9]{0,4})?$/.test(value))throw Error('Use the host’s Wi-Fi or Tailscale address.');value='ws://'+value+(value.includes(':')?'':':47540')+'/engine-lan';}
  const normalized=root.ZemaEngineLan.localURL(value),url=new URL(normalized);
  return {relay:normalized,connection:/^100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\./.test(url.hostname)?'Remote':'LAN'};
 }
 function target(text,fallback='LOS-SANTOS'){
  if(typeof text!=='string'||text.length>1024)throw Error('The invite is too long.');let raw=text.trim(),selectedRoom=fallback;
  if(raw.startsWith('zgtav:')){
   const u=new URL(raw);if(u.protocol!=='zgtav:'||u.hostname!=='join'||u.pathname&&u.pathname!=='/'||u.hash||u.username||u.password||u.port)throw Error('This invite is not valid.');
   const entries=[...u.searchParams.keys()];if(entries.length!==2||new Set(entries).size!==2||!entries.includes('relay')||!entries.includes('room'))throw Error('The invite needs a host and room.');
   raw=u.searchParams.get('relay');selectedRoom=u.searchParams.get('room');
  }
  return {...address(raw),room:room(selectedRoom)};
 }
 function invite(value){const t=target(value.relay,value.room);return 'zgtav://join?'+new URLSearchParams({relay:t.relay,room:t.room});}
 function read(storage){try{const raw=storage.getItem(key);if(typeof raw!=='string'||raw.length>32768)return [];const list=JSON.parse(raw);if(!Array.isArray(list))return [];const seen=new Set();return list.slice(0,limit).flatMap(x=>{try{const t=target(x.relay,x.room),id=t.relay+'\n'+t.room;if(seen.has(id))return [];seen.add(id);return [{...t,label:typeof x.label==='string'?x.label.slice(0,48):'',lastUsed:Number.isFinite(x.lastUsed)?x.lastUsed:0}];}catch(_){return [];}});}catch(_){return [];}}
 function remember(storage,value){const t=target(value.relay,value.room),rows=read(storage).filter(x=>x.relay!==t.relay||x.room!==t.room);rows.unshift({...t,label:typeof value.label==='string'?value.label.slice(0,48):'',lastUsed:Date.now()});storage.setItem(key,JSON.stringify(rows.slice(0,limit)));return rows.slice(0,limit);}
 function forget(storage,value){const rows=read(storage).filter(x=>x.relay!==value.relay||x.room!==value.room);storage.setItem(key,JSON.stringify(rows));return rows;}
 // Favorites are explicit. Do not promote the existing recent-host history.
 const favoriteKey='zgta-favorite-lobbies-v1',favoriteLimit=32;
 const identity=x=>x.relay+'\n'+x.room;
 function favorites(storage){
  try{const raw=storage.getItem(favoriteKey);if(typeof raw!=='string'||raw.length>32768)return [];const rows=JSON.parse(raw);if(!Array.isArray(rows))return [];
   const seen=new Set();return rows.slice(0,favoriteLimit).flatMap(x=>{try{const t=target(x.relay,x.room),id=identity(t);if(seen.has(id))return [];seen.add(id);return [{...t,label:typeof x.label==='string'?x.label.slice(0,48):''}];}catch(_){return [];}});
  }catch(_){return [];}
 }
 function setFavorite(storage,value,enabled){const t=target(value.relay,value.room),rows=favorites(storage).filter(x=>identity(x)!==identity(t));
  if(enabled){if(rows.length>=favoriteLimit)throw Error('You can save up to 32 favorite lobbies. Remove one first.');rows.unshift({...t,label:typeof value.label==='string'?value.label.slice(0,48):''});}
  storage.setItem(favoriteKey,JSON.stringify(rows));return rows;
 }
 function visible({hosts=[],favorites:bookmarks=[],mode='LAN',onlyFavorites=false,checkedAt=0,now=Date.now()}={}){
  const fresh=Number.isFinite(checkedAt)&&now>=checkedAt&&now-checkedAt<30000;
  const results=fresh?hosts:[],byRelay=new Map(results.map(h=>[h.address,h])),rows=[];
  const liked=new Set(bookmarks.map(identity));
  if(onlyFavorites){for(const saved of bookmarks){if(saved.connection!==mode)continue;
   const host=byRelay.get(saved.relay),lobby=host?.state==='online'&&host.catalog?host.lobbies.find(l=>l.room===saved.room):null;
   let state=host?.state||'unchecked';
   if(state==='online'&&!lobby)state=host.catalog&&host.room_policy==='hosted'?'room-missing':'unadvertised';
   rows.push({...saved,...(lobby||{}),favorite:true,state,verifiedRoom:!!lobby,latency:host?.latency_ms,total:host?.players,message:host?.message});
  }}else for(const host of results){
   // An answering relay and a guessed room name are not a live room listing.
   if(host.state!=='online'||!host.catalog||!Array.isArray(host.lobbies))continue;
   for(const lobby of host.lobbies){let t;try{t=target(host.address,lobby.room);}catch(_){continue;}if(t.connection!==mode)continue;
    rows.push({...t,...lobby,state:'online',verifiedRoom:true,latency:host.latency_ms,total:host.players,favorite:liked.has(identity(t))});
   }
  }
  const seen=new Set();return rows.filter(x=>{const id=identity(x);if(seen.has(id))return false;seen.add(id);return true;}).sort((a,b)=>a.room.localeCompare(b.room));
 }
 function canJoin(card){return (card.state==='online'||card.state==='unadvertised')&&!(card.slots>=card.capacity);}
 const api={key,limit,room,address,target,invite,read,remember,forget,favoriteKey,favoriteLimit,favorites,setFavorite,visible,canJoin};root.ZemaLobbyModel=api;if(typeof module==='object')module.exports=api;
})(globalThis);
