/* The launcher and runtime share one bounded preference/engine argument contract. */
(function(root){'use strict';
 const presets={
  battery:{title:'Battery saver',height:432,detail:[0,-1,0,0,0,0,0,0,0,0,0]},
  performance:{title:'Performance',height:540,detail:[0,-1,0,0,0,0,0,0,0,0,0]},
  balanced:{title:'Balanced',height:720,detail:[0,0,0,0,0,.2,.2,0,0,.2,.2]},
  quality:{title:'Quality',height:900,detail:[1,0,1,1,1,.4,.4,.2,.2,.4,.4]},
  ultra:{title:'High',height:1080,detail:[1,1,1,1,1,.6,.6,.4,.4,.6,.6]},
  max:{title:'Maximum (4K)',height:2160,detail:[1,1,2,1,1,.8,.8,.5,.5,.8,.8]}
 };
 const keys=['textureQuality','shadowQuality','reflectionQuality','particleQuality','grassQuality','cityDensity','lodScale','pedLodBias','vehicleLodBias','pedVariety','vehicleVariety'];
 // Repeated two-worker LAN starts stalled before the first frame; four is the validated browser budget.
 const defaults={version:1,mode:'sandbox',preset:'performance',height:0,fps:30,fill:true,cores:4,keyboardMouse:true,mouseSpeed:1,invertY:false,controller:true,targetingMode:1,lookSensitivity:2.5,aimSensitivity:2.5,newgame:false,relay:'',room:'LOS-SANTOS',player:'Player',connection:'LAN',lobbyRole:'join',lanRelay:'',lanRoom:'LOS-SANTOS',remoteRelay:'',remoteRoom:''};
 const heights=[0,432,540,720,900,1080,1290,1440,1620,2160];
 function normalize(raw){
  const r=raw&&typeof raw==='object'&&!Array.isArray(raw)?raw:{};const s={...defaults};
  for(const [k,values] of Object.entries({mode:['story','sandbox','lan'],connection:['LAN','Remote'],lobbyRole:['join','host'],preset:Object.keys(presets),height:heights,fps:[0,30,60],cores:[4],targetingMode:[0,1,2,3]}))if(values.includes(r[k]))s[k]=r[k];
  for(const k of ['fill','keyboardMouse','invertY','newgame','controller'])if(typeof r[k]==='boolean')s[k]=r[k];
  for(const k of ['mouseSpeed','lookSensitivity','aimSensitivity'])if(typeof r[k]==='number'&&Number.isFinite(r[k])&&r[k]>=.5&&r[k]<=10)s[k]=r[k];
  for(const [k,max] of [['relay',128],['room',64],['player',16],['lanRelay',128],['lanRoom',64],['remoteRelay',128],['remoteRoom',64]])if(typeof r[k]==='string'&&r[k].length<=max&&!/[\x00-\x1f\x7f-\x9f]/.test(r[k]))s[k]=r[k];
  if(r.connection===undefined&&/^ws:\/\/100\./.test(s.relay))s.connection='Remote';
  const bank=s.connection==='Remote'?'remote':'lan';
  if((!s[bank+'Relay']||r[bank+'Relay']===undefined)&&s.lobbyRole!=='host')s[bank+'Relay']=s.relay;
  if(!s[bank+'Room'])s[bank+'Room']=s.room;
  return s;
 }
 function read(storage){try{return normalize(JSON.parse(storage.getItem('zema-browser-launch-v1')));}catch(_){return normalize(null);}}
 function size(s,viewport){
  let aspect=s.fill&&viewport.width>0&&viewport.height>0?viewport.width/viewport.height:16/9;
  aspect=Math.max(.5,Math.min(4,aspect));const h=s.height||presets[s.preset].height;
  const k=Math.min(1,3840/(h*aspect));return [Math.max(320,Math.round(h*aspect*k/2)*2),Math.max(240,Math.round(h*k/2)*2)];
 }
 function query(raw,viewport){const s=normalize(raw),q=new URLSearchParams();
  q.set('mode',s.mode==='lan'?'story':s.mode);q.set('res',size(s,viewport).join('x'));q.set('fixed','1');q.set('low',['battery','performance'].includes(s.preset)?'1':'0');q.set('cores',String(s.cores));q.set('fps',String(s.fps));
  q.set('args',['-shaderQuality=1',...keys.map((k,i)=>'-'+k+'='+presets[s.preset].detail[i])].join(','));
  if(s.mode==='story'&&s.newgame)q.set('newgame','1');return q;
 }
 function decode(search){const q=new URLSearchParams(search),raw={};for(const k of Object.keys(defaults)){if(!q.has(k))continue;const v=q.get(k);raw[k]=typeof defaults[k]==='boolean'?v==='true':typeof defaults[k]==='number'?Number(v):v;}return normalize(raw);}
 function url(raw){const s=normalize(raw),q=new URLSearchParams();for(const [k,v]of Object.entries(s))q.set(k,String(v));return '/play/'+(s.mode==='lan'?'lan':s.mode)+'?'+q;}
 const api={presets,defaults,heights,normalize,read,size,query,decode,url};root.ZemaLaunchSettings=api;if(typeof module==='object')module.exports=api;
})(globalThis);
