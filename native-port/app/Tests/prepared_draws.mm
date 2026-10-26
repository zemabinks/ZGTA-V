// Production snapshot resolver with real JavaScriptCore and memory-only GPU
// handles. The real renderer remains covered by the game benchmark separately.
#import <Foundation/Foundation.h>
#import <JavaScriptCore/JavaScriptCore.h>
#include "webgpu.h"
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <limits>
#include <string>
#include <vector>
static JSContext *graphicsContext;
static WGPUDevice gpuDevice;
static void *engineMemory;
static uint64_t engineMemorySize;
static bool nativeOperationProfile=true;
static void (*nativeDetailProfileReport)();
struct NativeCallClock {NativeCallClock(bool,const char *){}};
struct NativeOperationClock {NativeOperationClock(const char *){}};
static void pg_log(const char *){assert(false);}
static void *rawGPUHandle(JSContextRef,JSValueRef){return nullptr;}
static JSValue *wrapGPU(JSContext *c,NSString *,void *,void(*)(void *)){return [JSValue valueWithNewObjectInContext:c];}
static unsigned pipelineRefs=0,pipelineReleases=0,groupRefs=0,groupReleases=0,pipelineSets=0,groupSets=0;
extern "C" WGPUBuffer wgpuDeviceCreateBuffer(WGPUDevice,const WGPUBufferDescriptor *){return (WGPUBuffer)(uintptr_t)1;}
extern "C" void wgpuBufferRelease(WGPUBuffer){}
extern "C" WGPUQueue wgpuDeviceGetQueue(WGPUDevice){return (WGPUQueue)(uintptr_t)1;}
extern "C" void wgpuQueueWriteBuffer(WGPUQueue,WGPUBuffer,uint64_t,const void *,size_t){}
extern "C" void wgpuRenderPipelineAddRef(WGPURenderPipeline){pipelineRefs++;}
extern "C" void wgpuRenderPipelineRelease(WGPURenderPipeline){pipelineReleases++;}
extern "C" void wgpuBindGroupAddRef(WGPUBindGroup){groupRefs++;}
extern "C" void wgpuBindGroupRelease(WGPUBindGroup){groupReleases++;}
extern "C" void wgpuRenderPassEncoderSetPipeline(WGPURenderPassEncoder,WGPURenderPipeline){pipelineSets++;}
extern "C" void wgpuRenderPassEncoderSetBindGroup(WGPURenderPassEncoder,uint32_t,WGPUBindGroup,size_t,const uint32_t *){groupSets++;}
#include "NativeUniforms.inc"
namespace NativeDraw {
struct Plan {};
struct Buffer {};
static Buffer *buffer(uint32_t){return nullptr;}
static std::array<double,9> lastDraw;
static unsigned issued=0;
static void draw(WGPURenderPassEncoder,Plan *,const double *values){std::copy(values,values+9,lastDraw.begin());issued++;}
}
#include "NativePipelineCache.inc"
#include "NativePreparedDraws.inc"
int main(){@autoreleasepool {
 namespace NP=NativePreparedDraw;namespace NU=NativeUniforms;
 graphicsContext=[[JSContext alloc] init];NU::install(graphicsContext);NativePipeline::install(graphicsContext);NP::install(graphicsContext);
 JSContextRef c=graphicsContext.JSGlobalContextRef;JSValueRef error=nullptr;
 uint32_t memory[64]={};engineMemory=memory;engineMemorySize=sizeof memory;
 uint32_t data[]={1,36,2,3,(uint32_t)-4,5};memcpy(memory+10,data,sizeof data);
 NP::DrawContext context;context.tail=1;context.epoch=1;context.frame=1;context.slot=0;context.slots=3;context.resourceGeneration=10;context.encoder=55;context.width=960;context.height=540;context.encoderValue=JSValueMakeNumber(c,55);
 NativePipeline::state[2]=17;NP::layouts[17]=NativePipeline::Layout{};
 auto identity=NativePipeline::key(&NP::layouts[17],1);
 JSObjectRef owner=JSObjectMake(c,nullptr,nullptr);JSValueProtect(c,owner);NativePipeline::values[identity]=owner;
 NativeDraw::Plan plan;NP::Record record;record.owner=owner;record.pipeline=(WGPURenderPipeline)(uintptr_t)101;record.plan=&plan;record.generation=10;record.pipelineGeneration=NativePipeline::generation;NP::records[identity]=record;
 assert(NP::prepareNative(c,10,context,&error)==0&&!error);
 const std::array<double,9> expected={1,36,2,3,-4,5,55,960,540};assert(NP::snapshots[0].draw==expected);
 JSValueRef args[]={JSValueMakeNumber(c,10),JSValueMakeNumber(c,1),JSValueMakeNumber(c,1),JSValueMakeNumber(c,1),JSValueMakeNumber(c,0),JSValueMakeNumber(c,3),JSValueMakeNumber(c,55),JSValueMakeNumber(c,10),JSValueMakeNumber(c,960),JSValueMakeNumber(c,540)};
 assert(NU::number(c,NP::prepare(c,nullptr,nullptr,10,args,&error))==1);
 assert(NP::snapshots[1].draw==NP::snapshots[0].draw&&pipelineRefs==2&&NP::roots.size()==1);
 auto pass=(WGPURenderPassEncoder)(uintptr_t)42;NP::replay(0,pass);NP::replay(1,pass);assert(pipelineSets==1&&groupSets==0&&NativeDraw::issued==2&&NativeDraw::lastDraw==NP::snapshots[0].draw);
 context.resourceGeneration=11;assert(NP::prepareNative(c,10,context,&error)==-1);context.resourceGeneration=10;
 NativePipeline::generation++;assert(NP::prepareNative(c,10,context,&error)==-1);NativePipeline::generation--;
 NativePipeline::values[identity]=JSValueMakeNull(c);assert(NP::prepareNative(c,10,context,&error)==-1);NativePipeline::values[identity]=owner;
 for(double index:{-1.0,0.5,64.0,std::numeric_limits<double>::quiet_NaN()})assert(NP::prepareNative(c,index,context,&error)==-1);
 engineMemorySize=23;assert(NP::prepareNative(c,0,context,&error)==-1);engineMemorySize=sizeof memory;
 // Real cache resolution, immutable offsets, proxy refresh dependencies and
 // resource stamps are identical through numeric and scripting entry points.
 uint8_t constants[64];for(unsigned i=0;i<64;i++)constants[i]=i;NU::shadows[10]={constants,sizeof constants,1};NU::state[0]=10;NU::state[1]=1;NU::bindings[16]=30;
 auto *pack=new NU::Pack;pack->members={{0,16,0}};JSObjectRef packObject=JSObjectMake(c,NU::packClass(),pack);JSValueProtect(c,packObject);
 auto *cache=new NU::BindingCache;cache->sources={0,0,1,0,3,0};cache->epoch=1;cache->keys[0].emplace_back();cache->last[0]=0;
 JSObjectRef cacheObject=JSObjectMake(c,NU::cacheClass(),cache);JSValueProtect(c,cacheObject);
 auto &key=cache->keys[0][0];key.entry=JSObjectMake(c,nullptr,nullptr);JSValueProtect(c,key.entry);JSValueRef initial=JSValueMakeNumber(c,777);key.dynamic=JSObjectMakeArray(c,1,&initial,nullptr);JSValueProtect(c,key.dynamic);
 key.ids={10,1,30};key.versions={1,0,0};key.pack=pack;key.packObject=packObject;key.packSize=16;key.chunkId=0x40000000;key.dynamicCount=1;key.group=(WGPUBindGroup)(uintptr_t)201;
 JSObjectRef resource=JSObjectMake(c,nullptr,nullptr),proxy=JSObjectMake(c,nullptr,nullptr);JSValueProtect(c,resource);JSValueProtect(c,proxy);
 JSObjectSetProperty(c,resource,NP::field("proxy_filter"),proxy,kJSPropertyAttributeNone,&error);key.used={resource};key.usedIds={0};key.dirty={resource};key.proxyChecks={proxy};key.proxyCoverage=1;
 auto clean=[&](){JSObjectSetProperty(c,proxy,NP::field("dirty"),JSValueMakeBoolean(c,false),kJSPropertyAttributeNone,&error);};clean();
 auto *proxyPlan=new NU::ProxyPlan;proxyPlan->slots={0};proxyPlan->samples={0};JSObjectRef proxyObject=JSObjectMake(c,NU::proxyClass(),proxyPlan);JSValueProtect(c,proxyObject);NU::srvs[30]={99,false};NU::textureFlags[99]=4;
 auto &cachedRecord=NP::records[identity];cachedRecord.needed[0]=true;cachedRecord.caches[0]=cacheObject;cachedRecord.nativeCaches[0]=cache;cachedRecord.proxies[0]=proxyObject;cachedRecord.nativeProxies[0]=proxyPlan;
 assert(NP::prepareNative(c,10,context,&error)==2);assert(NP::snapshots[2].offsets[0]==0&&groupRefs==1);
 assert(NU::number(c,JSObjectGetProperty(c,resource,NP::field("enc"),nullptr))==55&&JSValueToBoolean(c,JSObjectGetProperty(c,proxy,NP::field("dirty"),nullptr)));
 assert(NP::prepareNative(c,10,context,&error)==-2&&NP::snapshots.size()==3);clean();constants[16]=99;NU::shadows[10].version++;
 assert(NP::prepareNative(c,10,context,&error)==3&&NP::snapshots[3].offsets[0]==256&&NP::snapshots[2].offsets[0]==0);
 NP::replay(2,pass);NP::replay(3,pass);NP::replay(3,pass);assert(groupSets==2);
 clean();NP::directResolution=false;assert(NU::number(c,NP::prepare(c,nullptr,nullptr,10,args,&error))==4&&!key.dynamicDirty);NP::directResolution=true;
 clean();key.proxyCoverage=0;assert(NP::prepareNative(c,10,context,&error)==-2);key.proxyCoverage=1;
 key.dynamicCount=2;assert(NP::prepareNative(c,10,context,&error)==-1);key.dynamicCount=1;
 NP::clearSnapshots(c);assert(NP::snapshots.empty()&&NP::roots.empty()&&pipelineRefs==pipelineReleases&&groupRefs==groupReleases);
 NP::records.clear();NP::layouts.clear();NativePipeline::values.clear();
 for(JSValueRef value:{(JSValueRef)owner,(JSValueRef)packObject,(JSValueRef)cacheObject,(JSValueRef)key.entry,(JSValueRef)key.dynamic,(JSValueRef)resource,(JSValueRef)proxy,(JSValueRef)proxyObject})JSValueUnprotect(c,value);
 assert(!error);puts("PASS: production numeric/public prepared draws, generations, ownership, bounds, immutable constants, proxy dirty chains, stamps, replay deduplication and balanced GPU references.");
}return 0;}
