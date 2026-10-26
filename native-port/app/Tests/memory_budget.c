#include "NativeMemoryBudget.h"
#include "NativeEngineMemory.h"
#include <assert.h>
#include <stdio.h>

int main(void){
 assert(pg_streaming_headroom_budget(1000,2000,384,0)==1000);
 assert(pg_streaming_headroom_budget(1000,600,384,0)==216);
 assert(pg_streaming_headroom_budget(1000,384,384,0)==0);
 assert(pg_streaming_headroom_budget(1000,0,384,0)==0);
 assert(pg_streaming_headroom_budget(0,1000,384,0)==0);
 assert(pg_streaming_headroom_budget(UINT64_MAX,UINT64_MAX,384,0)==UINT64_MAX-384);
 assert(pg_streaming_resource_budget(1000,2000,384,0)==1000);
 assert(pg_streaming_resource_budget(1000,600,384,0)==216);
 assert(pg_streaming_resource_budget(1000,384,384,0)==0);
 assert(pg_streaming_resource_budget(1000,100,384,0)==-284);
 assert(pg_streaming_resource_budget(1000,0,384,0)==-384);
 assert(pg_streaming_resource_budget(-1000,100,384,0)==-1000);
 assert(pg_streaming_resource_budget(0,100,384,0)==-284);
 assert(pg_streaming_resource_budget(INT64_MAX,UINT64_MAX,384,0)==INT64_MAX);
 assert(pg_streaming_resource_budget(INT64_MAX,0,UINT64_MAX,0)==INT64_MIN);
 assert(pg_streaming_resource_budget(INT64_MIN,UINT64_MAX,384,0)==INT64_MIN);
 // The band: growth stops 256 above the reserve, eviction only below the reserve.
 assert(pg_streaming_headroom_budget(1000,2000,384,256)==1000);
 assert(pg_streaming_headroom_budget(1000,800,384,256)==160);
 assert(pg_streaming_headroom_budget(1000,500,384,256)==0);
 assert(pg_streaming_resource_budget(1000,800,384,256)==160);
 assert(pg_streaming_resource_budget(1000,500,384,256)==0);
 assert(pg_streaming_resource_budget(1000,384,384,256)==0);
 assert(pg_streaming_resource_budget(1000,100,384,256)==-284);
 assert(pg_streaming_resource_budget(INT64_MAX,UINT64_MAX,384,UINT64_MAX)==0);

 const uint64_t page=65536,MiB=1048576;
 const unsigned devices[]={3072,4096,6144,8192,12288,16384};
 for(unsigned i=0;i<sizeof devices/sizeof *devices;i++){
  PGEngineMemory m=pg_engine_memory(devices[i]*MiB,page);
  assert(m.maximumPages*page==devices[i]*MiB);
  assert(m.initialPages*page==(devices[i]<3328?devices[i]:3328)*MiB);
  assert(m.maximumPages>=m.initialPages);
 }
 assert(pg_engine_memory(24576*MiB,page).maximumPages*page==PG_ENGINE_MEMORY_MAX_BYTES);
 assert(pg_engine_memory(2048*MiB,page).maximumPages*page==PG_ENGINE_MEMORY_MIN_BYTES);
 assert(pg_engine_memory(0,page).maximumPages*page==PG_ENGINE_MEMORY_MAX_BYTES);
 assert(pg_engine_memory(8192*MiB+123,page).maximumPages*page==8192*MiB);
 assert(pg_engine_memory(UINT64_MAX,page).maximumPages*page==PG_ENGINE_MEMORY_MAX_BYTES);
 assert(pg_engine_memory(8192*MiB,0).maximumPages==0);
 puts("PASS: streaming headroom and resource budget clamps + device memory configuration.");
 return 0;
}
