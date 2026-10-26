/* Resolve only unavailable sprites to approved existing GTA asset names. */
(function(root){'use strict';
 const TABLE_ADDRESS=19520936,TABLE_COUNT_ADDRESS=19520944,MAX_DISTINCT=128;
 const FALLBACKS=[[428,59,"radar_heist"],[430,309,"radar_race"],[445,77,"radar_lester_family"],[671,374,"radar_business"],[673,309,"radar_race"],[679,374,"radar_business"],[739,280,"radar_friend"],[765,363,"radar_heist_prep"],[777,357,"radar_garage"],[788,374,"radar_business"],[789,303,"radar_bounty_hit"],[790,135,"radar_cinema"],[796,59,"radar_heist"],[797,59,"radar_heist"],[798,59,"radar_heist"],[829,377,"radar_parachute"],[830,357,"radar_garage"],[832,293,"radar_simeon_family"],[892,303,"radar_bounty_hit"]];
 function fallback(memory,reference,original){
  if(original!==0n)return {pointer:original,target:-1};
  try{
   const size=BigInt(memory.buffer.byteLength);
   if(typeof reference!=='bigint'||reference<=0n||reference+4n>size||BigInt(TABLE_COUNT_ADDRESS+2)>size)return {pointer:original,target:-1};
   const view=new DataView(memory.buffer),sprite=view.getInt32(Number(reference),true),row=bySprite.get(sprite);
   if(!row)return {pointer:original,target:-1};
   const count=view.getUint16(TABLE_COUNT_ADDRESS,true),base=view.getBigUint64(TABLE_ADDRESS,true);
   if(!count||count>1024||base===0n||base+BigInt(count)*16n>size)return {pointer:original,target:-1};
   let low=0,high=count;
   while(low<high){const mid=(low+high)>>>1,id=view.getInt32(Number(base)+mid*16,true);if(id<row[1])low=mid+1;else high=mid;}
   if(low===count||view.getInt32(Number(base)+low*16,true)!==row[1])return {pointer:original,target:-1};
   const pointer=view.getBigUint64(Number(base)+low*16+8,true),name=row[2];
   if(pointer===0n||pointer+BigInt(name.length)+1n>size)return {pointer:original,target:-1};
   const bytes=new Uint8Array(memory.buffer);for(let i=0;i<name.length;i++)if(bytes[Number(pointer)+i]!==name.charCodeAt(i))return {pointer:original,target:-1};
   if(bytes[Number(pointer)+name.length]!==0||view.getUint16(TABLE_COUNT_ADDRESS,true)!==count||view.getBigUint64(TABLE_ADDRESS,true)!==base)return {pointer:original,target:-1};
   return {pointer,target:row[1]};
  }catch(_){return {pointer:original,target:-1};}
 }
 const bySprite=new Map(FALLBACKS.map(row=>[row[0],row]));
 function callback(memory,original,report=()=>{}){
  if(!(memory instanceof WebAssembly.Memory)||typeof original!=='function'||typeof report!=='function')throw Error('Blip compatibility bridge required');
  const seen=new Set();
  return reference=>{
   const result=original(reference);
   if(result!==0n)return result;
   const replacement=fallback(memory,reference,result);
   try{
    const size=BigInt(memory.buffer.byteLength);
    if(typeof reference!=='bigint'||reference<=0n||reference+4n>size||BigInt(TABLE_COUNT_ADDRESS+2)>size)return replacement.pointer;
    const view=new DataView(memory.buffer),count=view.getUint16(TABLE_COUNT_ADDRESS,true);
    if(!count)return replacement.pointer;
    const sprite=view.getInt32(Number(reference),true);
    if(seen.has(sprite)||seen.size>=MAX_DISTINCT)return replacement.pointer;
    seen.add(sprite);
    report(replacement.target<0?'[blip-missing] sprite '+sprite+' table '+count:'[blip-fallback] sprite '+sprite+' -> '+replacement.target+' table '+count);
   }catch(_){/* A logging failure must not change icon selection. */}
   return replacement.pointer;
  };
 }
 const api={callback,fallback,FALLBACKS,TABLE_ADDRESS,TABLE_COUNT_ADDRESS,MAX_DISTINCT};root.ZemaBlipSprites=api;
 if(typeof module==='object')module.exports=api;
})(globalThis);
