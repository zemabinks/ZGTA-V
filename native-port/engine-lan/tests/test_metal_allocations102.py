"""Actual Metal allocator/constant/counter/readback paths with injected nil storage.

Objective-C fake buffers replace a GPU; the renderer implementation is extracted
unchanged. This tests allocation failure behavior, not graphics correctness/FPS.
"""
from pathlib import Path
import subprocess,tempfile,unittest
APP=Path(__file__).resolve().parents[2]/'app'
SOURCE=APP/'Source/MetalRenderer/MRRenderer.mm'
def span(s,a,b):return s[s.index(a):s.index(b,s.index(a))]
PREFIX=r'''
#import <Foundation/Foundation.h>
#include <algorithm>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <functional>
#include <map>
#include <string>
#include <vector>
@protocol MTLBuffer <NSObject>
@property(readonly) NSUInteger length;
@property(readonly) void* contents;
@end
static bool failAllocation=false,failContents=false;
static unsigned requests=0,blits=0,commits=0,notifications=0;
@interface FakeBuffer:NSObject<MTLBuffer>{NSMutableData* _data;BOOL _missing;}
-(instancetype)initWithLength:(NSUInteger)bytes;
@end
@implementation FakeBuffer
-(instancetype)initWithLength:(NSUInteger)bytes{self=[super init];if(self){_data=[NSMutableData dataWithLength:bytes];_missing=failContents;}return self;}
-(NSUInteger)length{return _data.length;}
-(void*)contents{return _missing?nullptr:_data.mutableBytes;}
@end
enum{MTLResourceStorageModeShared=0};
@interface FakeDevice:NSObject
-(id<MTLBuffer>)newBufferWithLength:(NSUInteger)bytes options:(NSUInteger)options;
@end
@implementation FakeDevice
-(id<MTLBuffer>)newBufferWithLength:(NSUInteger)bytes options:(NSUInteger)options{requests++;return failAllocation?nil:[[FakeBuffer alloc]initWithLength:bytes];}
@end
static std::atomic<bool> memoryTrimRequested{false};
static void logOnce(const char*,const char*,...){}
static void logOnce(const std::string&,const char*,...){}
'''
OBJECTS=r'''
enum{OBuffer,OTexture};
struct Object{int kind;};
struct Buffer:Object{
 uint32_t size=16,bytes=16,cbPad=0,cbCap=0;uint64_t cbFrame=UINT64_MAX,lastUse=0;
 std::vector<uint8_t> shadow;
 id<MTLBuffer> cbBuf=nil,counter=nil,buf=nil;NSUInteger cbOff=0;
 NSUInteger offset(){return 0;}
};
struct Texture:Object{
 uint32_t mips=1,dim=2,samples=1,width=4,height=4,depthOrLayers=1;bool bcNative=false,isDepth=false;
 int bcKind=0;NSUInteger format=0;uint64_t lastUse=0;id tex=nil;
 std::map<uint64_t,std::vector<uint8_t>> compressedShadow;
};
struct Table{Object* current=nullptr;Object* get(uint32_t){return current;}};
struct Renderer{FrameRing frames[3];uint64_t frame=0,serial=7;FakeDevice* device=[FakeDevice new];
 uint8_t* mem=nullptr;uint64_t memSize=0;Table objs;std::vector<std::function<void()>> onComplete;
}renderer;
static Renderer* R=&renderer;static constexpr unsigned FRAME_SLOTS=3;
'''
READBACK=r'''
struct MTLSize{NSUInteger width,height,depth;};
struct MTLOrigin{NSUInteger x,y,z;};
static MTLSize MTLSizeMake(NSUInteger w,NSUInteger h,NSUInteger d){return{w,h,d};}
static MTLOrigin MTLOriginMake(NSUInteger x,NSUInteger y,NSUInteger z){return{x,y,z};}
@interface FakeBlit:NSObject
-(void)copyFromBuffer:(id<MTLBuffer>)source sourceOffset:(NSUInteger)from toBuffer:(id<MTLBuffer>)destination destinationOffset:(NSUInteger)to size:(NSUInteger)size;
-(void)copyFromTexture:(id)source sourceSlice:(NSUInteger)slice sourceLevel:(NSUInteger)mip sourceOrigin:(MTLOrigin)origin sourceSize:(MTLSize)size toBuffer:(id<MTLBuffer>)destination destinationOffset:(NSUInteger)offset destinationBytesPerRow:(NSUInteger)row destinationBytesPerImage:(NSUInteger)image;
@end
@implementation FakeBlit
-(void)copyFromBuffer:(id<MTLBuffer>)source sourceOffset:(NSUInteger)from toBuffer:(id<MTLBuffer>)destination destinationOffset:(NSUInteger)to size:(NSUInteger)size{blits++;memcpy((uint8_t*)destination.contents+to,(uint8_t*)source.contents+from,size);}
-(void)copyFromTexture:(id)source sourceSlice:(NSUInteger)slice sourceLevel:(NSUInteger)mip sourceOrigin:(MTLOrigin)origin sourceSize:(MTLSize)size toBuffer:(id<MTLBuffer>)destination destinationOffset:(NSUInteger)offset destinationBytesPerRow:(NSUInteger)row destinationBytesPerImage:(NSUInteger)image{blits++;memset((uint8_t*)destination.contents+offset,0x3d,image*size.depth);}
@end
static FakeBlit* blitEncoder(){return[FakeBlit new];}
static void storeWord(uint64_t at,uint32_t value){assert(at+4<=R->memSize);memcpy(R->mem+at,&value,4);notifications++;}
static void commit(int){commits++;auto list=std::move(R->onComplete);R->onComplete.clear();for(auto& f:list)f();}
static constexpr int CReadback=1;
static void mipExtent(Texture* t,uint32_t,uint32_t& w,uint32_t& h,uint32_t& d){w=t->width;h=t->height;d=t->depthOrLayers;}
static uint32_t bcBlockBytes(int){return 8;}
static uint32_t bytesPerTexel(NSUInteger){return 4;}
static struct{uint64_t bcReadbacks=0;}gTextureStats;
'''
MAIN=r'''
static void reset(){for(auto& f:R->frames){f.chunks.clear();f.big.clear();f.chunk=f.off=0;}memoryTrimRequested=false;}
int main(int argc,char** argv){@autoreleasepool{
 if(argc==2){
  failAllocation=true;Buffer b;b.shadow.assign(64,0x5a);
  if(!strcmp(argv[1],"constant"))constantBuffer(&b,64);
  else if(!strcmp(argv[1],"counter"))counterOf(&b);
  else {R->frames[0].off=16;auto a=frameAlloc(64,16);memcpy(a.ptr,b.shadow.data(),64);}
  return 0;
 }
 // Failed chunks/oversized staging cannot consume a cursor or poison retry.
 reset();failAllocation=true;auto a=frameAlloc(64,16);assert(!a.buf&&!a.ptr);
 auto& f=R->frames[0];assert(f.chunks.empty()&&f.big.empty()&&f.off==0&&f.chunk==0&&memoryTrimRequested);
 failAllocation=false;a=frameAlloc(64,16);assert(a.buf&&a.ptr&&a.off==0&&f.off==64&&f.chunks.size()==1);
 auto first=a.buf;auto second=frameAlloc(17,256);assert(second.buf==first&&second.off==256&&f.off==273);
 f.off=FrameRing::CHUNK-4;auto oldOff=f.off;failAllocation=true;
 a=frameAlloc(64,16);assert(!a.buf&&f.off==oldOff&&f.chunk==0&&f.chunks.size()==1);
 failAllocation=false;a=frameAlloc(64,16);assert(a.buf&&a.off==0&&f.chunk==1&&f.off==64&&f.chunks.size()==2);
 failAllocation=true;oldOff=f.off;a=frameAlloc(FrameRing::CHUNK,16);assert(!a.buf&&f.big.empty()&&f.off==oldOff);
 failAllocation=false;a=frameAlloc(FrameRing::CHUNK,16);assert(a.buf&&a.off==0&&f.big.size()==1&&f.off==oldOff);
 reset();failContents=true;a=frameAlloc(32,16);assert(!a.buf&&f.chunks.empty()&&f.off==0);failContents=false;
 // Constants publish cache identity/capacity only after successful materialization.
 reset();Buffer b;b.shadow.assign(64,0x5a);failAllocation=true;
 auto c=constantBuffer(&b,96);assert(!c.buf&&b.cbFrame==UINT64_MAX&&b.cbPad==0&&b.cbCap==0&&!b.cbBuf);
 failAllocation=false;c=constantBuffer(&b,96);assert(c.buf&&b.cbFrame==R->frame&&b.cbCap==96);
 auto* bytes=(uint8_t*)c.buf.contents+c.off;for(unsigned i=0;i<96;i++)assert(bytes[i]==(i<64?0x5a:0));
 auto capOff=f.off;auto repeated=constantBuffer(&b,96);assert(repeated.buf==c.buf&&repeated.off==c.off&&f.off==capOff);
 Buffer counter;failAllocation=true;assert(!counterOf(&counter)&&!counter.counter);
 failAllocation=false;auto counted=counterOf(&counter);assert(counted&&counterOf(&counter)==counted);
 for(unsigned i=0;i<16;i++)assert(((uint8_t*)counted.contents)[i]==0);
 // Every GPU-backed readback failure signals once, leaves destination intact,
 // queues no null-pointer callback and encodes no invalid blit. A retry works.
 static uint8_t memory[8192];R->mem=memory;R->memSize=sizeof memory;
 for(unsigned mode=0;mode<3;mode++){
  reset();Buffer buffer;buffer.kind=OBuffer;buffer.buf=[R->device newBufferWithLength:16 options:0];memset(buffer.buf.contents,0x3d,16);
  Texture texture;texture.kind=OTexture;texture.tex=[NSObject new];texture.bcNative=mode==1;
  R->objs.current=mode==0?(Object*)&buffer:(Object*)&texture;
  uint32_t p[17]={};p[0]=1;p[9]=1024;p[11]=16;p[12]=64;p[13]=mode==0;p[14]=16;p[15]=32;
  memset(memory,0xaa,sizeof memory);notifications=blits=commits=0;R->onComplete.clear();failAllocation=true;
  readback(p);assert(notifications==1&&!blits&&!commits&&R->onComplete.empty());
  for(unsigned i=1024;i<1088;i++)assert(memory[i]==0xaa);
  uint32_t flag;memcpy(&flag,memory+32,4);assert(flag==0);
  failAllocation=false;notifications=blits=commits=0;readback(p);
  assert(notifications==1&&blits==1&&commits==1&&R->onComplete.empty()&&memory[1024]==0x3d);
 }
 puts("METAL_ALLOCATION_FAILURE102_PASS");return 0;
}}
'''

def fixture(source):
 return (PREFIX+span(source,'struct FrameRing {','struct Pipe {')+OBJECTS+
         span(source,'static Alloc frameAlloc(','// ---- engine memory')+
         span(source,'static Alloc constantBuffer(','// Called only for the just-reset')+
         span(source,'static id<MTLBuffer> counterOf(Buffer *b) {','static void setUavCounter(')+
         READBACK+span(source,'static void readback(const uint32_t *p) {','// ---- present')+MAIN)

def compile_fixture(folder,source):
 path=folder/'fixture.mm';path.write_text(fixture(source))
 result=subprocess.run(['/usr/bin/clang++','-std=c++17','-fobjc-arc','-framework','Foundation','-fsanitize=address,undefined','-fno-omit-frame-pointer',path,'-o',folder/'check'],capture_output=True,text=True)
 if result.returncode:raise AssertionError(result.stderr)
 return folder/'check'

class MetalAllocations102(unittest.TestCase):
 def test_actual_failure_retry_constants_counters_and_readback(self):
  with tempfile.TemporaryDirectory(prefix='zgta-metal-alloc102-') as temp:
   exe=compile_fixture(Path(temp),SOURCE.read_text())
   result=subprocess.run([exe],capture_output=True,text=True,timeout=30)
   self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
   self.assertIn('METAL_ALLOCATION_FAILURE102_PASS',result.stdout)
 def test_all_frame_alloc_callers_and_bind_results_guarded(self):
  source=SOURCE.read_text()
  import re
  calls=list(re.finditer(r'Alloc a = frameAlloc\([^;]+;',source))
  self.assertEqual(len(calls),10)
  for call in calls:self.assertRegex(source[call.end():call.end()+130],r'^\s*if \(!a.buf\)')
  readback=span(source,'static void readback(','// ---- present')
  self.assertEqual(readback.count('if (!a.buf) { done(); return; }'),3)
  self.assertIn('if (!bindStage(0, vs->info) || (ps && !bindStage(1, ps->info)))',source)
  self.assertIn('if (!bindStage(2, info)) return;',source)

if __name__=='__main__':unittest.main()
