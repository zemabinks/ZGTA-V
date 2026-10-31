#include "../Source/NativePerformanceSampler.h"
#include "../Source/MetalRenderer/MRBufferPool.h"
#include "../Source/MetalRenderer/MRBufferArena.h"
#include <cassert>
#include <memory>
#include <thread>
int main(){
 PGNativePerformanceSampler s;PGNativePerformanceMetrics result{};unsigned sampled=0;
 auto gauges=[&]{++sampled;PGNativePerformanceMetrics v{};v.metalBytes=1234;return v;};
 PGFrameWork work{};work.pipeline=2;work.gpuWait=3;work.uploads=1;work.uploadBytes=4096;
 for(int n=0;n<200;n++)s.record(n*20,20,500,work,gauges);
 assert(sampled==0&&!s.read(&result));
 s.enable(true);assert(!s.read(&result));
 for(int n=0;n<=50;n++)s.record(4000+n*20,20,500,work,gauges);
 assert(s.read(&result)&&result.frames==51&&result.metalBytes==1234);
 assert(result.frameMS==20&&result.pipelineWaitMS==2&&result.gpuFenceWaitMS==3&&result.uploadBytesPerFrame==4096);
 s.enable(false);assert(!s.read(&result));s.enable(true);assert(!s.read(&result));
 for(int n=0;n<=50;n++)s.record(6000+n*20,20,500,work,gauges);
 assert(s.read(&result)&&result.frames==51&&result.timeMS==7000);
 std::thread writer([&]{for(int n=0;n<5000;n++)s.record(8000+n*20,20,500,work,gauges);});
 for(int n=0;n<5000;n++)if(s.read(&result))assert(result.metalBytes==1234&&result.pipelineWaitMS==2);
 writer.join();assert(!s.read(nullptr));
 using Resource=std::shared_ptr<unsigned>;PGSharedBufferPool<Resource> pool(32,8);
 auto pending=std::make_shared<unsigned>(1);std::weak_ptr<unsigned> weak=pending;
 pool.retire(pending,16,20);pending.reset();pool.retire(std::make_shared<unsigned>(2),16,10);
 assert(pool.trim(10,8)==16&&pool.bytes()==16&&!weak.expired());
 assert(pool.trim(19,0)==0&&!weak.expired());assert(pool.trim(20,0)==16&&weak.expired());
 PGBufferArena<Resource> arena;auto a=arena.acquire(512,0,[](uint32_t){return std::make_shared<unsigned>(3);});
 auto live=a.resource;arena.retire(a,10);a={};
 assert(arena.trimEmpty(9)==0&&arena.backingSlabs()==1);
 assert(arena.trimEmpty(10)==arena.SlabBytes&&arena.backingSlabs()==0&&*live==3);
}
