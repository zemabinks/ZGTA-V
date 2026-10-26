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
static Buffer *buffer(uint32_t id){static Buffer gpu;return id==999?&gpu:nullptr;}
struct Vertex {uint32_t id=0,stride=0;uint64_t offset=0;};
static std::array<Vertex,16> vertices;
static uint32_t indexId,indexFormat;static uint64_t indexOffset;
static std::vector<std::array<uint64_t,3>> replayTrace;
static std::array<double,9> lastDraw;
static unsigned issued=0;
static void draw(WGPURenderPassEncoder,Plan *,const double *values){std::copy(values,values+9,lastDraw.begin());issued++;replayTrace.push_back({vertices[0].id,vertices[0].offset,indexOffset});}
}
#include "NativePipelineCache.inc"
#include "NativePreparedDraws.inc"
#include "NativeWarmDispatch.inc"
