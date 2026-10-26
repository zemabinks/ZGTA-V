// Exercise the production resolver with real JavaScriptCore values and a memory-only
// GPU stub. GPU correctness is covered separately by the five-scene simulator run.
#import <Foundation/Foundation.h>
#import <JavaScriptCore/JavaScriptCore.h>
#include "webgpu.h"
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
static JSContext *graphicsContext;
static WGPUDevice gpuDevice;
static void *engineMemory;
static uint64_t engineMemorySize;
struct NativeCallClock {NativeCallClock(bool,const char *){}};
struct NativeOperationClock {NativeOperationClock(const char *){}};
static bool nativeOperationProfile=false;
static uint32_t loggedErrors=0;
static void pg_log(const char *){loggedErrors++;}
static void *rawGPUHandle(JSContextRef,JSValueRef){return nullptr;}
static JSValue *wrapGPU(JSContext *c,NSString *,void *,void(*)(void *)){return [JSValue valueWithNewObjectInContext:c];}
extern "C" WGPUBuffer wgpuDeviceCreateBuffer(WGPUDevice,const WGPUBufferDescriptor *){return (WGPUBuffer)(uintptr_t)1;}
extern "C" void wgpuBufferRelease(WGPUBuffer){}
extern "C" WGPUQueue wgpuDeviceGetQueue(WGPUDevice){return (WGPUQueue)(uintptr_t)1;}
extern "C" void wgpuQueueWriteBuffer(WGPUQueue,WGPUBuffer,uint64_t,const void *,size_t){}
#include "NativeUniforms.inc"
int main(){@autoreleasepool {
 using namespace NativeUniforms;
 graphicsContext=[[JSContext alloc] init];install(graphicsContext);JSContextRef c=graphicsContext.JSGlobalContextRef;
 // Production uploads: unchanged partial ranges preserve native packed constants.
 uint8_t uploadSource[48],uploadTarget[32];memset(uploadSource,7,sizeof uploadSource);memset(uploadTarget,7,sizeof uploadTarget);
 engineMemory=uploadSource;engineMemorySize=sizeof uploadSource;shadows[90]={uploadTarget,sizeof uploadTarget,12};
 auto uploadRange=[&](uint32_t offset,uint32_t source,uint32_t size){JSValueRef args[]={JSValueMakeNumber(c,90),JSValueMakeNumber(c,offset),JSValueMakeNumber(c,source),JSValueMakeNumber(c,size)};upload(c,nullptr,nullptr,4,args,nullptr);};
 cacheUploadContents=true;uploadRange(4,8,16);assert(shadows[90].version==12);
 uploadSource[9]=42;uploadRange(4,8,16);assert(shadows[90].version==13&&uploadTarget[5]==42&&uploadTarget[3]==7&&uploadTarget[20]==7);
 uploadRange(4,8,16);assert(shadows[90].version==13);uploadRange(32,48,0);assert(shadows[90].version==13);
 uint32_t beforeErrors=loggedErrors;uploadRange(31,0,2);uploadRange(0,47,2);assert(loggedErrors==beforeErrors+2&&shadows[90].version==13);
 cacheUploadContents=false;uploadRange(4,8,16);assert(shadows[90].version==14);uploadRange(32,48,0);assert(shadows[90].version==15);
 nativeOperationProfile=true;uploadRange(4,8,16);assert(uploadStats.calls==1&&uploadStats.unchangedCalls==1&&uploadStats.bytes==16&&uploadStats.unchangedBytes==16);
 nativeOperationProfile=false;uploadStats={};shadows.erase(90);engineMemory=nullptr;engineMemorySize=0;
 // Profiling must respect published packet boundaries and ring wrapping.
 uint32_t packetMemory[64]={};engineMemory=packetMemory;engineMemorySize=sizeof packetMemory;
 auto packet=[&](uint32_t offset,uint32_t op,uint32_t words){packetMemory[offset/4]=op;packetMemory[offset/4+1]=words;return offset+8+words*4;};
 uint32_t packetHead=packet(64,23,6);packetHead=packet(packetHead,32,6);packetHead=packet(packetHead,32,6);packetHead=packet(packetHead,12,3);packetHead=packet(packetHead,32,6);
 profilePacketRange(0,64,packetHead,sizeof packetMemory);assert(packetCounts[23]==1&&packetCounts[32]==3&&packetCounts[12]==1&&packetDrawSpans[2]==1&&packetDrawSpans[1]==1);
 packetCounts.fill(0);packetDrawSpans.fill(0);profilePacketRange(0,64,100,sizeof packetMemory);assert(packetCounts[23]==1&&packetCounts[32]==0);
 packetCounts.fill(0);packetDrawSpans.fill(0);packet(224,1,0);packet(64,32,6);profilePacketRange(0,224,96,sizeof packetMemory);assert(packetCounts[1]==1&&packetCounts[32]==1&&packetDrawSpans[1]==1);
 packetCounts.fill(0);packetDrawSpans.fill(0);packet(64,32,1000);profilePacketRange(0,64,96,sizeof packetMemory);assert(packetCounts[32]==0);
 profilePacketRange(0,65,96,sizeof packetMemory);profilePacketRange(4,64,96,sizeof packetMemory);assert(packetCounts[32]==0);
 engineMemory=nullptr;engineMemorySize=0;
 uint8_t a[64],b[64];for(uint32_t i=0;i<64;i++){a[i]=i;b[i]=128+i;}
 shadows[10]={a,sizeof a,1};shadows[11]={b,sizeof b,1};
 state[0]=10;state[1]=1;state[3]=11;state[4]=0;bindings[16]=20;
 Pack *pack=new Pack;pack->members={{0,16,0},{1,16,16}};
 JSObjectRef packObject=JSObjectMake(c,packClass(),pack);JSValueProtect(c,packObject);
 BindingCache cache;cache.sources={0,0,1,0,0,1,1,1,3,0};cache.epoch=1;cache.keys[0].emplace_back();cache.last[0]=0;
 auto &key=cache.keys[0][0];key.entry=JSObjectMake(c,nullptr,nullptr);JSValueProtect(c,key.entry);
 JSValueRef initial=JSValueMakeNumber(c,777);key.dynamic=JSObjectMakeArray(c,1,&initial,nullptr);JSValueProtect(c,key.dynamic);
 key.dynamicCount=1;key.nativeDynamicOffset=777;key.pack=pack;key.packObject=packObject;key.packSize=32;key.chunkId=0x40000000u;
 for(size_t i=0;i<cache.sources.size();i+=2){uint32_t kind=cache.sources[i],id=bound(0,kind,cache.sources[i+1]);key.ids.push_back(id);key.versions.push_back(kind==0?version(id):0);}
 JSValueRef error=nullptr;
 auto *resolved=resolveCacheNative(c,&cache,0,1,1,1,3,false,&error);assert(resolved==&key&&!error);
 assert(key.dynamicDirty&&key.nativeDynamicOffset==RingBytes);
 assert(number(c,JSObjectGetPropertyAtIndex(c,key.dynamic,0,nullptr))==777);
 auto &bytes=ringChunks[0].stages[1].bytes;assert(!memcmp(bytes.data(),a+16,16)&&!memcmp(bytes.data()+16,b,16));
 uint32_t firstOffset=key.nativeDynamicOffset;
 assert(resolveCacheNative(c,&cache,0,1,1,1,3,false,&error)==&key&&ringOffset==256);
 // Identical uploads must reuse the existing ring offset; changed bytes must
 // produce a new immutable snapshot even when the same buffer remains bound.
 engineMemory=uploadSource;engineMemorySize=sizeof uploadSource;memcpy(uploadSource,a+16,16);cacheUploadContents=true;
 JSValueRef sameArgs[]={JSValueMakeNumber(c,10),JSValueMakeNumber(c,16),JSValueMakeNumber(c,0),JSValueMakeNumber(c,16)};
 upload(c,nullptr,nullptr,4,sameArgs,&error);assert(shadows[10].version==1);
 assert(resolveCacheNative(c,&cache,0,1,1,1,3,false,&error)==&key&&key.nativeDynamicOffset==firstOffset&&ringOffset==256);
 uploadSource[0]=99;upload(c,nullptr,nullptr,4,sameArgs,&error);assert(shadows[10].version==2&&a[16]==99);
 cacheUploadContents=false;engineMemory=nullptr;engineMemorySize=0;
 assert(resolveCacheNative(c,&cache,0,1,1,1,3,false,&error)==&key);
 assert(key.nativeDynamicOffset==RingBytes+256&&firstOffset==RingBytes);
 assert(bytes[0]==16&&bytes[256]==99); // earlier draw's constants remain immutable
 assert(resolveCacheNative(c,&cache,0,1,1,1,3,true,&error)==&key&&!key.dynamicDirty);
 assert(number(c,JSObjectGetPropertyAtIndex(c,key.dynamic,0,nullptr))==key.nativeDynamicOffset);
 state[1]=2;
 assert(resolveCacheNative(c,&cache,0,1,1,1,3,false,&error)==&key&&bytes[512]==a[32]);
 assert(resolveCacheNative(c,&cache,0,1,2,2,3,false,&error)==&key&&key.nativeDynamicOffset==2*RingBytes);
 assert(resolveCacheNative(c,&cache,0,1,2,2,3,true,&error)==&key&&!key.dynamicDirty);
 bindings[16]=21;assert(resolveCacheNative(c,&cache,0,1,2,2,3,false,&error)==nullptr);bindings[16]=20;
 ringOffset=RingBytes-UniformWindow;
 uint32_t oldOffset=key.nativeDynamicOffset;shadows[10].version++;
 assert(resolveCacheNative(c,&cache,0,1,2,2,3,false,&error)==nullptr); // changed chunk requires a new bind group
 assert(key.nativeDynamicOffset==oldOffset&&ringChunkIndex==1);
 assert(resolveCacheNative(c,&cache,0,1,3,0,4,false,&error)==nullptr); // frame slot count is fixed
 // Usage marks are stable within an encoder and must be refreshed after a submit.
 key.used={JSObjectMake(c,nullptr,nullptr),JSObjectMake(c,nullptr,nullptr)};
 for(JSObjectRef resource:key.used)JSValueProtect(c,resource);
 uint64_t encoderToMark=42;uint32_t marks=0;JSStringRef enc=JSStringCreateWithUTF8CString("enc");
 auto mark=[&](size_t i){marks++;JSObjectSetProperty(c,key.used[i],enc,JSValueMakeNumber(c,encoderToMark),kJSPropertyAttributeNone,&error);return !error;};
 stampResources(key,42,true,mark);assert(marks==2&&key.usedEncoder==42);
 stampResources(key,42,true,mark);assert(marks==2);
 encoderToMark=43;stampResources(key,43,true,mark);assert(marks==4&&key.usedEncoder==43);
 stampResources(key,43,false,mark);assert(marks==6);
 stampResources(key,44,true,[&](size_t){return false;});assert(key.usedEncoder==43);
 encoderToMark=44;stampResources(key,44,true,mark);assert(marks==8&&key.usedEncoder==44);
 assert(number(c,JSObjectGetProperty(c,key.used[0],enc,nullptr))==44);
 for(JSObjectRef resource:key.used)JSValueUnprotect(c,resource);JSStringRelease(enc);
 JSValueUnprotect(c,key.entry);JSValueUnprotect(c,key.dynamic);
 assert(resolveCacheNative(c,&cache,0,2,3,0,3,false,&error)==nullptr&&cache.keys[0].empty());
 JSValueUnprotect(c,packObject);
 // Store more than the old 32 entries through the production C API.
 JSObjectRef sources=JSObjectMakeTypedArray(c,kJSTypedArrayTypeUint32Array,6,nullptr);
 auto *sourceWords=(uint32_t *)JSObjectGetTypedArrayBytesPtr(c,sources,nullptr);
 const uint32_t inputs[]={0,0,2,0,3,0};memcpy(sourceWords,inputs,sizeof inputs);
 JSValueRef makeArgs[]={sources};JSValueRef handle=makeBindingCache(c,nullptr,nullptr,1,makeArgs,&error);JSValueProtect(c,handle);
 auto *many=(BindingCache *)JSObjectGetPrivate(JSValueToObject(c,handle,nullptr));
 JSValueRef storeArgs[]={handle,JSValueMakeNumber(c,0),JSValueMakeNumber(c,7)};
 for(uint32_t i=0;i<128;i++){bindings[16]=300+i;bindings[0]=5;assert(number(c,storeBindingCache(c,nullptr,nullptr,3,storeArgs,&error))==i);}
 assert(many->keys[0].size()==128&&!error);
 for(uint32_t i=0;i<128;i++){bindings[16]=300+i;uint32_t hit=findCache(c,many,0,7);assert((hit&255)==i+1&&(hit&256));}
 bindings[16]=300;state[0]=11;uint32_t changedConstants=findCache(c,many,0,7);assert((changedConstants&255)==1&&!(changedConstants&256));
 state[0]=10;
 // Force a hash collision: the wrong resource tuple must be rejected.
 many->last[0]=UINT32_MAX;many->buckets[0][many->keys[0][0].bindingHash].push_back(127);
 assert((findCache(c,many,0,7)&255)==1);
 many->buckets[0][many->keys[0][0].bindingHash].pop_back();
 bindings[16]=999;assert(number(c,storeBindingCache(c,nullptr,nullptr,3,storeArgs,&error))==0);
 bindings[16]=300;assert(findCache(c,many,0,7)==0);
 bindings[16]=427;assert((findCache(c,many,0,7)&255)==128);
 assert(findCache(c,many,0,8)==0&&many->buckets[0].empty());
 // Exercise owners at all three stage offsets, not just numeric keys.
 for(uint32_t at:{0u,128u,383u})JSObjectSetPropertyAtIndex(c,many->retained,at,JSObjectMake(c,nullptr,nullptr),&error);
 JSStringRef lengthName=JSStringCreateWithUTF8CString("length");
 assert(number(c,JSObjectGetProperty(c,many->retained,lengthName,&error))==384);
 cacheEpoch(c,many,9);assert(number(c,JSObjectGetProperty(c,many->retained,lengthName,&error))==0);
 assert(JSValueIsUndefined(c,JSObjectGetPropertyAtIndex(c,many->retained,383,&error)));
 JSStringRelease(lengthName);cacheEpoch(c,many,8);

 // The paired benchmark's reference mode keeps the original capacity/search.
 hashedBindingCache=false;
 JSValueRef referenceArgs[]={handle,JSValueMakeNumber(c,1),JSValueMakeNumber(c,8)};
 for(uint32_t i=0;i<64;i++){bindings[152+16]=500+i;storeBindingCache(c,nullptr,nullptr,3,referenceArgs,&error);}
 assert(many->keys[1].size()==32);
 bindings[152+16]=500;assert(findCache(c,many,1,8)==0);
 bindings[152+16]=563;assert(findCache(c,many,1,8)!=0);
 hashedBindingCache=true;JSValueUnprotect(c,handle);
 // A cached converted view is reusable only when every conversion is clean.
 BindingKey converted;converted.proxyCoverage=1;
 JSObjectRef depth=JSObjectMake(c,nullptr,nullptr),filtered=JSObjectMake(c,nullptr,nullptr);
 JSValueProtect(c,depth);JSValueProtect(c,filtered);converted.proxyChecks={depth,filtered};
 JSStringRef dirty=JSStringCreateWithUTF8CString("dirty");
 auto dirtyFlag=[&](JSObjectRef object,bool value){JSObjectSetProperty(c,object,dirty,JSValueMakeBoolean(c,value),kJSPropertyAttributeNone,&error);};
 dirtyFlag(depth,false);dirtyFlag(filtered,false);assert(proxiesReady(c,converted,1,&error));
 assert(!proxiesReady(c,converted,2,&error)); // incomplete coverage must use the original refresh path
 dirtyFlag(depth,true);assert(!proxiesReady(c,converted,1,&error)); // filtered child may still be clean
 assert(proxiesReady(c,converted,0,&error)); // no required conversion
 dirtyFlag(depth,false);dirtyFlag(filtered,true);assert(!proxiesReady(c,converted,1,&error));
 dirtyFlag(filtered,false);assert(proxiesReady(c,converted,1,&error));
 JSObjectDeleteProperty(c,filtered,dirty,&error);assert(!proxiesReady(c,converted,1,&error));
 converted.proxyChecks.clear();assert(!proxiesReady(c,converted,1,&error));
 JSStringRelease(dirty);JSValueUnprotect(c,depth);JSValueUnprotect(c,filtered);assert(!error);
 // Execute the production view selector too, including its cached-view return.
 NSString *worker=[NSString stringWithContentsOfFile:@"Resources/wgpu_worker.js" encoding:NSUTF8StringEncoding error:nil];
 NSRange begin=[worker rangeOfString:@"function srvView("],end=[worker rangeOfString:@"// ---- depth textures sampled" options:0 range:NSMakeRange(begin.location,worker.length-begin.location)];
 assert(begin.location!=NSNotFound&&end.location!=NSNotFound);
 [graphicsContext evaluateScript:[NSString stringWithUTF8String:R"JS(
 var sawProxy=false,fixtureTexture;
 var objs={get:()=>fixtureTexture};
 var isDepth=f=>f.startsWith('depth');
 var needsFloatProxy=(t,b)=>b.sample==='float'&&t.nativeFloatProxy;
 var makeTexture=(format,nativeFloatProxy=false)=>({kind:'texture',format,nativeFloatProxy,dirty:false,desc:{mipLevelCount:1,size:{depthOrArrayLayers:1}},tex:{createView:()=>({})}});
 var depthCopy=makeTexture('r32float',true),stencilCopy=makeTexture('r8uint'),filteredCopy=makeTexture('rgba16float'),comparisonCopy=makeTexture('depth32float');
 var depthProxy=(t,kind)=>kind==='stencil'?stencilCopy:depthCopy;
 var floatToDepthProxy=t=>comparisonCopy;
 var filterableFloatProxy=t=>filteredCopy;
 var check=(ok,message)=>{if(!ok)throw Error(message)};
 var mapFormat=()=>({format:'rgba8unorm'}),logOnce=()=>{};
 var srvFixture=()=>({res:1,fmt:0,a:0,b:1,c:0,d:1,views:new Map()});
 )JS"]];
 [graphicsContext evaluateScript:[worker substringWithRange:NSMakeRange(begin.location,end.location-begin.location)]];
 [graphicsContext evaluateScript:[NSString stringWithUTF8String:R"JS(
 fixtureTexture=makeTexture('depth32float');
 var viewSrv=srvFixture(),dependencies=[];
 var firstView=srvView(viewSrv,{dim:'2d',sample:'float'},dependencies);
 check(dependencies.length===2&&dependencies[0]===depthCopy&&dependencies[1]===filteredCopy,'depth/filter dependency chain');
 dependencies=[];check(srvView(viewSrv,{dim:'2d',sample:'float'},dependencies)===firstView,'cached converted view');
 check(dependencies.length===2&&dependencies[0]===depthCopy,'cached view retains both dependencies');
 dependencies=[];srvView(srvFixture(),{dim:'2d',sample:'uint'},dependencies);check(dependencies.length===1&&dependencies[0]===stencilCopy,'stencil dependency');
 fixtureTexture=makeTexture('r32float',true);dependencies=[];srvView(srvFixture(),{dim:'2d',sample:'float'},dependencies);check(dependencies.length===1&&dependencies[0]===filteredCopy,'float filtering dependency');
 dependencies=[];srvView(srvFixture(),{dim:'2d',sample:'depth'},dependencies);check(dependencies.length===1&&dependencies[0]===comparisonCopy,'comparison dependency');
 fixtureTexture=makeTexture('rgba8unorm');dependencies=[];srvView(srvFixture(),{dim:'2d',sample:'float'},dependencies);check(dependencies.length===0,'ordinary texture needs no conversion');
 )JS"]];
 assert(!graphicsContext.exception);
 puts("Native uniform resolver: identical/changed/partial/empty uploads, bounds checks, profile counters, deferred JS synchronization, cached hits, changed constants, frame slots, immutable offsets, resource mismatch, chunk rollover, invalidation, encoder usage stamps, 128 cache entries, collision checks, eviction, reference lookup, conversion dirty chains and production view dependencies passed.");
}return 0;}
