'use strict';
const assert=require('node:assert/strict'),online=require('../online.js'),lan=require('../browser.js');
const memory=new WebAssembly.Memory({initial:512,maximum:512}),m=new lan.Memory(memory),notes=[],calls=[];
const profile=new online.Profile(123456,'SaveProbe');let hooks,explode=false;
const host={commit:()=>true,prepareInterfaces:()=>true,allocate:()=>0n,release(){},networkUp(){},transportReady:()=>true,note:line=>notes.push(line)};
const originals={
 save_thread_create(...args){calls.push(args);return args[1];},
 save_block_worker(p){if(explode)throw Error('worker fixture');assert.equal(hooks.save_builder_buffer(100n,200n,300n),17);m.set32(p+68n,3);},
 save_builder_buffer(...args){calls.push(args);return 17;}
};
hooks=online.hooks(memory,originals,profile,host,lan.Memory);
// Ordinary thread and buffer operations preserve all arguments and results,
// and do not emit save-specific diagnostics.
const args=[123n,456n,789,10,11n,12n];assert.equal(hooks.save_thread_create(...args),456n);assert.deepEqual(calls.pop(),args);
assert.equal(hooks.save_builder_buffer(1n,2n,3n),17);assert.equal(notes.length,0);
for(const [result,label] of [[1n,'skipped'],[-1n,'failed'],[0xffffffffffffffffn,'failed'],[1234n,'started']]){
 assert.equal(hooks.save_thread_create(41759n,result,16384,-1,0n,0n),result);assert(notes.includes('LAN save: worker creation '+label));
}
hooks.save_block_worker(4096n);assert(notes.includes('LAN save: worker entered'));assert(notes.includes('LAN save: builder returned; result=17'));assert(notes.includes('LAN save: worker returned; state=3'));
explode=true;assert.throws(()=>hooks.save_block_worker(4096n),/worker fixture/);assert(notes.includes('LAN save: worker threw'));
const before=notes.length;hooks.save_builder_buffer(1n,2n,3n);assert.equal(notes.length,before,'Worker scope must unwind on failure');
for(let i=0;i<100;i++)hooks.save_thread_create(41759n,1234n,1,0,0n,0n);
assert.equal(notes.filter(n=>n==='LAN save: worker creation started').length,1,'Diagnostics are bounded and deduplicated');
assert(!notes.some(n=>n.includes('1234')||n.includes('4096')),'Do not emit pointer values');
console.log('SAVE_WORKER_FORWARDING_SCOPE_AND_BOUNDED_DIAGNOSTICS_PASS');
