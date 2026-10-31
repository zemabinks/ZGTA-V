'use strict';
const assert = require('node:assert/strict');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', value => input += value);
process.stdin.on('end', () => {
  const fixture = JSON.parse(input), cases = [];
  let instance, renderer = 0, privateStack = 4096n, available = false;
  let events = [], draws = [], passes = [], beginMasks = [], ends = 0, begins = 0;
  const memory = () => new DataView(instance.exports.memory.buffer);
  const put = (address, value) => memory().setUint32(address, value, true);
  const put64 = (address, value) => memory().setBigUint64(address, BigInt(value), true);
  const effect = () => Number(memory().getBigUint64(12432408, true));
  const imports = {mock: {
    lod(){}, unlock(){}, end(){}, alpha(){}, reset(){}, hint(){},
    begin(shader, kind, bind, flags){
      assert.equal(shader, 1000n); assert.equal(kind, 0);
      assert.equal(bind, 1); assert.equal(flags, 0);
      begins++; beginMasks.push(renderer);
      const count = available || memory().getUint32(6634168, true) === 11 ? 2 : 0;
      if(count){ put64(12432408, 999); put(12432416, count); }
      return count;
    },
    current(){ return privateStack; }, alloc(n){ return privateStack -= n; },
    restore(n){ privateStack = n; },
    emit(op, at, count){
      assert.equal(op, 65); assert.equal(count, 1);
      renderer = memory().getUint32(Number(at), true);
      events.push({value: renderer, effect: effect(), completedPasses: ends});
    },
    bind_pass(effectPointer, pass, shader){
      assert.equal(effectPointer, 1500n); assert.equal(shader, 1000n);
      passes.push(pass);
    },
    end_pass(){ ends++; },
    geometry(pointer){ assert.equal(pointer, 4000n); draws.push(renderer); }
  }};
  instance = new WebAssembly.Instance(new WebAssembly.Module(Buffer.from(fixture.wasm, 'base64')), imports);
  const e = instance.exports;
  const setup = () => {
    new Uint8Array(e.memory.buffer).fill(0);
    renderer = 0; privateStack = 4096n; available = false;
    events = []; draws = []; passes = []; beginMasks = []; ends = 0; begins = 0; e.active.value = 0;
    put(6634168, 20); put(21490232, 11);
    [7248300, 7248304, 7248320].forEach((address, index) => put(address, 20 + index));
    memory().setUint16(23984584, 0xf00f, true);
    // Shader, model, one geometry and its real table64 virtual draw slot.
    put64(1008, 1500); put64(2008, 3000); memory().setUint16(2016, 1, true);
    put64(3000, 4000); put64(4000, 5000); put64(5024, 0);
  };
  const invoke = () => {
    e.draw(1000n, 0, 2000n, 0);
    assert.equal(effect(), 0, 'actual original inline store must clear current effect');
    assert.equal(privateStack, 4096n, 'adapter emitter must restore private stack');
    assert.equal(memory().getUint32(6634168, true), 20, 'fallback must restore forced technique');
  };
  const save = (name, passed) => cases.push({name, passed, renderer, active: e.active.value,
    draws: draws.slice(), events: events.slice(), passes: passes.slice(),
    beginMasks: beginMasks.slice(), ends, begins});

  setup(); invoke();
  // Both genuine loop iterations must retain coverage until the original inline
  // EndDraw store. Inspect state here before any subsequent BeginDraw can repair it.
  assert.deepEqual(draws, [25, 25]); assert.deepEqual(passes, [0, 1]); assert.equal(ends, 2);
  save('inline_end_cleanup', renderer === 0 && e.active.value === 0
    && JSON.stringify(events) === JSON.stringify([
      {value:25, effect:999, completedPasses:0}, {value:0, effect:0, completedPasses:2}]));

  setup(); invoke(); available = true; invoke();
  save('consecutive_ordinary_draw', JSON.stringify(draws) === JSON.stringify([25,25,0,0])
    && e.active.value === 0 && ends === 4 && begins === 3);

  const leavePartial = () => {
    assert.equal(e.begin(1000n, 0, 1, 0), 2);
    assert.equal(renderer, 25); assert.equal(e.active.value, 1);
    events = []; draws = []; passes = []; beginMasks = []; ends = 0; begins = 0;
  };
  setup(); leavePartial(); available = true; invoke();
  save('begin_available_clears_stale', renderer === 0 && e.active.value === 0
    && JSON.stringify(draws) === JSON.stringify([0,0]) && begins === 1 && beginMasks[0] === 0);

  setup(); leavePartial(); memory().setUint16(23984584, 0, true); invoke();
  save('begin_empty_clears_stale', renderer === 0 && e.active.value === 0
    && draws.length === 0 && begins === 1 && beginMasks[0] === 0);

  setup(); leavePartial(); memory().setUint16(23984584, 65535, true); invoke();
  save('begin_full_fallback_clears_stale', renderer === 0 && e.active.value === 0
    && JSON.stringify(draws) === JSON.stringify([0,0]) && begins === 2 && beginMasks[0] === 0);

  setup(); available = true; invoke(); invoke();
  save('ordinary_draw_adds_no_packets', renderer === 0 && e.active.value === 0
    && events.length === 0 && JSON.stringify(draws) === JSON.stringify([0,0,0,0]));
  console.log(JSON.stringify({scope:'isolated actual original f9299; no full game or scene validation', cases}));
});
