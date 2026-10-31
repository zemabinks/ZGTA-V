'use strict';
document.getElementById('run').onclick=async()=>{
 const out=document.getElementById('result'),report={gameplayVerified:false,platform:navigator.userAgent};let device;
 try{
  const adapter=await navigator.gpu?.requestAdapter({powerPreference:'high-performance'});
  if(!adapter)throw Error('WebGPU adapter unavailable');
  const wanted=['shader-f16','clip-distances','float32-filterable','texture-formats-tier1','depth32float-stencil8'];
  report.features=wanted.filter(x=>adapter.features.has(x));
  device=await adapter.requestDevice({requiredFeatures:report.features});
  const modules=await (await fetch(new URLSearchParams(location.search).get('inputs'))).json();
  report.shaderCount=modules.length;report.shaderErrors=[];
  for(let i=0;i<modules.length;i++){
   const row=modules[i],module=device.createShaderModule({code:zemaWithStipple(row.text,8),label:row.label});
   const info=await module.getCompilationInfo(),errors=info.messages.filter(x=>x.type==='error');
   if(errors.length)report.shaderErrors.push({label:row.label,errors:errors.map(x=>x.message)});
   if(i%25===0)out.textContent='Compiled '+(i+1)+'/'+modules.length+' shaders…';
  }
  const vs=device.createShaderModule({code:'@vertex fn vs(@builtin(vertex_index) i:u32)->@builtin(position) vec4f {var p=array<vec2f,3>(vec2f(-1,-1),vec2f(3,-1),vec2f(-1,3));return vec4f(p[i],0,1);}'});
  report.coverage=[];
  for(let level=1;level<16;level++){
   const fs=device.createShaderModule({code:zemaWithStipple('@fragment fn main()->@location(0) vec4f {return vec4f(1,1,1,1);}',level)});
   const pipeline=await device.createRenderPipelineAsync({layout:'auto',vertex:{module:vs,entryPoint:'vs'},fragment:{module:fs,entryPoint:'main',targets:[{format:'rgba8unorm'}]}});
   const texture=device.createTexture({size:[4,4],format:'rgba8unorm',usage:GPUTextureUsage.RENDER_ATTACHMENT|GPUTextureUsage.COPY_SRC});
   const buffer=device.createBuffer({size:1024,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
   const command=device.createCommandEncoder(),pass=command.beginRenderPass({colorAttachments:[{view:texture.createView(),loadOp:'clear',clearValue:[0,0,0,0],storeOp:'store'}]});
   pass.setPipeline(pipeline);pass.draw(3);pass.end();command.copyTextureToBuffer({texture},{buffer,bytesPerRow:256},{width:4,height:4});device.queue.submit([command.finish()]);
   await buffer.mapAsync(GPUMapMode.READ);const bytes=new Uint8Array(buffer.getMappedRange());let covered=0;
   for(let y=0;y<4;y++)for(let x=0;x<4;x++)if(bytes[y*256+x*4+3]===255)covered++;
   report.coverage.push({level,covered});buffer.unmap();buffer.destroy();texture.destroy();
   if(covered!==level)throw Error('Incorrect GPU fade coverage at '+level+': '+covered);
  }
  if(report.shaderErrors.length)throw Error(report.shaderErrors.length+' shader compilation failures');
  report.result='PASS';
 }catch(error){report.result='FAIL';report.error=String(error.stack||error);}
 finally{device?.destroy();out.textContent=JSON.stringify(report,null,2);}
};
