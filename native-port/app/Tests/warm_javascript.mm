#include "WarmDispatchHarness.inc"
static NSString *between(NSString *source,NSString *start,NSString *end){
 NSRange begin=[source rangeOfString:start];assert(begin.location!=NSNotFound);
 NSRange finish=[source rangeOfString:end options:0 range:NSMakeRange(begin.location,source.length-begin.location)];assert(finish.location!=NSNotFound);
 return [source substringWithRange:NSMakeRange(begin.location,finish.location-begin.location)];
}
int main(){@autoreleasepool {
 namespace NW=NativeWarm;namespace NP=NativePreparedDraw;
 graphicsContext=[[JSContext alloc] init];NativeUniforms::install(graphicsContext);NativePipeline::install(graphicsContext);NP::install(graphicsContext);NW::install(graphicsContext);
 JSContextRef c=graphicsContext.JSGlobalContextRef;
 std::array<uint32_t,4096> memory{};engineMemory=memory.data();engineMemorySize=sizeof memory;
 JSObjectRef buffer=JSObjectMakeArrayBufferWithBytesNoCopy(c,memory.data(),sizeof memory,[](void *,void *){},nullptr,nullptr);
 graphicsContext[@"testEngineBytes"]=[JSValue valueWithJSValueRef:buffer inContext:graphicsContext];
 uint8_t constants[64]={};NativeUniforms::shadows[10]={constants,sizeof constants,0};
 NativePipeline::state[0]=7;NativePipeline::state[2]=17;NP::layouts[17]=NativePipeline::Layout{};
 auto identity=NativePipeline::key(&NP::layouts[17],1);JSObjectRef owner=JSObjectMake(c,nullptr,nullptr);JSValueProtect(c,owner);NativePipeline::values[identity]=owner;
 NativeDraw::Plan plan;NP::Record record;record.owner=owner;record.pipeline=(WGPURenderPipeline)(uintptr_t)101;record.plan=&plan;record.generation=10;record.pipelineGeneration=NativePipeline::generation;NP::records[identity]=record;NativePipeline::state[0]=0;
 [graphicsContext evaluateScript:@"var self=globalThis;var nativeGPUCall=function(){};var NativeGPU=function(){};var normalizeGPUVector=function(v){return v;};var capturedBatches=[];var nativeGPUBatch=function(a,o){capturedBatches.push([Array.from(a),o]);};"];
 NSString *batch=[NSString stringWithContentsOfFile:@"Resources/gpu-batch.js" encoding:NSUTF8StringEncoding error:nil];assert(batch);[graphicsContext evaluateScript:batch];assert(!graphicsContext.exception);
 [graphicsContext evaluateScript:[NSString stringWithUTF8String:R"JS(
 var nativeWarmDispatcher=true,nativeCompiledUniforms=true,nativePreparedDraws=true,nativeDirectDrawResolver=true,nativeDrawSynced=true;
 var nativeDetailedProfile=false,nativeBridgeProfile=false,dbgIdx=0,debugDraw=0,debugPs=0,debugCs=0,nanHuntState=0,shotEvery=0,shotAllRt=false;
 var pass={label:'fixture-pass'},rtKey=1,passKey=1,passInfo={tailId:1,width:960,height:540},gEpoch=1,ubo={frame:1,slot:0},FRAME_SLOTS=3,encEpoch=55,nativeResourceEpoch=10;
 var S={shader:[0,0,0],layout:17,topo:4,vb:Array.from({length:16},()=>({buf:0,stride:0,offset:0})),ib:{buf:0,fmt:0,offset:0}};
 var objs=new Map([[10,{version:3}]]),fr={upBytes:0},pdirty=false,passSt={pl:1,bg0:2,bg1:3,dyn0:4,dyn1:5};
 var drawCount=0,indirectDraws=0,nativePreparedHits=0,nativePreparedMisses=0,nativeWarmSpans=0,nativeWarmPackets=0,nativeWarmDraws=0;
 var u32=new Uint32Array(testEngineBytes),f32=new Float32Array(testEngineBytes),i32=new Int32Array(testEngineBytes),ringW=0,ringBase=0,ringSize=testEngineBytes.byteLength,RING_DATA=64,OP={WRAP:1};
 var sinceYield=0,executedLocal=0,lastYieldT=1e12,performance={now:()=>0},shaderSourcesReady=()=>true,isNode=false;
 var debugPsProbe=false,debugDrawN=0,testFallbacks=[];function doDraw(){testFallbacks.push([S.shader[0],S.layout,S.vb[0].offset]);drawCount++;}
 var testDone=false,testError='';
 )JS"]];assert(!graphicsContext.exception);
 NSString *worker=[NSString stringWithContentsOfFile:@"Resources/wgpu_worker.js" encoding:NSUTF8StringEncoding error:nil];assert(worker);
 [graphicsContext evaluateScript:between(worker,@"function nativePreparationReady()",@"function syncNativeDrawState()")];assert(!graphicsContext.exception);
 [graphicsContext evaluateScript:between(worker,@"async function runCommands(tail, head)",@"async function loop()")];assert(!graphicsContext.exception);
 uint32_t tail=64;auto append=[&](uint32_t op,std::initializer_list<uint32_t> values){uint32_t offset=tail;memory[tail/4]=op;memory[tail/4+1]=values.size();std::copy(values.begin(),values.end(),memory.begin()+tail/4+2);tail+=8+values.size()*4;return offset;};
 append(18,{0,7});append(18,{2,91});append(21,{0,1,50,16,32});append(22,{60,57,8});append(12,{10,0,4,0x12345678});append(32,{1,36,1,0,0,0});append(21,{0,1,50,16,96});append(47,{10,4,4,0x87654321});append(32,{1,72,1,0,0,0});append(0,{});
 graphicsContext[@"testHead"]=@(tail);
 [graphicsContext evaluateScript:@"runCommands(64,testHead).then(t=>{testTail=t;testDone=true;}).catch(e=>{testError=String(e.stack||e);});"];assert(!graphicsContext.exception);
 if(graphicsContext[@"testError"].toString.length){fprintf(stderr,"%s\n",graphicsContext[@"testError"].toString.UTF8String);return 1;}
 assert(graphicsContext[@"testDone"].toBool);
 JSValue *check=[graphicsContext evaluateScript:@"testTail===testHead && executedLocal===10 && drawCount===2 && nativePreparedHits===2 && nativePreparedMisses===0 && nativeWarmPackets===9 && nativeWarmDraws===2 && fr.upBytes===8 && objs.get(10).version===5 && S.shader[0]===7 && S.shader[2]===91 && S.vb[0].offset===96 && S.ib.offset===8 && pdirty && passSt.pl===null"];assert(check.toBool);
 [graphicsContext evaluateScript:@"flushDrawBatch()"];assert(!graphicsContext.exception);
 assert(graphicsContext[@"capturedBatches"][0][0][0].toUInt32==28&&graphicsContext[@"capturedBatches"][0][0][2].toUInt32==0);
 assert(NativeDraw::vertices[0].id==0);NW::replay(0,(WGPURenderPassEncoder)(uintptr_t)42);assert(NativeDraw::replayTrace[0][1]==32&&NativeDraw::replayTrace[1][1]==96);
 NW::clear();NP::clearSnapshots(c);
 tail=64;append(21,{0,1,50,16,128});append(19,{999});append(32,{0,3,1,0,0,0});append(0,{});graphicsContext[@"testHead"]=@(tail);
 [graphicsContext evaluateScript:@"testDone=false;runCommands(64,testHead).then(t=>{testTail=t;testDone=true;}).catch(e=>{testError=String(e.stack||e);});"];
 if(graphicsContext[@"testError"].toString.length){fprintf(stderr,"%s\n",graphicsContext[@"testError"].toString.UTF8String);return 1;}
 assert(graphicsContext[@"testDone"].toBool);
 check=[graphicsContext evaluateScript:@"testTail===testHead && executedLocal===14 && testFallbacks.length===1 && testFallbacks[0][1]===999 && testFallbacks[0][2]===128 && nativePreparedMisses===1 && objs.get(10).version===5"];assert(check.toBool);
 NW::clear();NP::clearSnapshots(c);assert(pipelineRefs==pipelineReleases&&groupRefs==groupReleases);
 puts("PASS: actual JSC command loop, compiled spans, final shader/vertex/index state, uploads/versions/counters, ordered batch ranges and exactly one prepared miss before JS fallback.");
}return 0;}
