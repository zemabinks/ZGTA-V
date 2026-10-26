/* Local, explicit capability checks. No GPU workloads or telemetry uploads. */
(function(root){'use strict';
 const memory64=new Uint8Array([0,97,115,109,1,0,0,0,5,3,1,4,0]);
 const typedFunctions=new Uint8Array([0,97,115,109,1,0,0,0,1,11,2,96,1,126,1,127,96,1,112,1,127,3,2,1,1,10,9,1,7,0,32,0,251,20,0,11]);
 function engineSupport(wasm=root.WebAssembly){return {memory64:!!wasm?.validate(memory64),typedFunctions:!!wasm?.validate(typedFunctions)};}
 async function inspect(nav=root.navigator,wasm=root.WebAssembly,isolated=root.crossOriginIsolated){
  const report={sharedMemory:!!isolated,...engineSupport(wasm),webgpu:!!nav?.gpu,adapter:null,bc:false,fallback:false};
  if(!report.webgpu)return report;
  const adapter=await nav.gpu.requestAdapter({powerPreference:'high-performance'});
  if(!adapter)return report;
  const info=adapter.info||{};report.adapter=info.description||info.vendor||'Available; browser hides the GPU name';
  report.bc=!!adapter.features?.has('texture-compression-bc');report.fallback=!!(adapter.isFallbackAdapter||info.isFallbackAdapter);
  return report;
 }
 function text(r){return ['Shared memory: '+(r.sharedMemory?'ready':'unavailable'),'WebAssembly memory64: '+(r.memory64?'ready':'unavailable'),'Typed engine functions: '+(r.typedFunctions?'ready':'unavailable'),'High-performance WebGPU adapter: '+(r.adapter||'unavailable'),'BC game textures: '+(r.bc?'supported':'unsupported on this adapter'),'Software fallback reported: '+(r.fallback?'yes':'no')].join('\n');}
 function faster(raw){return {...raw,preset:'performance',height:432,fps:60,cores:4};}
 root.ZemaBrowserPerformance={engineSupport,inspect,text,faster};
 if(typeof module==='object')module.exports=root.ZemaBrowserPerformance;
})(globalThis);
