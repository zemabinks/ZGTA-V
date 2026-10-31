"""Execute the actual renderer accounting paths without a live GPU or app launch."""
from pathlib import Path
import subprocess
import tempfile
import unittest

APP = Path(__file__).resolve().parents[2] / "app"
SOURCE = APP / "Source/MetalRenderer/MRRenderer.mm"


def span(text, start, end):
    return text[text.index(start):text.index(end)]


class MetalAccounting101(unittest.TestCase):
    def compile_run(self, fixture, *, objc=False):
        with tempfile.TemporaryDirectory(prefix="zgta-metal-accounting101-") as directory:
            path = Path(directory)
            source = path / ("fixture.mm" if objc else "fixture.cpp")
            source.write_text(fixture)
            command = ["/usr/bin/clang++", "-std=c++17", "-Wall", "-Wextra",
                       "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                       "-I", str(APP / "Source"), "-I", str(APP / "Source/MetalRenderer")]
            if objc:
                command += ["-fobjc-arc", "-framework", "Foundation"]
            command += [str(source), "-o", str(path / "fixture")]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(path / "fixture")], capture_output=True,
                                    text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_actual_pipeline_wait_reaches_sampler_and_keeps_shared_budget(self):
        source = SOURCE.read_text()
        wait = span(source, "\tif (!pipe->ready.load(std::memory_order_acquire) && R->pipeWaitMs < 8)",
                    '\n\tif (!pipe->ready.load(std::memory_order_acquire)) { drawOutcome')
        exported = span(source, "\t const PGFrameWork work{", "\n\t performanceSampler.record")
        self.compile_run(r'''
#include <atomic>
#include <cassert>
#include <cmath>
#include "NativePerformanceSampler.h"
struct FrameWork { double idle=0,pipeline=0,uploads=0,uploadBytes=0,gpuWait=0,submit=0; };
struct Renderer { double pipeWaitMs=0;FrameWork work; } renderer;
static Renderer* R=&renderer;
struct Pipe { std::atomic<bool> ready{false}; } pipeline;
static Pipe* pipe=&pipeline;
static double clockMS=0,readyAt=-1;
static double nowMs(){return clockMS;}
static void usleep(unsigned micros){clockMS+=micros/1000.;if(readyAt>=0&&clockMS>=readyAt)pipe->ready=true;}
static void drawWait(){
''' + wait + r'''
}
static PGFrameWork frameWork(){
''' + exported + r'''
 return work;
}
int main(){
 pipe->ready=true;drawWait();assert(R->pipeWaitMs==0&&R->work.pipeline==0);
 pipe->ready=false;readyAt=2;drawWait();assert(R->pipeWaitMs==2&&R->work.pipeline==2);
 pipe->ready=false;readyAt=-1;drawWait();assert(R->pipeWaitMs==8&&R->work.pipeline==8);
 drawWait();assert(clockMS==8&&R->work.pipeline==8); // budget shared across draws
 PGNativePerformanceSampler sampler;sampler.enable(true);
 auto gauges=[](){return PGNativePerformanceMetrics{};};
 sampler.record(0,16,1,frameWork(),gauges);
 sampler.record(1000,16,1,frameWork(),gauges);
 PGNativePerformanceMetrics value{};assert(sampler.read(&value)&&value.pipelineWaitMS==8);
 R->pipeWaitMs=0;R->work=FrameWork(); // actual present-frame reset semantics
 pipe->ready=true;drawWait();assert(frameWork().pipeline==0);
 return 0;
}
''')

    def test_actual_present_maintenance_releases_only_completed_arena_ranges(self):
        source = SOURCE.read_text()
        collect = span(source, "\t// Reclaim completed retirements even when no new buffer is allocated.",
                       "\n\tdouble tn = nowMs();")
        present = span(source, "static void present(uint32_t texId)", "// ---- object creation")
        self.assertLess(present.index("waitSerial(next.lastSerial)"), present.index(collect))
        self.assertLess(present.index(collect), present.index("performanceSampler.record"))
        self.compile_run(r'''
#include <atomic>
#include <cassert>
#include <memory>
#include "MRBufferArena.h"
struct Storage{};
static PGBufferArena<std::shared_ptr<Storage>> bufferArena;
struct Renderer{std::atomic<uint64_t> completed{0};} renderer;
static Renderer* R=&renderer;
static void maintenance(){
''' + collect + r'''
}
int main(){
 using Arena=decltype(bufferArena);
 auto create=[](uint32_t){return std::make_shared<Storage>();};
 auto first=bufferArena.acquire(Arena::SlabBytes,0,create);
 auto second=bufferArena.acquire(Arena::SlabBytes,0,create);
 std::weak_ptr<Storage> firstLife=first.resource,secondLife=second.resource;
 bufferArena.retire(std::move(first),4);bufferArena.retire(std::move(second),9);
 maintenance();assert(bufferArena.backingSlabs()==2&&bufferArena.pendingRanges()==2);
 R->completed=4;maintenance();
 assert(bufferArena.backingSlabs()==2&&bufferArena.pendingRanges()==1);
 assert(!firstLife.expired()&&!secondLife.expired()); // warm empty + in-flight slab
 R->completed=9;maintenance();
 assert(bufferArena.backingSlabs()==1&&bufferArena.pendingRanges()==0);
 assert(!firstLife.expired()&&secondLife.expired());
 assert(bufferArena.activeBytes()==0&&bufferArena.pendingAllocationBytes()==0);
 assert(bufferArena.reusableBytes()==Arena::SlabBytes);
 maintenance();assert(bufferArena.backingSlabs()==1); // idempotent without acquire
 return 0;
}
''')

    def test_actual_depth_proxy_accounts_real_estimated_and_failed_storage(self):
        source = SOURCE.read_text()
        destructor = span(source, "Texture::~Texture() {", "\n\nstatic const uint32_t RING_DATA")
        refresh = span(source, "static void refreshDepthProxy(Texture *t) {", "\nstatic void prepareProxies")
        fixture = r'''
#import <Foundation/Foundation.h>
#include <algorithm>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <map>
#include <vector>
enum {MTLPixelFormatDepth32Float=252,MTLTextureType2D=2,MTLTextureType2DArray=3,
 MTLTextureUsageShaderRead=1,MTLTextureUsageRenderTarget=4,MTLStorageModePrivate=2,
 MTLLoadActionDontCare=0,MTLStoreActionStore=1,MTLPrimitiveTypeTriangle=3};
@protocol MTLTexture <NSObject>
@property(readonly) NSUInteger allocatedSize;
-(id<MTLTexture>)newTextureViewWithPixelFormat:(NSUInteger)format textureType:(NSUInteger)type levels:(NSRange)levels slices:(NSRange)slices;
@end
static NSUInteger allocationBytes=4096;static bool failAllocation=false;
static unsigned allocations=0,draws=0,ended=0;
@interface FakeTexture:NSObject<MTLTexture>@end
@implementation FakeTexture
-(NSUInteger)allocatedSize{return allocationBytes;}
-(id<MTLTexture>)newTextureViewWithPixelFormat:(NSUInteger)format textureType:(NSUInteger)type levels:(NSRange)levels slices:(NSRange)slices{return [FakeTexture new];}
@end
@interface MTLTextureDescriptor:NSObject
@property NSUInteger pixelFormat,width,height,mipmapLevelCount,textureType,arrayLength,usage,storageMode;
@end
@implementation MTLTextureDescriptor @end
@interface FakeDevice:NSObject
-(id<MTLTexture>)newTextureWithDescriptor:(MTLTextureDescriptor*)descriptor;
@end
@implementation FakeDevice
-(id<MTLTexture>)newTextureWithDescriptor:(MTLTextureDescriptor*)descriptor{allocations++;return failAllocation?nil:[FakeTexture new];}
@end
@interface FakeAttachment:NSObject
@property id<MTLTexture> texture;
@property NSUInteger level,slice,loadAction,storeAction;
@end
@implementation FakeAttachment @end
@interface MTLRenderPassDescriptor:NSObject
@property FakeAttachment* depthAttachment;
+(instancetype)renderPassDescriptor;
@end
@implementation MTLRenderPassDescriptor
+(instancetype)renderPassDescriptor{auto* descriptor=[self new];descriptor.depthAttachment=[FakeAttachment new];return descriptor;}
@end
@protocol MTLRenderCommandEncoder <NSObject>
-(void)setRenderPipelineState:(id)state;
-(void)setDepthStencilState:(id)state;
-(void)setFragmentTexture:(id<MTLTexture>)texture atIndex:(NSUInteger)index;
-(void)drawPrimitives:(NSUInteger)primitive vertexStart:(NSUInteger)first vertexCount:(NSUInteger)count;
-(void)endEncoding;
@end
@interface FakeEncoder:NSObject<MTLRenderCommandEncoder>@end
@implementation FakeEncoder
-(void)setRenderPipelineState:(id)state{}
-(void)setDepthStencilState:(id)state{}
-(void)setFragmentTexture:(id<MTLTexture>)texture atIndex:(NSUInteger)index{}
-(void)drawPrimitives:(NSUInteger)primitive vertexStart:(NSUInteger)first vertexCount:(NSUInteger)count{draws++;}
-(void)endEncoding{ended++;}
@end
@interface FakeCommand:NSObject
-(id<MTLRenderCommandEncoder>)renderCommandEncoderWithDescriptor:(MTLRenderPassDescriptor*)descriptor;
@end
@implementation FakeCommand
-(id<MTLRenderCommandEncoder>)renderCommandEncoderWithDescriptor:(MTLRenderPassDescriptor*)descriptor{return [FakeEncoder new];}
@end
struct Texture{
 explicit Texture(uint32_t){}~Texture();
 NSUInteger format=0;bool isDepth=false,bcSrgb=false,proxyDirty=true;
 uint32_t dim=2,width=7,height=3,depthOrLayers=2,mips=3,samples=1;
 uint64_t gpuBytes=0,bcGameBytes=0,lastUse=0;int bcKind=0;
 id<MTLTexture> tex=nil;Texture* depthProxy=nullptr;
 std::map<uint64_t,id<MTLTexture>> views;
 std::map<uint64_t,std::vector<uint8_t>> compressedShadow;
};
struct{std::atomic<int64_t> gpuBytes{0},bcGameBytes{0},bcGpuBytes{0},shadowBytes{0},kindBytes[8][2];
 std::atomic<uint64_t> createFailures{0};}gTextureStats;
struct Renderer{FakeDevice* device=[FakeDevice new];uint64_t serial=17;
 std::map<uint64_t,id> dssCache;}renderer;
static Renderer* R=&renderer;static id depthCopyPipe=nil;
static void endEncoders(){}
static FakeCommand* commandBuffer(){return [FakeCommand new];}
static void logOnce(const char*,const char*,...){}
''' + destructor + refresh + r'''
static void checkSuccess(NSUInteger actual,uint64_t expected){
 allocationBytes=actual;unsigned initialAllocations=allocations,initialDraws=draws;
 auto* source=new Texture(1);source->tex=[FakeTexture new];
 refreshDepthProxy(source);
 assert(allocations==initialAllocations+1&&draws==initialDraws+6);
 assert(source->depthProxy->gpuBytes==expected&&gTextureStats.gpuBytes==expected);
 assert(!source->proxyDirty&&source->lastUse==17);
 refreshDepthProxy(source);assert(allocations==initialAllocations+1&&draws==initialDraws+6);
 source->proxyDirty=true;refreshDepthProxy(source);
 assert(draws==initialDraws+12&&gTextureStats.gpuBytes==expected);
 delete source;assert(gTextureStats.gpuBytes==0);
}
int main(){@autoreleasepool{
 checkSuccess(4096,4096);checkSuccess(0,200); // rectangular mip/layer estimate
 failAllocation=true;auto* source=new Texture(1);source->tex=[FakeTexture new];
 unsigned before=allocations,drawsBefore=draws;
 refreshDepthProxy(source);refreshDepthProxy(source);
 assert(allocations==before+1&&gTextureStats.createFailures==1);
 assert(source->depthProxy&&!source->depthProxy->tex&&source->depthProxy->gpuBytes==0);
 assert(gTextureStats.gpuBytes==0&&draws==drawsBefore&&source->proxyDirty);
 delete source;assert(gTextureStats.gpuBytes==0&&gTextureStats.createFailures==1);
 assert(ended==draws);return 0;
}}
'''
        self.compile_run(fixture, objc=True)

    def test_actual_pressure_trim_keeps_live_slots_and_rematerializes_stale_constants(self):
        source = SOURCE.read_text()
        internal = (APP / "Source/MetalRenderer/MRInternal.h").read_text()
        present = span(source, "static void present(uint32_t texId)", "// ---- object creation")
        trim_call = "trimCompletedFrameRing(next, R->completed.load(std::memory_order_acquire), tn)"
        self.assertLess(present.index("waitSerial(next.lastSerial)"), present.index("next.reset()"))
        self.assertLess(present.index("next.reset()"), present.index(trim_call))
        self.assertLess(present.index("trimIdleBufferCaches(tn)"), present.index(trim_call))
        self.assertLess(present.index(trim_call), present.index("performanceSampler.record"))
        commit = span(source, "static void commit(CommitReason", "static void waitSerial")
        self.assertLess(commit.index("for (auto &f : *callbacks) f()"),
                        commit.index("r->completed.compare_exchange_weak"))
        table = span(source, "class ObjectTable {", "// ---- per-frame ring")
        ring = span(source, "struct FrameRing {", "struct Pipe {")
        buffer = span(internal, "struct Buffer : Object {", "struct Shader : Object {")
        allocation = span(source, "static Alloc frameAlloc(", "// ---- engine memory")
        constants = span(source, "static Alloc constantBuffer(", "// ---- views")
        self.compile_run(r'''
#import <Foundation/Foundation.h>
#include <algorithm>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <memory>
#include <unordered_set>
#include <vector>
#include "MRBufferArena.h"
@protocol MTLBuffer <NSObject>
@property(readonly) NSUInteger length;
@property(readonly) void* contents;
@end
static unsigned liveStorage=0;
@interface FakeBuffer:NSObject<MTLBuffer>{NSMutableData* _data;}
-(instancetype)initWithLength:(NSUInteger)bytes;
@end
@implementation FakeBuffer
-(instancetype)initWithLength:(NSUInteger)bytes{self=[super init];if(self){_data=[NSMutableData dataWithLength:bytes];liveStorage++;}return self;}
-(NSUInteger)length{return _data.length;}
-(void*)contents{return _data.mutableBytes;}
-(void)dealloc{liveStorage--;}
@end
enum {MTLResourceStorageModeShared=0};
@interface FakeDevice:NSObject
-(id<MTLBuffer>)newBufferWithLength:(NSUInteger)bytes options:(NSUInteger)options;
@end
@implementation FakeDevice
-(id<MTLBuffer>)newBufferWithLength:(NSUInteger)bytes options:(NSUInteger)options{return [[FakeBuffer alloc]initWithLength:bytes];}
@end
enum ObjKind { OBuffer, OOther };
struct Object {ObjKind kind;uint32_t oid;Object(ObjKind kind,uint32_t oid):kind(kind),oid(oid){}virtual ~Object(){} };
''' + buffer + r'''
Buffer::~Buffer(){}
''' + table + ring + r'''
struct Renderer {ObjectTable objs;FrameRing frames[3];uint64_t frame=6;FakeDevice* device=[FakeDevice new];}renderer;
static Renderer* R=&renderer;static constexpr unsigned FRAME_SLOTS=3;
static bool bufferCachePressure=false;
static std::atomic<bool> memoryTrimRequested{false};
static void logOnce(const char*,const char*,...){}
''' + allocation + constants + r'''
static void fill(FrameRing& frame,unsigned count){
 for(unsigned i=0;i<count;i++)frame.chunks.push_back([R->device newBufferWithLength:FrameRing::CHUNK options:0]);
}
int main(){@autoreleasepool{
 FrameRing& selected=R->frames[0];FrameRing& other=R->frames[1];
 fill(selected,6);fill(other,6);assert(liveStorage==12);
 selected.chunk=0;selected.off=64;selected.lastSerial=6;selected.reset();
 other.chunk=0;other.off=64;other.lastSerial=12;other.reset();
 auto* stale=new Buffer(1);stale->shadow.assign(64,0x5a);stale->cbFrame=3;stale->cbBuf=selected.chunks[4];stale->cbOff=128;stale->cbCap=64;R->objs.set(1,stale);
 auto* liveOther=new Buffer(2);liveOther->cbFrame=4;liveOther->cbBuf=other.chunks[5];liveOther->cbOff=128;liveOther->cbCap=64;R->objs.set(2,liveOther);
 auto* current=new Buffer(3);current->cbFrame=6;current->cbBuf=selected.chunks[5];current->cbOff=128;current->cbCap=64;R->objs.set(3,current);
 __weak id<MTLBuffer> discarded=selected.chunks[4],protectedCurrent=selected.chunks[5],protectedOther=other.chunks[5];
 // Modern/nonpressure path keeps exact allocation identities and strong cache refs.
 assert(trimCompletedFrameRing(selected,9,2000)==0&&selected.chunks.size()==6&&liveStorage==12);
 assert(stale->cbFrame==3&&stale->cbOff==128&&stale->cbCap==64&&stale->cbBuf==discarded);
 bufferCachePressure=true;
 assert(trimCompletedFrameRing(selected,5,2000)==0&&selected.chunks.size()==6); // in-flight serial
 assert(trimCompletedFrameRing(other,9,2000)==0&&other.chunks.size()==6&&protectedOther);
 assert(trimCompletedFrameRing(selected,9,2000)==4*FrameRing::CHUNK);
 assert(selected.chunks.size()==2&&!discarded&&protectedCurrent&&protectedOther);
 assert(!stale->cbBuf&&stale->cbFrame==UINT64_MAX&&stale->cbOff==0&&stale->cbCap==0);
 assert(stale->shadow.size()==64&&stale->shadow[0]==0x5a); // CPU data survives
 assert(current->cbFrame==6&&current->cbBuf==protectedCurrent&&liveOther->cbBuf==protectedOther);
 assert(liveStorage==9); // three resources actually freed; current strong ref is deliberately protected
 // Bound references from the current frame are not invalidated or reused.
 auto cached=constantBuffer(current,64);assert(cached.buf==protectedCurrent&&cached.off==128);
 // A stale materialization is rebuilt from its surviving shadow in the active ring slot.
 auto fresh=constantBuffer(stale,64);assert(fresh.buf==selected.chunks[0]&&stale->cbFrame==6);
 assert(std::memcmp((uint8_t*)fresh.buf.contents+fresh.off,stale->shadow.data(),64)==0);
 auto repeated=constantBuffer(stale,64);assert(repeated.buf==fresh.buf&&repeated.off==fresh.off);
 fill(selected,2);
 assert(trimCompletedFrameRing(selected,9,4000)==0); // no trimming once slot starts allocating
 selected.reset();
 assert(trimCompletedFrameRing(selected,9,2500)==0); // at most one trim per slot/second
 assert(trimCompletedFrameRing(selected,9,3001)==2*FrameRing::CHUNK&&selected.chunks.size()==2);
 // High observed demand is retained together with a spare, even under pressure.
 fill(selected,4);selected.chunk=4;selected.off=16;selected.reset();
 assert(trimCompletedFrameRing(selected,9,5000)==0&&selected.chunks.size()==6);
 R->objs.erase(1);R->objs.erase(2);R->objs.erase(3);
 selected.chunks.clear();other.chunks.clear();fresh.buf=nil;repeated.buf=nil;cached.buf=nil;
 assert(liveStorage==0);return 0;
}}
''', objc=True)


if __name__ == "__main__":
    unittest.main()
