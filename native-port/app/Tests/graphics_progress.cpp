#include "../Source/MetalRenderer/MRProgress.h"
#include <cassert>
#include <cstring>
#include <thread>
int main(){
 PGGraphicsProgress p;char line[384];
 auto initial=p.snapshot();assert(!initial.ringBound&&initial.phase==PGGraphicsProgress::NotStarted);
 PGGraphicsProgress::format(line,sizeof line,initial,1000000000);assert(strstr(line,"presentAgeMs=-1"));
 std::atomic<uint32_t> ring[2]={{4096},{1024}};p.bindRing(ring);p.executing(7,1536);p.submitted(21);p.completed(19);p.presented(1000000000);
 p.phase(PGGraphicsProgress::NextDrawable);auto drawable=p.snapshot();
 assert(drawable.phase==PGGraphicsProgress::NextDrawable&&drawable.operation==7&&drawable.cursor==1536);
 assert(drawable.head==4096&&drawable.tail==1024&&drawable.ringBound);
 p.waiting(20);auto blocked=p.snapshot();assert(blocked.waitTarget==20&&blocked.phase==PGGraphicsProgress::WaitSerial);
 PGGraphicsProgress::format(line,sizeof line,blocked,3000000000);
 assert(strstr(line,"phase=waitSerial op=7"));assert(strstr(line,"submitted=21 completed=19 waitSerial=20 presentAgeMs=2000"));
 // Completion callbacks may arrive out of order; published completion never regresses.
 std::thread first([&]{for(uint64_t i=20;i<=10000;i++)p.completed(i);});
 std::thread second([&]{for(uint64_t i=20;i<=12000;i++)p.completed(i);});
 uint64_t last=19;for(unsigned i=0;i<10000;i++){auto s=p.snapshot();assert(s.completed>=last);last=s.completed;}
 first.join();second.join();assert(p.snapshot().completed==12000);
 p.waited();assert(p.snapshot().waitTarget==0&&p.snapshot().phase==PGGraphicsProgress::Executing);
 ring[0].store(8192);assert(p.snapshot().head==8192); // fresh producer head while consumer is blocked
 p.phase(PGGraphicsProgress::RingIdle);assert(p.snapshot().phase==PGGraphicsProgress::RingIdle);
 char small[9];PGGraphicsProgress::format(small,sizeof small,p.snapshot(),500000000);assert(small[8]=='\0');
 PGGraphicsProgress::format(line,sizeof line,p.snapshot(),500000000);assert(strstr(line,"presentAgeMs=0"));
 p.executing(11,22699888);p.buffer(123,65536,3,16);p.phase(PGGraphicsProgress::BufferAllocate);
 auto allocation=p.snapshot();assert(allocation.bufferId==123&&allocation.bufferBytes==65536&&allocation.bufferBind==3&&allocation.bufferMisc==16);
 PGGraphicsProgress::format(line,sizeof line,allocation,500000000);
 assert(strstr(line,"phase=buffer-allocate op=11")&&strstr(line,"lastBuffer=123/65536 bind=3 misc=16"));
 return 0;
}
