"""Actual buffer create/upload/copy/readback paths with a CPU Metal test double."""
from pathlib import Path
import subprocess
import tempfile
import unittest

APP=Path(__file__).resolve().parents[2]/'app'

def span(text,start,end):return text[text.index(start):text.index(end)]

class MetalBufferArena(unittest.TestCase):
    def test_completion_safe_coalescing_and_many_live_small_buffers(self):
        with tempfile.TemporaryDirectory(prefix='zema-buffer-arena-') as d:
            binary=Path(d)/'fixture'
            result=subprocess.run(['/usr/bin/clang++','-std=c++17','-Wall','-Wextra','-Werror',
                str(APP/'Tests/buffer_arena.cpp'),'-o',str(binary)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            subprocess.run([str(binary)],check=True,capture_output=True,text=True,timeout=30)

    def test_actual_buffer_paths_keep_subranges_separate(self):
        source=(APP/'Source/MetalRenderer/MRRenderer.mm').read_text()
        internal=(APP/'Source/MetalRenderer/MRInternal.h').read_text()
        buffer=span(internal,'struct Buffer : Object {','struct Shader : Object {')
        globals=span(source,'static Renderer *R;','// ---- debug trace')
        allocation=span(source,'static id<MTLBuffer> sharedBuffer(','// A constant buffer\'s current contents')
        copy=span(source,'static void copyRegion(const uint32_t *p) {','\tif (so->kind != OTexture || dobj->kind != OTexture) return;')+'}\n'
        readback=span(source,'static void readback(const uint32_t *p) {','\tif (o->kind != OTexture) { done(); return; }')+'}\n'
        bindings=span(source,'\tuint64_t avail[16] = {};','\tMTLPrimitiveType type = primitiveType(R->topo);')
        indexed=span(source,'\t\t[R->pass drawIndexedPrimitives:type indexCount:dCount','\n\telse [R->pass drawPrimitives:')
        indirect=span(source,'\tif (kind >= 4) {','\t// D3D11 reads zeros past the end of a vertex/index buffer;')
        fixture=r'''
#import <Foundation/Foundation.h>
#include <algorithm>
#include <atomic>
#include <cassert>
#include <cstring>
#include <functional>
#include <map>
#include <string>
#include <vector>
#include "MRBufferArena.h"
#include "MRBufferPool.h"
#include "MRProgress.h"
static unsigned deviceAllocations=0;
@protocol MTLBuffer <NSObject>
@property(readonly) void* contents;
@property(readonly) NSUInteger length;
@end
@interface FakeBuffer:NSObject<MTLBuffer>{NSMutableData* _data;}
-(instancetype)initWithLength:(NSUInteger)bytes;
@end
@implementation FakeBuffer
-(instancetype)initWithLength:(NSUInteger)bytes{self=[super init];if(self)_data=[NSMutableData dataWithLength:bytes];return self;}
-(void*)contents{return _data.mutableBytes;}-(NSUInteger)length{return _data.length;}
@end
@interface FakeDevice:NSObject
@property(readonly) NSUInteger maxBufferLength;
-(id<MTLBuffer>)newBufferWithLength:(NSUInteger)length options:(NSUInteger)options;
@end
@implementation FakeDevice
-(NSUInteger)maxBufferLength{return 1u<<30;}
-(id<MTLBuffer>)newBufferWithLength:(NSUInteger)length options:(NSUInteger)options{++deviceAllocations;return [[FakeBuffer alloc]initWithLength:length];}
@end
@interface FakeBlit:NSObject
-(void)copyFromBuffer:(id<MTLBuffer>)src sourceOffset:(NSUInteger)from toBuffer:(id<MTLBuffer>)dst destinationOffset:(NSUInteger)to size:(NSUInteger)bytes;
@end
@implementation FakeBlit
-(void)copyFromBuffer:(id<MTLBuffer>)src sourceOffset:(NSUInteger)from toBuffer:(id<MTLBuffer>)dst destinationOffset:(NSUInteger)to size:(NSUInteger)bytes{
 assert(from+bytes<=src.length&&to+bytes<=dst.length);
 memmove((uint8_t*)dst.contents+to,(uint8_t*)src.contents+from,bytes);
}
@end
static NSUInteger vertexOffset=0,indexOffset=0,argumentOffset=0;
@interface FakePass:NSObject
-(void)drawIndexedPrimitives:(NSUInteger)type indexCount:(NSUInteger)count indexType:(NSUInteger)indexType indexBuffer:(id<MTLBuffer>)buf indexBufferOffset:(NSUInteger)offset instanceCount:(NSUInteger)instances baseVertex:(NSInteger)base baseInstance:(NSUInteger)first;
-(void)drawIndexedPrimitives:(NSUInteger)type indexType:(NSUInteger)indexType indexBuffer:(id<MTLBuffer>)buf indexBufferOffset:(NSUInteger)offset indirectBuffer:(id<MTLBuffer>)args indirectBufferOffset:(NSUInteger)argOffset;
-(void)drawPrimitives:(NSUInteger)type indirectBuffer:(id<MTLBuffer>)args indirectBufferOffset:(NSUInteger)argOffset;
@end
@implementation FakePass
-(void)drawIndexedPrimitives:(NSUInteger)type indexCount:(NSUInteger)count indexType:(NSUInteger)indexType indexBuffer:(id<MTLBuffer>)buf indexBufferOffset:(NSUInteger)offset instanceCount:(NSUInteger)instances baseVertex:(NSInteger)base baseInstance:(NSUInteger)first{indexOffset=offset;}
-(void)drawIndexedPrimitives:(NSUInteger)type indexType:(NSUInteger)indexType indexBuffer:(id<MTLBuffer>)buf indexBufferOffset:(NSUInteger)offset indirectBuffer:(id<MTLBuffer>)args indirectBufferOffset:(NSUInteger)argOffset{indexOffset=offset;argumentOffset=argOffset;}
-(void)drawPrimitives:(NSUInteger)type indirectBuffer:(id<MTLBuffer>)args indirectBufferOffset:(NSUInteger)argOffset{argumentOffset=argOffset;}
@end
enum ObjKind{OBuffer};struct Object{ObjKind kind;uint32_t oid;Object(ObjKind kind,uint32_t id):kind(kind),oid(id){}virtual ~Object(){}};
'''+buffer+r'''
struct Objects{std::map<uint32_t,Buffer*> items;
 void set(uint32_t id,Buffer* b){auto& old=items[id];delete old;old=b;}
 Object* get(uint32_t id){auto it=items.find(id);return it==items.end()?nullptr:it->second;}
 void erase(uint32_t id){auto it=items.find(id);if(it!=items.end()){delete it->second;items.erase(it);}}
};
struct Renderer{FakeDevice* device;FakePass* pass;id<MTLBuffer> zeroBuffer;Objects objs;std::atomic<uint64_t> completed{0};uint64_t serial=1,frame=1,skipped=0,draws=0;uint8_t* mem;uint64_t memSize;std::vector<std::function<void()>> onComplete;
 struct VB{uint32_t buf,stride,offset;}vb[16];struct IB{uint32_t buf,fmt,offset;}ib;
};
'''+globals+r'''
enum {MTLResourceStorageModeShared=0,BIND_VB=1,BIND_IB=2,BIND_CB=4,BIND_SRV=8,BIND_UAV=128};
enum {MTLIndexTypeUInt16=0,MTLIndexTypeUInt32=1,kVertexBufferTop=30};
static void logOnce(const std::string&,const char*,...){}
static Buffer* buffer(uint32_t id){return static_cast<Buffer*>(R->objs.get(id));}
struct Alloc{id<MTLBuffer> buf;NSUInteger off;uint8_t* ptr;};
static Alloc frameAlloc(NSUInteger bytes,NSUInteger){id<MTLBuffer> b=[R->device newBufferWithLength:bytes+256 options:0];return {b,256,(uint8_t*)b.contents+256};}
static bool inFlight(uint64_t serial){return serial>R->completed.load();}
static FakeBlit* blitEncoder(){static FakeBlit* b=[FakeBlit new];return b;}
static void storeWord(uint64_t addr,uint32_t value){memcpy(R->mem+addr,&value,4);}
static const int CReadback=0;
static void commit(int){for(auto& f:R->onComplete)f();R->onComplete.clear();R->completed=R->serial++;}
static void setBuffer(int,id<MTLBuffer>,NSUInteger offset,int){vertexOffset=offset;}
'''+allocation+copy+readback+r'''
static void checkBindings(){
 bool foldV=false,foldI=false,indexed=true;uint32_t start=0,startInstance=0;int32_t baseVertex=0;
 struct Layout{std::vector<std::pair<uint32_t,uint32_t>> slots;}layout;layout.slots.push_back({0,0});auto* lay=&layout;
 R->vb[0]={2,32,12};
'''+bindings+r'''
 assert(vertexOffset==buffer(2)->offset()+12&&avail[0]==buffer(2)->bytes-12);
}
static void checkIndexed(){
 uint32_t type=0,dCount=4,isz=2,start=3,dInst=1,iFirst=0;bool foldV=false;int32_t baseVertex=0;auto* ib=buffer(2);R->ib.offset=4;
'''+indexed+r'''
 assert(indexOffset==ib->offset()+4+6);
}
static void drawIndirect(){uint32_t kind=4,type=0,words[3]={4,2,8};const uint32_t* p=words;
'''+indirect+r'''
}
int main(){@autoreleasepool{
 Renderer renderer;R=&renderer;R->device=[FakeDevice new];R->pass=[FakePass new];uint8_t output[1024]={};R->mem=output;R->memSize=sizeof output;
 uint32_t desc[5]={1,312,2,0,0};createBuffer(desc);desc[0]=2;desc[1]=7272;desc[2]=1;createBuffer(desc);
 auto* a=buffer(1);auto* b=buffer(2);assert(a->buf==b->buf&&a->offset()!=b->offset());assert(deviceAllocations==1);
 uint32_t upload[7]={1,4,16,11,22,33,44};uploadBuffer(upload,false);
 assert(((uint32_t*)(a->contents()+4))[0]==11&&*(uint32_t*)b->contents()==0);
 uint32_t cp[14]={2,0,8,0,0,1,0,1,4,0,0,20,0,0};copyRegion(cp);
 assert(((uint32_t*)(b->contents()+8))[0]==11&&a->lastUse==1&&b->lastUse==1);
 // The old bytes remain untouched while an in-flight buffer is renamed.
 auto old=b->storage;upload[0]=2;upload[1]=12;upload[3]=99;uploadBuffer(upload,false);
 assert(b->offset()!=old.offset);assert(((uint32_t*)((uint8_t*)old.resource.contents+old.offset+12))[0]==22);
 assert(((uint32_t*)(b->contents()+8))[0]==11&&((uint32_t*)(b->contents()+12))[0]==99);
 uint32_t rd[17]={2,0,1,8,0,0,24,0,0,16,0,0,0,1,16,100,0};readback(rd);
 assert(*(uint32_t*)(output+16)==11&&*(uint32_t*)(output+20)==99);
 assert(b->lastUse==1&&R->completed==1); // readback pins its source through commit
 checkBindings();checkIndexed();R->ib={2,57,4};drawIndirect();
 assert(indexOffset==b->offset()+4&&argumentOffset==b->offset()+8);
 R->completed=R->serial; // the draw fixture's simulated GPU has finished
 R->objs.erase(1);R->objs.erase(2);bufferArena.collect(R->completed);
 // Same zeroed logical object semantics when a region is reused.
 desc[0]=3;desc[1]=312;desc[2]=2;createBuffer(desc);assert(*(uint32_t*)(buffer(3)->contents()+4)==0);R->objs.erase(3);
 unsigned before=deviceAllocations;
 for(unsigned i=0;i<40000;i++){desc[0]=100+i;desc[1]=i%2?7272:312;desc[2]=i%2?1:2;createBuffer(desc);}
 fprintf(stderr,"small-buffer requests=40000 device-allocations=%u\n",deviceAllocations-before);
 assert(deviceAllocations-before<100);
 for(unsigned i=0;i<40000;i++)R->objs.erase(100+i);bufferArena.collect(R->completed);
 assert(bufferArena.activeRanges()==0&&bufferArena.backingSlabs()==1);
}}
'''
        with tempfile.TemporaryDirectory(prefix='zema-arena-paths-') as d:
            path=Path(d);(path/'fixture.mm').write_text(fixture)
            compiled=subprocess.run(['/usr/bin/clang++','-std=c++17','-fobjc-arc','-framework','Foundation',
                '-I',str(APP/'Source/MetalRenderer'),str(path/'fixture.mm'),'-o',str(path/'fixture')],capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            result=subprocess.run([str(path/'fixture')],capture_output=True,text=True,timeout=90)
            self.metrics=result.stderr.strip()
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
