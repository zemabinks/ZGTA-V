/* glue5 a62e56a5 gamer_tags.rs adaptation (MIT), with checked transactional writes. */
(function(root){'use strict';
 const ORDER=19506224,SORTED=19506092,HUD=19561688,PARTS=30,TAGS=52,STRIDE=672,RELAYOUT=264;
 function complete(memory){
  const view=new DataView(memory.buffer),size=view.byteLength;
  if(size<ORDER+120||size<SORTED+1||size<HUD+8||!view.getUint8(SORTED))return 0;
  const order=[],seen=new Set(),repeats=[];
  for(let i=0;i<PARTS;i++){const part=view.getInt32(ORDER+i*4,true);if(part<0||part>=PARTS)return 0;order.push(part);if(seen.has(part))repeats.push(i);seen.add(part);}
  if(!repeats.length)return 0;
  const hud=view.getBigUint64(HUD,true),end=hud+BigInt(TAGS*STRIDE);
  if(hud===0n||end>BigInt(size))return 0;
  const missing=Array.from({length:PARTS},(_,i)=>i).filter(i=>!seen.has(i));
  if(missing.length!==repeats.length)return 0;
  repeats.forEach((i,n)=>view.setInt32(ORDER+i*4,missing[n],true));
  for(let i=0;i<TAGS;i++)view.setUint8(Number(hud)+i*STRIDE+RELAYOUT,1);
  return repeats.length;
 }
 function callback(memory,original){if(typeof original!=='function')throw Error('Gamer tag original missing');return()=>{original();complete(memory);};}
 const api={complete,callback};root.ZemaGamerTags=api;if(typeof module==='object')module.exports=api;
})(globalThis);
