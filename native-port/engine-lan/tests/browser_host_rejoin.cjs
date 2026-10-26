'use strict';
const assert=require('node:assert/strict'),readline=require('node:readline'),api=require('../browser.js');
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const clients=[1,2].map(n=>new api.Client(process.argv[2],'ROOM','Player'+n,new api.SharedLan()));
(async()=>{
 const input=readline.createInterface({input:process.stdin});
 const restart=new Promise(resolve=>input.once('line',resolve));
 await Promise.all(clients.map(c=>c.connect()));
 const identities=clients.map(c=>({vip:c.lan.vip,handle:c.lan.bind(6672).handle,epoch:c.epoch,buffer:c.lan.buffer}));
 console.log('HOST_CLIENTS_READY');
 await restart;
 // Explicit retry is valid even before the old socket's close event arrives.
 clients.forEach(c=>c.disconnect());await Promise.all(clients.map(c=>c.connect()));
 clients.forEach((c,i)=>{assert.equal(c.lan.vip,identities[i].vip);assert.equal(c.lan.buffer,identities[i].buffer);assert.equal(c.lan.port(identities[i].handle),6672);assert.notEqual(c.epoch,identities[i].epoch);});
 assert(clients[0].lan.send(6672,clients[1].lan.vip,6672,Buffer.from('after host restart')));
 let frame;for(let i=0;i<150&&!frame;i++){await wait(10);frame=clients[1].lan.receive(6672);}
 assert(frame);assert.equal(Buffer.from(frame.data).toString(),'after host restart');
 console.log('BROWSER_HOST_RESTART_TWO_CLIENTS_SAME_BUFFERS_HANDLES_AND_DATA_PASS');input.close();
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>clients.forEach(c=>c.disconnect()));
