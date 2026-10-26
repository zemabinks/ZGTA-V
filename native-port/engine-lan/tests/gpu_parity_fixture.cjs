'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const worker=fs.readFileSync(process.argv[2],'utf8');
const sandbox={process,require,console,performance,module:{exports:{}},MessageChannel:class{constructor(){this.port1={};this.port2={};}},URLSearchParams,setTimeout,clearTimeout,setInterval,clearInterval};
vm.runInNewContext(worker+'\nmodule.exports.parity={mapFormat,proxyPipeline,copyThroughBuffer,markDepthDirty,ensurePass,setDepthFrame:(id,flags)=>{endPass();rtKey=null;S.rt.forEach(r=>r.tex=0);S.ds={tex:id,mip:0,slice:0,fmt:0,flags};},zemaPackNormClear,zemaMipPipeline,floatToDepthProxy,generateMips,clearUav,setDevice:v=>device=v,setEncoder:v=>encoder=v,zemaNormalizedProxy,markColorDirty,prepareDepthProxies,srvView,put:(id,o)=>objs.set(id,o),setSrv:(stage,slot,id)=>S.srv[stage][slot]=id};',sandbox);
const p=sandbox.module.exports.parity,calls=[];let desc;
p.setDevice({features:new Set(['texture-formats-tier1']),createShaderModule:d=>d,createRenderPipeline:d=>(desc=d,d),createBuffer:d=>d});
assert.equal(p.mapFormat(11,32).format,'rgba16unorm');assert.equal(p.mapFormat(35,8).format,'rg16unorm');assert.equal(p.mapFormat(10,32).format,'rgba16float');assert.equal(p.mapFormat(34,8).format,'rg16float');
p.proxyPipeline('stencil');assert.equal(desc.fragment.targets[0].format,'rg8uint');assert.match(desc.fragment.module.code,/return vec4<u32>\(s, s, 0u, 1u\)/);
global.GPUBufferUsage={COPY_SRC:4,COPY_DST:8};sandbox.GPUBufferUsage=global.GPUBufferUsage;p.setEncoder({copyTextureToBuffer:(...a)=>calls.push(a),copyBufferToTexture:(...a)=>calls.push(a)});
p.copyThroughBuffer({format:'rgba16unorm',tex:'source'},{mip:0,layer:0},{format:'bc1-rgba-unorm',tex:'dest'},{mip:0,layer:0},16,8,false,0,0,0,0);
assert.equal(calls[0][1].bytesPerRow,256);assert.equal(calls[0][2].width,16);assert.equal(calls[1][2].width,64);assert.equal(calls[1][2].height,32);assert.equal(calls[1][1].texture,'dest');
p.setDevice({features:new Set()});assert.equal(p.mapFormat(11,32).format,'rgba16float');assert.equal(p.mapFormat(35,8).format,'rg16float');
console.log('NORM16_FORMAT_BC_COPY_AND_STENCIL_PARITY_PASS');

// Exercise the actual worker's normalized texture scan, proxy reuse and SRV.
sandbox.GPUTextureUsage={COPY_SRC:1,COPY_DST:2,TEXTURE_BINDING:4,RENDER_ATTACHMENT:8};sandbox.GPUShaderStage={FRAGMENT:2};let draws=0,created=0,layoutSpec;
const texture=desc=>({format:desc.format,createView:view=>({desc,view})});
p.setDevice({features:new Set(['texture-formats-tier1','float32-filterable']),createTexture:desc=>(created++,texture(desc)),createShaderModule:desc=>desc,createBindGroupLayout:spec=>(layoutSpec=spec,spec),createPipelineLayout:spec=>spec,createRenderPipeline:spec=>({...spec,getBindGroupLayout:()=>layoutSpec}),createBindGroup:spec=>spec});
p.setEncoder({beginRenderPass:()=>({setPipeline(){},setBindGroup(){},draw(){draws++;},end(){}})});
const descN={dimension:'2d',size:{width:4,height:4,depthOrArrayLayers:2},mipLevelCount:2,sampleCount:1,format:'rg16unorm'},original={kind:'texture',desc:descN,format:'rg16unorm',tex:texture(descN)};
const proxy=p.zemaNormalizedProxy(original);assert.equal(proxy.format,'rgba32float');assert.equal(layoutSpec.entries[0].texture.sampleType,'unfilterable-float');assert.equal(draws,4);assert.equal(created,1);assert.equal(original.format,'rg16unorm');assert.equal(p.zemaNormalizedProxy(original),proxy);assert.equal(draws,4);p.markColorDirty(original);assert.equal(proxy.dirty,true);
p.put(100,original);const srv={kind:'srv',res:100,isBuf:false,fmt:35,a:0,b:1,c:0,d:1,views:new Map()};p.put(101,srv);p.setSrv(1,0,101);const prog={info:{bindings:[{kind:'texture',binding:32,sample:'float'}]}};p.prepareDepthProxies(prog,1);assert.equal(draws,8);assert.equal(proxy.dirty,false);const view=p.srvView(srv,{dim:'2d',sample:'float'});assert.equal(view.__proxyTex,proxy.tex);assert.equal(draws,8);console.log('ACTUAL_WORKER_NORM16_SAMPLING_REFRESH_AND_SRV_PASS');

// Run the original worker's missed entry points, not a mirrored implementation.
let piped=[],bound=[],copies=[],uploads=[];
const pass=()=>({setPipeline(v){piped.push(v);},setBindGroup(_i,v){bound.push(v);},draw(){},end(){}});
const encoder={beginRenderPass:pass,copyBufferToTexture:(...args)=>copies.push(args)};
const gpu={features:new Set(['texture-formats-tier1','float32-filterable']),createTexture:texture,createShaderModule:d=>d,createBindGroupLayout:d=>d,createPipelineLayout:d=>d,createRenderPipeline:d=>({...d,getBindGroupLayout:()=>d.layout.bindGroupLayouts[0]}),createBindGroup:d=>d,createBuffer:d=>d,queue:{writeTexture:(dst,data,layout,size)=>uploads.push({dst,data:Uint8Array.from(data),layout,size})}};
p.setDevice(gpu);p.setEncoder(encoder);
p.generateMips(101);
assert.equal(piped.length,2);assert.equal(bound[0].layout.entries[0].texture.sampleType,'unfilterable-float');
assert.equal(bound[0].entries.length,1);assert.match(piped[0].fragment.module.code,/textureLoad\(src,min\(c\+vec2i\(1,1\),m\),0\)/);assert.doesNotMatch(piped[0].fragment.module.code,/textureSample/);assert.equal(piped[0].fragment.targets[0].format,'rg16unorm');
assert.equal(proxy.dirty,true);assert.equal(original.format,'rg16unorm');
const dproxy=p.floatToDepthProxy(original);assert.equal(dproxy.format,'depth32float');assert.equal(bound.at(-1).layout.entries[0].texture.sampleType,'unfilterable-float');
const cu={kind:'uav',res:100,isBuf:false,a:0};p.put(102,cu);proxy.dirty=false;dproxy.dirty=false;
p.clearUav(102,0,[0,0,0,0]);assert.equal(copies.length,2);assert.equal(copies[0][0].bytesPerRow,256);assert.equal(proxy.dirty,true);assert.equal(dproxy.dirty,true);
p.setEncoder(null);proxy.dirty=false;dproxy.dirty=false;p.clearUav(102,0,[0x1234abcd,0x89abcdef,0,0]);
assert.equal(uploads.length,2);assert.deepEqual(Array.from(uploads[0].data.subarray(0,8)),[0xcd,0xab,0xef,0xcd,0xcd,0xab,0xef,0xcd]);assert.equal(proxy.dirty,true);assert.equal(dproxy.dirty,true);assert.equal(uploads[0].layout.bytesPerRow,16);
const numeric=Float32Array.from([0.5,-0.25,2,NaN]),bits=new Uint32Array(numeric.buffer),packed=new Uint8Array(16);p.zemaPackNormClear(packed,8,true,bits);assert.deepEqual(Array.from(new Uint16Array(packed.buffer)),[32768,0,65535,0,32768,0,65535,0]);
console.log('ACTUAL_WORKER_MIPS_DEPTH_AND_CLEAR_NORM16_PARITY_PASS');

proxy.dirty=false;dproxy.dirty=false;p.clearUav(102,1,bits);assert.deepEqual(Array.from(new Uint16Array(uploads.at(-1).data.buffer,0,4)),[32768,0,32768,0]);assert.equal(proxy.dirty,true);assert.equal(dproxy.dirty,true);assert.equal(original.format,'rg16unorm');

// Real pass creation must invalidate only the aspects that pass can write.
const depthTarget={kind:'texture',format:'depth24plus-stencil8',tex:{createView:()=>({})},views:new Map(),desc:{dimension:'2d',sampleCount:1,size:{width:64,height:32}},proxy_depth:{dirty:false},proxy_stencil:{dirty:false}};
p.put(201,depthTarget);p.setEncoder({beginRenderPass:()=>({end(){}})});
for(const flags of [0,1,2,3]){
 depthTarget.proxy_depth.dirty=false;depthTarget.proxy_stencil.dirty=false;
 p.setDepthFrame(201,flags);assert.equal(p.ensurePass(),true);
 assert.equal(depthTarget.proxy_depth.dirty,(flags&1)===0,'depth flags '+flags);
 assert.equal(depthTarget.proxy_stencil.dirty,(flags&2)===0,'stencil flags '+flags);
}
depthTarget.proxy_depth.dirty=false;depthTarget.proxy_stencil.dirty=false;
p.markDepthDirty(depthTarget);assert.equal(depthTarget.proxy_depth.dirty,true);assert.equal(depthTarget.proxy_stencil.dirty,true);
console.log('ACTUAL_WORKER_READ_ONLY_DEPTH_AND_STENCIL_PASS');
