// WebGPU tier1 normalized16 textures are renderable but not filterable.
// Keep their exact integer bytes for GPU compression/copies; only shader reads
// use a lazily refreshed floating-point proxy with a filterable sample type.
const zemaNormPipelines=new Map();
function zemaNorm16(format){return format==='rg16unorm'||format==='rgba16unorm';}
function zemaNormPipeline(format){
 if(zemaNormPipelines.has(format))return zemaNormPipelines.get(format);
 const module=device.createShaderModule({code:`@group(0) @binding(0) var src:texture_2d<f32>;
 @vertex fn vs(@builtin(vertex_index) i:u32)->@builtin(position) vec4f {var p=array<vec2f,3>(vec2f(-1,-1),vec2f(3,-1),vec2f(-1,3));return vec4f(p[i],0,1);}
 @fragment fn fs(@builtin(position) pos:vec4f)->@location(0) vec4f{return textureLoad(src,vec2i(pos.xy),0);}`});
 const bgl=device.createBindGroupLayout({entries:[{binding:0,visibility:GPUShaderStage.FRAGMENT,texture:{sampleType:'unfilterable-float',viewDimension:'2d'}}]});
 const pipeline=device.createRenderPipeline({layout:device.createPipelineLayout({bindGroupLayouts:[bgl]}),vertex:{module,entryPoint:'vs'},fragment:{module,entryPoint:'fs',targets:[{format}]}});
 zemaNormPipelines.set(format,pipeline);return pipeline;
}
function zemaNormalizedProxy(t){
 if(!zemaNorm16(t.format))return t;
 if(t.desc.dimension!=='2d'||t.desc.sampleCount>1)throw Error('Unsupported normalized16 sampling dimension/count');
 let px=t.proxy_norm16;
 if(!px){const d=t.desc,format=device.features.has('float32-filterable')?'rgba32float':'rgba16float';
  if(format==='rgba16float')logOnce('norm16-half-proxy','normalized16 sample proxy uses half precision; full precision requires float32-filterable');
  const desc={size:d.size,mipLevelCount:d.mipLevelCount,sampleCount:1,dimension:'2d',format,usage:GPUTextureUsage.TEXTURE_BINDING|GPUTextureUsage.RENDER_ATTACHMENT};
  const tex=device.createTexture(desc);px=t.proxy_norm16={kind:'texture',tex,desc,format,views:new Map(),dirty:true};
 }
 if(px.dirty){endPass();const pipeline=zemaNormPipeline(px.format),enc=getEncoder();
  if(!px.passes){px.passes=[];for(let mip=0;mip<t.desc.mipLevelCount;mip++)for(let layer=0;layer<t.desc.size.depthOrArrayLayers;layer++){
   const src=t.tex.createView({dimension:'2d',baseMipLevel:mip,mipLevelCount:1,baseArrayLayer:layer,arrayLayerCount:1});
   const dst=px.tex.createView({dimension:'2d',baseMipLevel:mip,mipLevelCount:1,baseArrayLayer:layer,arrayLayerCount:1});
   px.passes.push({dst,bg:device.createBindGroup({layout:pipeline.getBindGroupLayout(0),entries:[{binding:0,resource:src}]})});
  }}
  for(const p of px.passes){const pass=enc.beginRenderPass({colorAttachments:[{view:p.dst,loadOp:'clear',storeOp:'store'}]});pass.setPipeline(pipeline);pass.setBindGroup(0,p.bg);pass.draw(3);pass.end();}
  usedInEncoder.add(t);px.dirty=false;
 }
 return px;
}

// All these helpers use textureLoad, so their source must allow unfilterable
// normalized16 and float32 textures as well as ordinary filterable formats.
function zemaLoadLayout(){return device.createBindGroupLayout({entries:[{binding:0,visibility:GPUShaderStage.FRAGMENT,texture:{sampleType:'unfilterable-float',viewDimension:'2d'}}]});}
function zemaMipPipeline(format){
 const layout=zemaLoadLayout();
 const module=device.createShaderModule({code:`@group(0) @binding(0) var src:texture_2d<f32>;
 @vertex fn vs(@builtin(vertex_index) i:u32)->@builtin(position)vec4f{var p=array<vec2f,3>(vec2f(-1,-1),vec2f(3,-1),vec2f(-1,3));return vec4f(p[i],0,1);}
 @fragment fn fs(@builtin(position) p:vec4f)->@location(0)vec4f{
 let m=vec2i(textureDimensions(src))-1;let c=vec2i(p.xy)*2;
 return (textureLoad(src,min(c,m),0)+textureLoad(src,min(c+vec2i(1,0),m),0)
 +textureLoad(src,min(c+vec2i(0,1),m),0)+textureLoad(src,min(c+vec2i(1,1),m),0))*0.25;}`});
 return device.createRenderPipeline({layout:device.createPipelineLayout({bindGroupLayouts:[layout]}),vertex:{module,entryPoint:'vs'},fragment:{module,entryPoint:'fs',targets:[{format}]}});
}
// D3D11 ClearUAV Uint copies each channel's low bits. Float converts the
// numeric value into the destination format. Preserve 16-bit words exactly.
function zemaPackNormClear(data,bpt,isFloat,values){
 const dv=new DataView(data.buffer,data.byteOffset,data.byteLength),word=new DataView(new ArrayBuffer(4));
 const channels=bpt/2,packed=[];
 for(let c=0;c<channels;c++){
  let v=values[c] & 65535;
  if(isFloat){word.setUint32(0,values[c]>>>0,true);const f=word.getFloat32(0,true);const scaled=(Number.isNaN(f)?0:Math.min(1,Math.max(0,f)))*65535;
   const lo=Math.floor(scaled),fraction=scaled-lo;v=fraction>0.5?lo+1:fraction<0.5?lo:lo+(lo&1);
  }packed.push(v);
 }
 for(let i=0;i<data.byteLength;i+=bpt)for(let c=0;c<channels;c++)dv.setUint16(i+c*2,packed[c],true);
}
