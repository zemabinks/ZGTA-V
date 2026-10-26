#include "../Source/MetalRenderer/MRBufferPool.h"
#include <cassert>
#include <memory>
struct Storage { unsigned value; explicit Storage(unsigned v):value(v) {} };
int main() {
 assert(PGMetalBufferBytes(0,1024)==4&&PGMetalBufferBytes(5,1024)==8);
 assert(PGMetalBufferBytes(1024,1024)==1024&&PGMetalBufferBytes(1025,1024)==0);
 assert(PGMetalBufferBytes(UINT32_MAX,UINT64_MAX)==0);
 assert(PGMetalBufferBytes(UINT32_MAX-3,UINT64_MAX)==UINT32_MAX-3);
 using Resource=std::shared_ptr<Storage>;
 PGSharedBufferPool<Resource> pool(1024, 2);
 auto a=std::make_shared<Storage>(1);auto weak=std::weak_ptr<Storage>(a);
 pool.retire(a,512,9);a.reset();
 assert(!weak.expired());assert(!pool.acquire(512,8)); // GPU still owns old bytes
 assert(!pool.acquire(256,100)); // do not change a binding's storage length
 auto ready=pool.acquire(512,9);assert(ready&&ready->value==1);
 assert(pool.bytes()==0&&pool.count()==0);ready.reset();assert(weak.expired());
 pool.retire(std::make_shared<Storage>(2),512,10);
 pool.retire(std::make_shared<Storage>(3),512,11);
 auto excess=std::make_shared<Storage>(4);auto ew=std::weak_ptr<Storage>(excess);
 pool.retire(excess,4,0);excess.reset();assert(ew.expired());
 assert(pool.bytes()==1024&&pool.count()==2);
 auto exact=pool.acquire(512,10);assert(exact->value==2);
 assert(!pool.acquire(512,10));assert(pool.acquire(512,11)->value==3);
 pool.retire({},4,0);pool.retire(std::make_shared<Storage>(5),2048,0);
 assert(pool.count()==0);
 // A streaming-style create/destroy cycle must not allocate each resource anew.
 unsigned allocations=0;
 for(unsigned serial=1;serial<=50000;serial++) {
  auto resource=pool.acquire(512,serial-1);
  if(!resource){resource=std::make_shared<Storage>(0);allocations++;}
  resource->value=serial;pool.retire(resource,512,serial);
  assert(pool.bytes()<=1024&&pool.count()<=2);
 }
 assert(allocations==1);assert(pool.hits>=49999);
}
