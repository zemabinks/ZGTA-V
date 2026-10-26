'use strict';
document.getElementById('run').onclick=async()=>{
 const out=document.getElementById('result'),results={gameplayVerified:false};let d;
 const ensure=(p,m)=>{if(!p)throw Error(m);};
 try{
  const a=await navigator.gpu?.requestAdapter();ensure(a,'WebGPU adapter unavailable');
  const wanted=['texture-formats-tier1','texture-compression-bc','depth32float-stencil8'];results.features=wanted.filter(f=>a.features.has(f));
  d=await a.requestDevice({requiredFeatures:results.features});d.pushErrorScope('validation');
  const usage=GPUTextureUsage,bu=GPUBufferUsage;
  const vert='@vertex fn vs(@builtin(vertex_index) i:u32)->@builtin(position) vec4f {var p=array<vec2f,3>(vec2f(-1,-1),vec2f(3,-1),vec2f(-1,3));return vec4f(p[i],0,1);}';
  async function read(t,bpp){const b=d.createBuffer({size:256,usage:bu.COPY_DST|bu.MAP_READ}),e=d.createCommandEncoder();e.copyTextureToBuffer({texture:t},{buffer:b,bytesPerRow:256},{width:1,height:1});d.queue.submit([e.finish()]);await b.mapAsync(GPUMapMode.READ);const bytes=new Uint8Array(b.getMappedRange()).slice(0,bpp);b.unmap();b.destroy();return bytes;}
  function draw(t,fragment,bg){const m=d.createShaderModule({code:vert+fragment}),p=d.createRenderPipeline({layout:'auto',vertex:{module:m,entryPoint:'vs'},fragment:{module:m,entryPoint:'fs',targets:[{format:t.format}]}}),e=d.createCommandEncoder(),r=e.beginRenderPass({colorAttachments:[{view:t.createView(),loadOp:'clear',storeOp:'store'}]});r.setPipeline(p);if(bg)r.setBindGroup(0,d.createBindGroup({layout:p.getBindGroupLayout(0),entries:bg}));r.draw(3);r.end();d.queue.submit([e.finish()]);}
  const frag='@fragment fn fs()->@location(0) vec4f{return vec4f(63488.0/65535.0,31.0/65535.0,0,0);}';
  const old=d.createTexture({size:[1,1],format:'rgba16float',usage:usage.RENDER_ATTACHMENT|usage.COPY_SRC});draw(old,frag);const legacy=await read(old,8);results.legacyHalfFloatWords=Array.from(new Uint16Array(legacy.buffer));ensure(results.legacyHalfFloatWords[0]!==0xf800,'Legacy mismatch reproduction failed');
  if(results.features.includes('texture-formats-tier1')){
   const t=d.createTexture({size:[1,1],format:'rgba16unorm',usage:usage.RENDER_ATTACHMENT|usage.COPY_SRC});draw(t,frag);const b=await read(t,8);results.normalizedWords=Array.from(new Uint16Array(b.buffer));ensure(JSON.stringify(results.normalizedWords)==='[63488,31,0,0]','UNORM16 compressed-word preservation failed');results.unorm16='PASS';
   if(results.features.includes('texture-compression-bc')){
    const buf=d.createBuffer({size:256,usage:bu.COPY_DST|bu.COPY_SRC}),bc=d.createTexture({size:[4,4],format:'bc1-rgba-unorm',usage:usage.COPY_DST|usage.TEXTURE_BINDING}),e=d.createCommandEncoder();e.copyTextureToBuffer({texture:t},{buffer:buf,bytesPerRow:256},{width:1,height:1});e.copyBufferToTexture({buffer:buf,bytesPerRow:256},{texture:bc},{width:4,height:4});d.queue.submit([e.finish()]);
    const sample=d.createTexture({size:[1,1],format:'rgba8unorm',usage:usage.RENDER_ATTACHMENT|usage.COPY_SRC});draw(sample,'@group(0) @binding(0) var t:texture_2d<f32>;@fragment fn fs()->@location(0) vec4f{return textureLoad(t,vec2i(0),0);}',[{binding:0,resource:bc.createView()}]);const color=Array.from(await read(sample,4));ensure(JSON.stringify(color)==='[255,0,0,255]','BC1 skin word copy/sample failed: '+color);results.bc1CopySample='PASS';
   }
  }else results.unorm16='UNAVAILABLE: legacy float skin fallback remains unverified';
  const depth=d.createTexture({size:[1,1],format:'depth24plus-stencil8',usage:usage.RENDER_ATTACHMENT|usage.TEXTURE_BINDING}),e=d.createCommandEncoder();e.beginRenderPass({colorAttachments:[],depthStencilAttachment:{view:depth.createView(),depthLoadOp:'clear',depthStoreOp:'store',depthClearValue:1,stencilLoadOp:'clear',stencilStoreOp:'store',stencilClearValue:37}}).end();d.queue.submit([e.finish()]);
  const proxy=d.createTexture({size:[1,1],format:'rg8uint',usage:usage.RENDER_ATTACHMENT|usage.COPY_SRC});draw(proxy,'@group(0) @binding(0) var t:texture_2d<u32>;@fragment fn fs()->@location(0) vec4u{let s=textureLoad(t,vec2i(0),0).x;return vec4u(s,s,0,1);}',[{binding:0,resource:depth.createView({aspect:'stencil-only'})}]);const rg=Array.from(await read(proxy,2));ensure(JSON.stringify(rg)==='[37,37]','Stencil channel replication failed: '+rg);results.stencilRG='PASS';
  const response=await fetch('minimap-gpu-modules.json');
  if(response.ok){const modules=await response.json();results.minimapShaders=[];for(const source of modules){const m=d.createShaderModule(source),info=await m.getCompilationInfo(),errors=info.messages.filter(x=>x.type==='error');ensure(!errors.length,source.label+': '+errors.map(x=>x.message).join('; '));results.minimapShaders.push({label:source.label,result:'PASS'});}}else results.minimapShaders='NOT_REQUESTED';
  const error=await d.popErrorScope();ensure(!error,error?.message);results.result='PASS';
 }catch(e){results.result='FAIL';results.error=String(e.stack||e);}finally{d?.destroy();out.textContent=JSON.stringify(results,null,2);}
};
