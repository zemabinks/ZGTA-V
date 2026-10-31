const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const text = fs.readFileSync(process.argv[2], 'utf8');
// Execute the actual transformed staging functions, with a queue which copies
// upload bytes before returning, as WebGPU writeBuffer specifies.
const writes = [], buffers = [];
const context = {isNode:true,process:{env:{}},GPUBufferUsage:{UNIFORM:1,COPY_DST:2},device:{
 createBuffer(d){const b={d,id:buffers.length}; buffers.push(b);return b;},
 queue:{writeBuffer(buf,at,bytes,off=0,size=bytes.byteLength){
  writes.push({buf,at,bytes:Uint8Array.from(new Uint8Array(bytes.buffer,bytes.byteOffset+off,size))});
 }}
}};
vm.createContext(context);
vm.runInContext(text.slice(text.indexOf('const RING_CHUNK ='),text.indexOf('const curObjs =')) + '\nthis.api={ubo,uniformAlloc,stageReserve,flushUniforms,dirtyChunks,getChunk:()=>allocChunk};',context);
const a=context.api, allocations=[];
function alloc(n){const at=a.uniformAlloc(n),chunk=a.getChunk();return {at,chunk,bytes:a.stageReserve(chunk,at,n)};}
for(let frame=0;frame<9;frame++){
 a.ubo.slot=frame%3;a.ubo.chunk=0;a.ubo.off=0;
 const one=alloc(16);one.bytes.fill(frame+1,one.at,one.at+16);allocations.push(one);
 const next=alloc(400000);next.bytes.fill(100+frame,next.at,next.at+400000);
 assert.equal(next.bytes[one.at],frame+1,'growth must retain pending writes');
 a.flushUniforms();assert.equal(a.dirtyChunks.size,0);
 const uploaded=writes.at(-1);assert.equal(uploaded.at,(frame%3)*(8<<20));
 assert.equal(uploaded.bytes[0],frame+1);assert.equal(uploaded.bytes[next.at],100+frame);
 // A second flush in the same frame must target only the new range.
 const last=alloc(16);last.bytes.fill(222,last.at,last.at+16);a.flushUniforms();
 assert.equal(writes.at(-1).at,(frame%3)*(8<<20)+last.at);assert.equal(writes.at(-1).bytes.length,16);
}
assert.equal(a.ubo.mirrors.length,1);
assert.equal(allocations[0].chunk.mirror,allocations[1].chunk.mirror);
assert.equal(allocations[0].chunk.buf,allocations[1].chunk.buf);
assert.notEqual(allocations[0].chunk.base,allocations[1].chunk.base);
assert.equal(writes[0].bytes[0],1,'next frame must not mutate captured uploads');
a.ubo.chunk=1;a.ubo.off=0;const other=alloc(16);assert.notEqual(other.chunk.mirror,allocations[0].chunk.mirror);
assert.throws(()=>a.stageReserve(other.chunk,-1,16),/range/);assert.throws(()=>a.stageReserve(other.chunk,8<<20,16),/range/);

const tableStart=text.indexOf('\tlet consts = null;\n\tif (rec.consts)');
assert.ok(tableStart>0);
const tableCode=text.slice(tableStart,text.indexOf('\n\tconst flat =',tableStart));
vm.runInContext('const zemaConstantTables=new Map(); this.table = arr => { const isNode=false,rec={consts:true},sh={fetched:{consts:arr}};'+tableCode+' return consts; };',context);
const count=buffers.length,first=context.table([1,2]);
assert.equal(context.table([1,2]),first);assert.equal(context.table([0x100000001,2]),first);
assert.notEqual(context.table([1,2,0]),first);assert.notEqual(context.table([1,3]),first);
assert.equal(buffers.length-count,3);
const content=writes.find(x=>x.buf===first).bytes;
assert.deepEqual([...new Uint32Array(content.buffer)],[1,0,0,0,2,0,0,0]);

vm.runInContext(fs.readFileSync(process.argv[3],'utf8')+'\nthis.fade=zemaWithStipple;',context);
for(let level=1;level<16;level++){
 const plain='@fragment fn main() -> @location(0) vec4<f32> { return vec4<f32>(1); }';
 assert.match(context.fade(plain,level),/@builtin\(position\) zema_fade_position/);
 const positioned='@fragment fn main(@builtin(position) p:vec4<f32>, @location(0) v:vec2<f32>) -> @location(0) vec4<f32> { return vec4<f32>(v,0,1); }';
 const transformed=context.fade(positioned,level);assert.match(transformed,/u32\(p.x\)/);assert.doesNotMatch(transformed,/zema_fade_position/);
 let covered=0;for(let y=0;y<4;y++)for(let x=0;x<4;x++)if(4*((((x^y)&1)<<1)|(y&1))+(((((x^y)>>1)&1)<<1)|(y>>1))<level)covered++;
 assert.equal(covered,level);
}
assert.throws(()=>context.fade('@fragment fn main() {}',0),/level/);

// Execute the transformed module selection and recipe functions, including the
// existing alpha-test and location-remap implementations. Only GPU module
// creation is mocked: these checks do not claim real shader compilation.
function sourceBetween(start,end){
 const at=text.indexOf(start), stop=text.indexOf(end,at);
 assert.ok(at>=0 && stop>at,'worker source anchors: '+start);
 return text.slice(at,stop);
}
const modules=[], variants={device:{createShaderModule(d){const m={...d,id:modules.length};modules.push(m);return m;}},logOnce(){}};
vm.createContext(variants);
vm.runInContext(
 sourceBetween('function a2cModule(', '\n// ZEMA_MINIMAP_PARITY_V1')+
 sourceBetween('const remapVariants =', '\nfunction getPipeline(')+
 sourceBetween('function pipelineRecipe(', "\n// 'done'")+
 '\nthis.api={pixelModule,pipelineRecipe,recipeKey,remapVariants};',variants);
const v=variants.api, shader={
 module:{original:true}, variants:new Map(), label:'ped test',
 text:'@group(1) @binding(5) var<uniform> cb:vec4<f32>;\n'+
 '@fragment\nfn main(@location(3u) v3:vec4<f32>) -> @location(0) vec4<f32> {\n main_inner(v3);\n return o0; }'
}, remap={ps:true,key:'3>1',map:new Map([[3,1]])};
assert.equal(v.pixelModule(shader,false,null),shader.module,'default module remains unchanged');
assert.equal(v.pixelModule(shader,false,null,0),shader.module);
assert.equal(modules.length,0);
const alpha=v.pixelModule(shader,true,null,0);
assert.match(alpha.code,/o0.w < 0.5f/);
assert.equal(v.pixelModule(shader,true,null,0),alpha,'default alpha module keeps its existing cache');
const composed=v.pixelModule(shader,true,remap,5);
assert.match(composed.code,/o0.w < 0.5f/);
assert.match(composed.code,/@location\(1u\) v3/);
assert.doesNotMatch(composed.code,/@location\(3u\)/);
assert.match(composed.code,/@location\(0\) vec4<f32>/,'output location must not be remapped');
assert.match(composed.code,/@group\(1\) @binding\(5\)/,'resource layout must not change');
assert.match(composed.code,/>= 5u/);
assert.equal(v.pixelModule(shader,true,remap,5),composed,'all variant dimensions are cached');
assert.notEqual(v.pixelModule(shader,true,remap,6),composed,'fade levels must not alias');
assert.notEqual(v.pixelModule(shader,false,remap,5),composed,'alpha-test state must not alias');
assert.notEqual(v.pixelModule(shader,true,null,5),composed,'remap state must not alias');
assert.equal(modules.length,5);
assert.equal(v.pixelModule(shader,false,null,0),shader.module,'variants cannot replace the default module');

// Exact engine phase masks stay distinct from legacy levels and compose with
// the same alpha-test/remap dimensions and recorded recipe keys.
for (const code of [16,17,25,27,31]) {
 const exact=v.pixelModule(shader,true,remap,code);
 assert.match(exact.code,/zema_fade_phase/);
 assert.match(exact.code,/o0.w < 0.5f/);
 assert.match(exact.code,/@location\(1u\) v3/);
 assert.equal(v.pixelModule(shader,true,remap,code),exact);
 assert.notEqual(exact,composed);
}

const layout={els:[],slots:[]}, targets=[];targets.samples=1;
function recipe(...fade){return v.pipelineRecipe({hash:'vs'},{hash:'ps'},layout,[],4,undefined,null,null,null,targets,null,false,false,...fade);}
const defaultRecipe=recipe(), zeroRecipe=recipe(0), fadedRecipe=recipe(5), oldRecipe={...zeroRecipe};delete oldRecipe.stipple;
assert.equal(defaultRecipe.stipple,0);
assert.equal(v.recipeKey(defaultRecipe),v.recipeKey(zeroRecipe));
assert.equal(v.recipeKey(oldRecipe),v.recipeKey(zeroRecipe),'old recorded recipes retain zero-fade semantics');
assert.notEqual(v.recipeKey(fadedRecipe),v.recipeKey(zeroRecipe));
assert.notEqual(v.recipeKey(fadedRecipe),v.recipeKey(recipe(6)));
for(const code of [16,17,25,27,31]) {
 assert.notEqual(v.recipeKey(recipe(code)),v.recipeKey(recipe(code&15)));
 assert.equal(v.recipeKey(JSON.parse(JSON.stringify(recipe(code)))),v.recipeKey(recipe(code)));
}
assert.equal(v.recipeKey(JSON.parse(JSON.stringify(fadedRecipe))),v.recipeKey(fadedRecipe),'serialized recipes retain the fade key');
console.log(JSON.stringify({status:'PASS',frames:9,mirrorsPerChunk:1,frameGpuRegions:3,tableExactEquality:true,orderedDitherLevels:15,composedPixelVariants:true,recipeFadeSeparation:true,legacyRecipeDefaultZero:true}));
