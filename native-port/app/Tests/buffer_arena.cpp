#include "../Source/MetalRenderer/MRBufferArena.h"
#include <cassert>
#include <memory>
#include <vector>
struct Storage {unsigned id;explicit Storage(unsigned id):id(id){}};
int main(){
 using Resource=std::shared_ptr<Storage>;using Arena=PGBufferArena<Resource>;
 Arena arena;unsigned created=0;auto create=[&](uint32_t bytes){assert(bytes==4u<<20);return std::make_shared<Storage>(++created);};
 assert(PGUseBufferArena(312,2,0)&&PGUseBufferArena(7272,1,0));
 assert(!PGUseBufferArena(7272,1|8,0)&&!PGUseBufferArena(7272,1,16));
 assert(!PGUseBufferArena(1u<<20,1,0)&&!PGUseBufferArena(4,4,0));
 auto a=arena.acquire(312,0,create);auto b=arena.acquire(7272,0,create);
 assert(a.resource==b.resource&&a.offset!=b.offset&&a.offset%256==0&&b.offset%256==0);
 assert(a.bytes>=312&&b.bytes>=7272&&created==1);
 assert(arena.activeBytes()==a.bytes+b.bytes&&arena.activeRequestedBytes()==312+7272);
 assert(arena.pendingAllocationBytes()==0);
 assert(arena.reusableBytes()+arena.activeBytes()==Arena::SlabBytes);
 arena.retire(a,10);arena.retire(b,4);arena.collect(5);
 assert(arena.activeRanges()==0&&arena.pendingRanges()==1);
 assert(arena.activeBytes()==0&&arena.activeRequestedBytes()==0&&arena.pendingAllocationBytes()==a.bytes);
 assert(arena.reusableBytes()+arena.pendingAllocationBytes()==Arena::SlabBytes);
 auto c=arena.acquire(312,5,create);assert(c.offset!=a.offset);
 arena.retire(c,6);arena.collect(10);assert(arena.pendingRanges()==0);
 // Coalescing recovers an entire slab after mixed-order ranges retire.
 auto whole=arena.acquire(Arena::SlabBytes,10,create);assert(whole.offset==0&&created==1);
 arena.retire(whole,11);arena.collect(11);
 std::vector<Arena::Allocation> live;
 for(unsigned i=0;i<40000;i++)live.push_back(arena.acquire(i%2?7272:312,11,create));
 assert(created<100&&arena.activeRanges()==40000);
 // Free in a non-sequential order, with some submissions still in flight.
 for(size_t i=0;i<live.size();i+=2)arena.retire(live[i],20);
 for(size_t i=1;i<live.size();i+=2)arena.retire(live[i],30);
 arena.collect(25);assert(arena.pendingRanges()==20000);
 assert(arena.activeRanges()==0);arena.collect(30);assert(arena.pendingRanges()==0&&arena.backingSlabs()==1);
 assert(arena.createdSlabs()==created);
 assert(arena.activeBytes()==0&&arena.activeRequestedBytes()==0&&arena.pendingAllocationBytes()==0);
 assert(arena.reusableBytes()==Arena::SlabBytes);
 Arena failed;assert(!failed.acquire(312,0,[](uint32_t){return Resource{};}));assert(failed.backingSlabs()==0);
 assert(!failed.acquire(Arena::SlabBytes+1,0,create));
}
