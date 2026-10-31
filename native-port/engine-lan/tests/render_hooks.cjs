'use strict';
const assert=require('node:assert/strict');
let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',s=>input+=s);
process.stdin.on('end',()=>{
  const fixture=JSON.parse(input),events=[],hints=[],alphaCalls=[];let instance,passes=0,fallback=2,calls=0,stack=4096n;
  const imports={mock:{
    lod(){instance.exports.unlock(2000n);},unlock(p){events.push(['unlock',p.toString()]);},
    begin(){calls++;return calls===1?passes:fallback;},end(){events.push(['end']);},
    alpha(a,invert){
      alphaCalls.push([a>>>0,invert>>>0]);
      const data=new DataView(instance.exports.memory.buffer),index=Math.min(a>>>0,255)>>>3;
      data.setUint16(23984584,(data.getUint16(7344304+index*2,true)^(-invert))&65535,true);
    },reset(){events.push(['reset']);},
    hint(resource,offset,size){hints.push([resource.toString(),offset,size]);events.push(['hint']);},
    current(){return stack;},alloc(n){stack-=n;return stack;},restore(n){stack=n;},
    emit(op,at,count){events.push(['emit',op,new DataView(instance.exports.memory.buffer).getUint32(Number(at),true),count]);}
  }};
  instance=new WebAssembly.Instance(new WebAssembly.Module(Buffer.from(fixture.wasm,'base64')),imports);
  const e=instance.exports,m=new DataView(e.memory.buffer),put=(a,n)=>m.setUint32(a,n>>>0,true);
  const table=Buffer.from(fixture.original_table_hex,'hex');
  new Uint8Array(e.memory.buffer,7344304,64).set(table);
  const expected=(alpha,invert)=>{
    const raw=(table.readUInt16LE((Math.min(alpha>>>0,255)>>>3)*2)^(-invert))&65535;
    let mask=0;for(let phase=0;phase<4;phase++)if(((raw>>>(phase*4))&15)===15)mask|=1<<phase;
    return mask;
  };
  const forced=6634168,deferred=21490232;put(deferred,11);[7248300,7248304,7248320].forEach((a,j)=>put(a,20+j));
  const draw=(group,alpha,invert=0,explicit=0,p=0,f=2)=>{
    put(forced,group);e.alpha(alpha,invert);passes=p;fallback=f;calls=0;events.length=0;
    assert.deepEqual(alphaCalls.at(-1),[alpha>>>0,invert>>>0]);return e.begin(100n,0,0,explicit);
  };
  for(const group of [20,21,22])for(let a=0;a<=255;a++)for(const invert of [0,1]){
    const mask=expected(a,invert);assert.equal(draw(group,a,invert),mask?2:0);
    assert.equal(calls,mask?2:1);assert.equal(m.getUint32(forced,true),group);assert.equal(stack,4096n);
    assert.deepEqual(events,mask&&mask!==15?[['emit',65,16|mask,1]]:[]);
    const before=events.length;e.end();
    assert.deepEqual(events.slice(before),mask&&mask!==15?[['end'],['emit',65,0,1]]:[['end']]);
  }
  for(const a of [256,0xffffffff])for(const invert of [0,1]){
    const mask=expected(a,invert);assert.equal(draw(20,a,invert),mask?2:0);assert.equal(calls,mask?2:1);e.end();
  }
  for(const invert of [0,1]){
    assert.equal(draw(20,128,invert,9),0);assert.equal(calls,1);assert.deepEqual(events,[]);
    assert.equal(draw(20,128,invert,0,3),3);assert.equal(calls,1);assert.deepEqual(events,[]);
    for(const group of [-1,99]){assert.equal(draw(group,128,invert),0);assert.equal(calls,1);assert.deepEqual(events,[]);}
    assert.equal(draw(20,128,invert,0,0,0),0);assert.deepEqual(events,[]);e.end();assert.equal(events.length,1);
  }
  // ResetStippleAlpha clears the sample mask only. It must not overwrite the
  // real non-MSAA GlobalFade mask or make its next draw incorrectly solid.
  e.alpha(255,1);e.reset();put(forced,20);calls=0;passes=0;fallback=2;events.length=0;
  assert.equal(e.begin(100n,0,0,0),0);assert.equal(calls,1);assert.deepEqual(events,[]);e.end();
  m.setBigUint64(2080,100n,true);put(2096,32);put(2100,312<<10);
  hints.length=0;e.unlock(2000n);assert.equal(hints.length,0);
  events.length=0;e.lod();assert.deepEqual(hints,[['100',32,312<<10]]);assert.deepEqual(events.map(v=>v[0]),['hint','unlock']);
  e.unlock(2000n);assert.equal(hints.length,1);put(2100,128<<10);e.lod();assert.equal(hints.length,1);
  put(2100,(128<<10)+1);m.setBigUint64(2080,0n,true);e.lod();assert.equal(hints.length,1);
  console.log('WASM_MEMORY64_RENDER_HOOKS_EXECUTION_PASS: exact256x2x3 fade cases');
});
