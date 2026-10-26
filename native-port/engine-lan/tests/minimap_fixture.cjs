'use strict';
// Executes the real worker reflection and minimap selectors with a recording
// module factory. Does not launch GTA, a renderer, or a physical GPU.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const worker = fs.readFileSync(process.argv[2], 'utf8');
const shaders = process.argv[3];
const code = worker + `\nmodule.exports = { ...module.exports,
  zemaMinimapShaderSource, zemaPauseMapBlend, zemaMinimapPrograms,
  setDevice: d => device = d, pipelineRecipe, recipeKey };`;
const sandbox = { process, require, console, performance, module: { exports: {} },
    MessageChannel: class { constructor() { this.port1 = {}; this.port2 = {}; } },
    URLSearchParams, setTimeout, clearTimeout, setInterval, clearInterval };
vm.runInNewContext(code, sandbox);
const api = sandbox.module.exports;
const modules = [];
api.setDevice({ createShaderModule(desc) { modules.push(desc); return desc; } });
const source = hash => fs.readFileSync(shaders + '/' + hash + '.wgsl', 'utf8');
function program(hash, label) {
    const { text, pack } = api.packUniforms(source(hash));
    const info = api.parseWgsl(text), groupBindings = {};
    for (const b of info.bindings) (groupBindings[b.group] ||= []).push(b);
    return { label, text, pack, info, groupBindings, variants: new Map(), bgls: [] };
}
const plainVS = program('4e1d5d361e0ed0bc', 'im::VS_Blit');
const plainPS = program('7f531ca66548aefe', 'im::PS_BlitDepthToAlpha');
const originalVS = plainVS.text, originalPS = plainPS.text;
const [hudVS, hudPS] = api.zemaMinimapPrograms(plainVS, plainPS, null);
assert.notEqual(hudVS, plainVS); assert.notEqual(hudPS, plainPS);
assert.equal(hudPS.pack.size, 64);
assert.equal(hudPS.pack.members[0].binding, 5);
assert.deepEqual(Array.from(hudPS.info.bindings, b => b.binding).sort((a,b) => a-b), [0, 18, 34]);
assert.match(hudVS.text, /v0\.x \* 2\.0f - 1\.0f/);
assert.match(hudVS.text, /1\.0f - v0\.y \* 2\.0f/);
assert.match(hudPS.text, /textureSample/);
assert.equal((hudPS.text.match(/textureSample\(/g) || []).length, 5);
assert.notEqual(hudPS.groupBindings, plainPS.groupBindings);
assert.notEqual(hudPS.bgls, plainPS.bgls);
assert.equal(plainVS.text, originalVS); assert.equal(plainPS.text, originalPS);
assert.equal(api.zemaMinimapPrograms(plainVS, plainPS, null)[0], hudVS);
assert.equal(api.zemaMinimapPrograms(plainVS, plainPS, null)[1], hudPS);
assert.equal(modules.length, 2, 'variants are memoized rather than compiled every draw');
const pause = { words: [0,0,1,2,2,4,2,2,4,8] };
assert.equal(api.zemaPauseMapBlend(pause), true);
assert.equal(api.zemaPauseMapBlend({ words: [0,0,1,2,2,4,2,2,4,15] }), false);
assert.equal(api.zemaPauseMapBlend(null), false);
const [pauseVS, pausePS] = api.zemaMinimapPrograms(plainVS, plainPS, pause);
assert.notEqual(pauseVS, hudVS); assert.equal(pausePS, plainPS);
assert.equal(pauseVS.pack.members[0].binding, 1);
assert.equal(pauseVS.pack.size, 192);
assert.match(pauseVS.text, /cbpack_v\.cb1_1/);
const other = { ...plainPS, label: 'im::PS_Blit' };
assert.equal(api.zemaMinimapPrograms(plainVS, other, null)[0], plainVS);
assert.equal(api.zemaMinimapPrograms(plainVS, other, null)[1], other);
// shaderProgram gives the variant an already-packed VS. Even if a future
// pinned VS carries constants, coordinate replacement must keep original
// D3D slot metadata rather than pack binding 0 again.
const withConstants = api.packUniforms('struct Slot { values: array<vec4<f32>, 2u>, }\n@group(0u) @binding(6u) var<uniform> slot6 : Slot;\n' + source('4e1d5d361e0ed0bc'));
const constantVS = { ...plainVS, text: withConstants.text, pack: withConstants.pack, zemaMinimapVariants: undefined };
const constantHudVS = api.zemaMinimapPrograms(constantVS, plainPS, null)[0];
assert.equal(constantHudVS.pack, withConstants.pack);
assert.equal(constantHudVS.pack.members[0].binding, 6);
assert.equal(constantHudVS.pack.size, 32);
assert.equal((constantHudVS.text.match(/struct cbpack_t/g) || []).length, 1);
assert.ok(!constantHudVS.text.includes('cbpack_v.cbpack_v'));
const radarSource = source('5c5d5123dfb3dd00');
const radar = api.zemaMinimapShaderSource({ effect: 'radar', program: 'PS_TexturedUnlitAA' }, radarSource);
assert.ok(!radar.includes('@location(5u)'));
assert.match(radar, /let v5 = vec4<f32>\(1\.0f\);/);
assert.match(radar, /textureSample\(t0, s0/);
assert.match(radar, /discard;/);
assert.equal(api.zemaMinimapShaderSource({ effect: 'not-radar', program: 'PS_TexturedUnlitAA' }, radarSource), radarSource);
assert.throws(() => api.zemaMinimapShaderSource({ effect: 'radar', program: 'PS_TexturedUnlitAA' }, radar), /Unexpected radar/);
assert.throws(() => api.zemaMinimapPrograms({ ...plainVS, text: 'changed' }, plainPS, null), /Unexpected HUD/);
// Original real shader hashes remain in cache recipes; blend words select
// distinct HUD and pause programs both in doDraw and compileAhead.
assert.match(worker, /zemaMinimapPrograms\(vsProg, psProg, S\.blend\.id/);
assert.match(worker, /zemaMinimapPrograms\(vsProg, psProg, rc\.b/);
console.log(JSON.stringify({ minimapReflectionAndSelection: 'PASS',
    shaderVariants: modules.length, originalShadersPreserved: true,
    gpuCompilationVerified: false, gameplayVerified: false }));
