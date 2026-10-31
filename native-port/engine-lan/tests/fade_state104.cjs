'use strict';
const assert = require('node:assert/strict');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', value => input += value);
process.stdin.on('end', () => {
  const fixture = JSON.parse(input), cases = [];
  let instance, calls = 0, events = [], uniformUploads = [], privateStack = 4096n;
  const imports = {mock: {
    lod(){}, unlock(){}, begin(){ return ++calls === 1 ? 0 : 2; }, end(){}, hint(){},
    current(){ return privateStack; }, alloc(n){ return privateStack -= n; },
    restore(n){ privateStack = n; },
    emit(op, at, count){
      assert.equal(op,65); assert.equal(count,1);
      events.push(new DataView(instance.exports.memory.buffer).getUint32(Number(at),true));
    },
    uniform(handle,at,count){
      if(handle === 41){
        assert.equal(count,1);
        const view = new DataView(instance.exports.memory.buffer);
        uniformUploads.push([0,4,8,12].map(offset => view.getFloat32(Number(at)+offset,true)));
      }
    },
    blend(){}, msaa(){}, predicate(){ return 0; }
  }};
  instance = new WebAssembly.Instance(new WebAssembly.Module(Buffer.from(fixture.wasm,'base64')),imports);
  const e = instance.exports, m = new DataView(e.memory.buffer);
  const put = (a,v) => m.setUint32(a,v >>> 0,true);
  const raw = () => m.getUint16(23984584,true);
  const sample = () => m.getBigUint64(12433376,true);
  for(const [address,hex] of Object.entries(fixture.tables))
    new Uint8Array(e.memory.buffer,Number(address),64).set(Buffer.from(hex,'hex'));
  put(21490232,11);
  [7248300,7248304,7248320].forEach((a,j) => put(a,20+j));
  put(12382196,17); put(12433364,23); put(23984580,41); put(23984568,42);
  // These are actual original engine state locations, not hook shadow globals.
  const mode = count => { put(12623176,count); put(7344224,1); };
  const draw = (name, expectedMask) => {
    put(6634168,20); calls = 0; events = [];
    const result = e.begin(100n,0,0,0);
    const expectedEvents = expectedMask && expectedMask !== 15 ? [16|expectedMask] : [];
    const observedEvents = events.slice();
    const expectedResult = expectedMask ? 2 : 0;
    const passed = result === expectedResult && calls === (expectedMask ? 2 : 1)
      && JSON.stringify(observedEvents) === JSON.stringify(expectedEvents);
    cases.push({name,passed,expectedMask,result,calls,events:observedEvents,
      rawMask:raw(),sampleMask:sample().toString(16)});
    assert.equal(m.getUint32(6634168,true),20);
    e.end();
    assert.equal(privateStack,4096n);
    assert.equal(e.engine_stack.value,65536n);
  };

  mode(1);
  e.alpha(128,0); assert.equal(raw(),0xf00f);
  assert.deepEqual(uniformUploads.at(-1),[1,0,0,1]); draw('non_msaa_partial',9);
  e.reset_alpha(0,1); assert.equal(raw(),0xffff);
  assert.deepEqual(uniformUploads.at(-1),[1,1,1,1]); draw('reset_alpha_true',15);

  e.alpha(128,0); assert.equal(raw(),0xf00f);
  e.reset_alpha(1,0); assert.equal(raw(),0xf00f);
  assert.deepEqual(uniformUploads.at(-1),[1,0,0,1]); draw('reset_alpha_false_retains_mask',9);

  e.alpha(64,0); assert.equal(raw(),0x000f);
  put(50000,1); e.set_msaa(50000n); assert.equal(raw(),0xffff);
  assert.deepEqual(uniformUploads.at(-1),[1,1,1,1]); draw('set_msaa_reset',15);

  e.alpha(64,0); assert.equal(raw(),0x000f);
  e.sample_reset(); assert.equal(raw(),0x000f); assert.equal(sample(),0xffffffffffffffffn);
  assert.deepEqual(uniformUploads.at(-1),[1,0,0,0]);
  draw('sample_only_reset',1);

  e.alpha(32,0); assert.equal(raw(),0x000f);
  // This executes the authenticated setter without going through the adapter's
  // captured args: the draw must honor actual current guest state, whatever its
  // source, rather than a prior captured setter call.
  e.original_alpha(128,1); assert.equal(raw(),0x0ff0);
  assert.deepEqual(uniformUploads.at(-1),[0,1,1,0]);
  draw('authoritative_external_mask',6);

  mode(4);
  m.setUint16(23984584,0,true);
  e.alpha(128,0);
  assert.equal(raw(),0); assert.notEqual(sample(),0n); assert.notEqual(sample(),0xffffffffffffffffn);
  draw('msaa_stale_non_msaa_mask_guard',9);

  e.sample_reset(); assert.equal(raw(),0); assert.equal(sample(),0xffffffffffffffffn);
  draw('msaa_sample_reset',15);

  e.alpha(128,0); e.original_blend(17,23,0n); assert.equal(sample(),0n);
  draw('msaa_zero_mask',0);

  e.alpha(128,1); e.original_blend(17,23,-1n); assert.equal(sample(),0xffffffffffffffffn);
  draw('msaa_all_ones_mask',15);

  e.alpha(128,0); const before = sample();
  e.reset_alpha(0,0); assert.equal(sample(),before); draw('msaa_reset_false_retains_mask',9);

  e.alpha(128,1); e.reset_alpha(0,1); assert.equal(sample(),0xffffffffffffffffn);
  draw('msaa_reset_alpha_true',15);
  console.log(JSON.stringify({original_state_assertions:'PASS',cases}));
});
