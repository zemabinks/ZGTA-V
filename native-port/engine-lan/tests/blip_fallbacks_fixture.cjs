'use strict';
const assert=require('node:assert/strict'),fix=require(process.argv[2]);
const memory=new WebAssembly.Memory({initial:300}),v=new DataView(memory.buffer),b=new Uint8Array(memory.buffer);
const ref=64n,base=4096,count=426,names={59:'radar_heist',77:'radar_lester_family',135:'radar_cinema',280:'radar_friend',293:'radar_simeon_family',303:'radar_bounty_hit',309:'radar_race',357:'radar_garage',363:'radar_heist_prep',374:'radar_business',377:'radar_parachute'};
v.setBigUint64(fix.TABLE_ADDRESS,BigInt(base),true);v.setUint16(fix.TABLE_COUNT_ADDRESS,count,true);
for(let id=0;id<count;id++){v.setInt32(base+id*16,id,true);if(names[id]){const p=16384+id*64;v.setBigUint64(base+id*16+8,BigInt(p),true);b.set(new TextEncoder().encode(names[id]+'\0'),p);}}
let originalResult=0n,calls=0;const reports=[],cb=fix.callback(memory,()=>{calls++;return originalResult;},line=>reports.push(line));
const expected=[[428,59],[430,309],[445,77],[671,374],[673,309],[679,374],[739,280],[765,363],[777,357],[788,374],[789,303],[790,135],[796,59],[797,59],[798,59],[829,377],[830,357],[832,293],[892,303]];
for(const [sprite,target]of expected){v.setInt32(Number(ref),sprite,true);const before=Buffer.from(b);assert.equal(cb(ref),BigInt(16384+target*64));assert.deepEqual(Buffer.from(b),before);assert.equal(v.getInt32(Number(ref),true),sprite);}
assert.equal(reports.length,expected.length);assert(reports.includes('[blip-fallback] sprite 445 -> 77 table 426'));
v.setInt32(Number(ref),445,true);originalResult=999n;assert.equal(cb(ref),999n);originalResult=0n;
const targetAt=base+77*16+8,good=v.getBigUint64(targetAt,true);
for(const bad of [0n,BigInt(b.length-1),0xffffffffffffffffn]){v.setBigUint64(targetAt,bad,true);assert.equal(cb(ref),0n);}v.setBigUint64(targetAt,good,true);
b[Number(good)]^=1;assert.equal(cb(ref),0n);b[Number(good)]^=1;
b[Number(good)+'radar_lester_family'.length]=1;assert.equal(cb(ref),0n);b[Number(good)+'radar_lester_family'.length]=0;
for(const n of [0,1025,65535]){v.setUint16(fix.TABLE_COUNT_ADDRESS,n,true);assert.equal(cb(ref),0n);}v.setUint16(fix.TABLE_COUNT_ADDRESS,count,true);
for(const bad of [0n,BigInt(b.length-1),0xffffffffffffffffn]){v.setBigUint64(fix.TABLE_ADDRESS,bad,true);assert.equal(cb(ref),0n);}v.setBigUint64(fix.TABLE_ADDRESS,BigInt(base),true);
const throwing=fix.callback(memory,()=>0n,()=>{throw Error('sink');});assert.equal(throwing(ref),good);assert.equal(throwing(ref),good);
v.setInt32(Number(ref),999,true);assert.equal(cb(ref),0n);assert.equal(cb(-1n),0n);assert.equal(cb(0n),0n);assert.equal(cb(BigInt(b.length-3)),0n);assert(calls>expected.length);
console.log('MATCHED_BUILTIN_SPRITES_ORIGINAL_PRIORITY_NO_WRITES_BOUNDS_PASS');
