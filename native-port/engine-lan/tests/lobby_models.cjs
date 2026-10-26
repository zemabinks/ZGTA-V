'use strict';
const assert=require('node:assert/strict');global.ZemaEngineLan=require('../browser.js');const M=require('../lobby-model.js');
const cases=['ROOM + north & south','Café 港','LOS-SANTOS'];
for(const room of cases){const value={relay:'ws://100.70.1.9:47541/engine-lan',room};assert.deepEqual(M.target(M.invite(value)),{...value,connection:'Remote'});}
assert.equal(M.target('192.168.1.5:47541').relay,'ws://192.168.1.5:47541/engine-lan');
for(const value of ['8.8.8.8','https://example.com','ws://0177.0.0.1/engine-lan','zgtav://join?relay=10.1.1.1&room=A&room=B','zgtav://join?relay=10.1.1.1&room=A#x'])assert.throws(()=>M.target(value));
const memory=new Map(),storage={getItem:key=>memory.get(key),setItem:(key,val)=>memory.set(key,val)};
for(let i=0;i<20;i++)M.remember(storage,{relay:'ws://192.168.1.5:47541/engine-lan',room:'room '+i});assert.equal(M.read(storage).length,12);M.remember(storage,M.read(storage)[0]);assert.equal(M.read(storage).length,12);M.forget(storage,M.read(storage)[0]);assert.equal(M.read(storage).length,11);
console.log(JSON.stringify({cases:cases.map(room=>M.invite({relay:'ws://100.70.1.9:47541/engine-lan',room})),result:'LOBBY_MODELS_PASS'}));
