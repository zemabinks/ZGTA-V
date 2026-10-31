#pragma once
#include <array>
#include <cstdint>
#include <memory>
#include <map>
#include <set>
#include <utility>
#include <vector>

inline bool PGUseBufferArena(uint32_t bytes,uint32_t bind,uint32_t misc) {
 return bytes && bytes <= (256u << 10) && (bind & 3) && !(bind & ~3u) && !misc;
}

// Persistent vertex/index storage. A buddy allocator bounds fragmentation and
// coalesces freed ranges. Only the renderer thread mutates it; completed serials
// are sampled from the command queue. Never recycle an in-flight range.
template<class Resource> class PGBufferArena {
public:
 static constexpr uint32_t Unit=256, MaxOrder=14, SlabBytes=Unit<<MaxOrder;
 static constexpr uint32_t NoSlab=UINT32_MAX;
 struct Allocation {
  Resource resource{};
  uint32_t slab=NoSlab,offset=0,bytes=0,order=0,requestedBytes=0;
  explicit operator bool() const { return bool(resource); }
 };
private:
 struct Slab {
  Resource resource;
  std::array<std::set<uint32_t>,MaxOrder+1> free;
  uint32_t live=0;
  explicit Slab(Resource resource):resource(std::move(resource)) { free[MaxOrder].insert(0); }
 };
 std::vector<std::unique_ptr<Slab>> slabs;
 std::multimap<uint64_t,Allocation> retired;
 uint64_t active=0,created=0,liveBytes=0,requested=0,pendingBytes=0;
 static bool take(Slab& slab,uint32_t order,uint32_t& offset) {
  uint32_t found=order;
  while(found<=MaxOrder && slab.free[found].empty()) ++found;
  if(found>MaxOrder)return false;
  auto first=slab.free[found].begin();offset=*first;slab.free[found].erase(first);
  while(found>order){--found;slab.free[found].insert(offset+(Unit<<found));}
  ++slab.live;return true;
 }
 void release(const Allocation& a) {
  Slab& slab=*slabs[a.slab];uint32_t offset=a.offset,order=a.order;
  while(order<MaxOrder){
   uint32_t buddy=offset^(Unit<<order);auto it=slab.free[order].find(buddy);
   if(it==slab.free[order].end())break;
   slab.free[order].erase(it);offset=offset<buddy?offset:buddy;++order;
  }
  slab.free[order].insert(offset);--slab.live;
 }
public:
 void collect(uint64_t completed) {
  bool released=false;
  for(auto it=retired.begin();it!=retired.end()&&it->first<=completed;){
   pendingBytes-=it->second.bytes;release(it->second);it=retired.erase(it);released=true;
  }
  if(!released)return;
  // Keep one empty backing allocation warm; other empty slabs are released.
  bool kept=false;
  for(auto& slab:slabs)if(slab&&!slab->live){if(kept)slab.reset();else kept=true;}
 }
 template<class Create> Allocation acquire(uint32_t bytes,uint64_t completed,Create create) {
  if(!bytes||bytes>SlabBytes)return {};
  collect(completed);uint32_t order=0;
  while((Unit<<order)<bytes)++order;
  uint32_t offset=0,index=0;
  for(;index<slabs.size();++index)
   if(slabs[index]&&take(*slabs[index],order,offset)){++active;liveBytes+=Unit<<order;requested+=bytes;return {slabs[index]->resource,index,offset,Unit<<order,order,bytes};}
  Resource resource=create(SlabBytes);if(!resource)return {};
  auto slab=std::make_unique<Slab>(std::move(resource));take(*slab,order,offset);
  for(index=0;index<slabs.size()&&slabs[index];++index){}
  if(index==slabs.size())slabs.push_back(nullptr);
  slabs[index]=std::move(slab);++active;++created;liveBytes+=Unit<<order;requested+=bytes;
  return {slabs[index]->resource,index,offset,Unit<<order,order,bytes};
 }
 void retire(Allocation allocation,uint64_t serial) {
  if(!allocation||allocation.slab==NoSlab)return;
  liveBytes-=allocation.bytes;requested-=allocation.requestedBytes;pendingBytes+=allocation.bytes;
  retired.emplace(serial,std::move(allocation));--active;
 }
 uint64_t activeRanges() const {return active;}
 uint64_t activeBytes() const {return liveBytes;}
 uint64_t activeRequestedBytes() const {return requested;}
 uint64_t pendingAllocationBytes() const {return pendingBytes;}
 // Holes in occupied slabs are reusable but are not independently releasable.
 uint64_t reusableBytes() const {return backingSlabs()*SlabBytes-liveBytes-pendingBytes;}
 uint64_t trimEmpty(uint64_t completed) {
  collect(completed);uint64_t released=0;
  for(auto& slab:slabs)if(slab&&!slab->live){slab.reset();released+=SlabBytes;}
  return released;
 }
 size_t pendingRanges() const {return retired.size();}
 uint64_t createdSlabs() const {return created;}
 uint64_t backingSlabs() const {uint64_t n=0;for(auto& s:slabs)if(s)++n;return n;}
};
