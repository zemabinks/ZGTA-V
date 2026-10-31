#pragma once
#include <cstddef>
#include <cstdint>
#include <utility>
#include <vector>

inline uint32_t PGMetalBufferBytes(uint32_t size,uint64_t deviceLimit) {
 uint64_t rounded=(uint64_t(size)+3)&~uint64_t(3);
 if (rounded<4) rounded=4;
 return rounded<=deviceLimit&&rounded<=UINT32_MAX?uint32_t(rounded):0;
}

// Renderer-thread only. Completion callbacks publish a serial; they never
// mutate this pool. Exact sizes avoid changing view lengths or binding offsets.
template<class Resource> class PGSharedBufferPool {
 struct Entry { Resource resource; uint64_t bytes, lastUse; };
 std::vector<Entry> entries;
 uint64_t held = 0;
 const uint64_t maxBytes;
 const size_t maxEntries;
public:
 uint64_t hits = 0, misses = 0;
 explicit PGSharedBufferPool(uint64_t bytes = 32ull << 20, size_t count = 128)
 : maxBytes(bytes), maxEntries(count) { entries.reserve(count); }
 void retire(Resource resource, uint64_t bytes, uint64_t lastUse) {
  if (!resource || !bytes || bytes > maxBytes || held > maxBytes - bytes || entries.size() >= maxEntries) return;
  entries.push_back({std::move(resource), bytes, lastUse}); held += bytes;
 }
 Resource acquire(uint64_t bytes, uint64_t completed) {
  for (size_t i = 0; i < entries.size(); ++i) {
   if (entries[i].bytes != bytes || entries[i].lastUse > completed) continue;
   Resource resource = std::move(entries[i].resource); held -= bytes;
   if (i + 1 != entries.size()) entries[i] = std::move(entries.back());
   entries.pop_back(); ++hits; return resource;
  }
  ++misses; return {};
 }
 uint64_t bytes() const { return held; }
 // Never discard an entry whose last GPU use has not completed. A warning can
 // trim idle storage without waiting, resetting the device or touching live data.
 uint64_t trim(uint64_t completed, uint64_t keepBytes) {
  uint64_t released=0;
  for(size_t i=0;i<entries.size()&&held>keepBytes;){
   if(entries[i].lastUse>completed){++i;continue;}
   const auto bytes=entries[i].bytes;held-=bytes;released+=bytes;
   if(i+1!=entries.size())entries[i]=std::move(entries.back());
   entries.pop_back();
  }
  return released;
 }
 size_t count() const { return entries.size(); }
};
