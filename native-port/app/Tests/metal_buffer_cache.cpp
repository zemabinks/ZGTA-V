#include "PlayGTA5MetalBufferCache.h"
#include <cstdio>
int main(){
 using playgta5::MetalBufferChange;
 playgta5::MetalBufferCache<uintptr_t,30> cache;
 assert(cache.Update(0,1,256)==MetalBufferChange::Bind);
 assert(cache.Update(0,1,512)==MetalBufferChange::Offset);
 assert(cache.Update(0,1,512)==MetalBufferChange::Unchanged);
 assert(cache.Update(0,2,512)==MetalBufferChange::Bind);
 assert(cache.Update(29,1,512)==MetalBufferChange::Bind);
 cache.Clear(); // a different layout's vertex input overwrote a former uniform slot
 assert(cache.Update(0,2,512)==MetalBufferChange::Bind);
 assert(cache.Update(29,1,512)==MetalBufferChange::Bind);
 playgta5::MetalBufferCache<uintptr_t,30> otherStage;
 assert(otherStage.Update(0,2,512)==MetalBufferChange::Bind);
 cache.Clear();assert(cache.Update(0,0,0)==MetalBufferChange::Bind);
 assert(cache.Update(0,0,0)==MetalBufferChange::Unchanged);
 for(size_t i=0;i<30;i++){
   cache.Clear();
   assert(cache.Update(i,i+1,0)==MetalBufferChange::Bind);
   assert(cache.Update(i,i+1,0)==MetalBufferChange::Unchanged);
   assert(cache.Update(i,i+1,1ull<<32)==MetalBufferChange::Offset);
   assert(cache.Update(i,i+2,0)==MetalBufferChange::Bind);
 }
 puts("Metal buffer cache: buffer identity, offsets, unchanged bindings, layout resets, independent stages, 64-bit offsets and all slots passed.");
}
