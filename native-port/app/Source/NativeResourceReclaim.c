#include "NativeResourceReclaim.h"
#include "NativePageReclaim.h"
#include <sys/mman.h>
#include <unistd.h>
#include <string.h>
#include <stdio.h>
extern void pg_log(const char *);
static PGPageReclaim resourcePages;
static _Atomic bool reclaimPressure;
static bool reclaimReady;
static _Atomic bool releaseLogged;
#define RESOURCE_HEAP 8043728ull
static int resource_advice(void *unused,void *at,size_t size,bool reuse){
 (void)unused;
#if defined(__APPLE__)
 return madvise(at,size,reuse?MADV_FREE_REUSE:MADV_FREE_REUSABLE);
#else
 (void)at;(void)size;(void)reuse;return -1;
#endif
}
void pg_resource_reclaim_init(void *base,uint64_t capacity){
 const char *disabled=getenv("ZGTA_DISABLE_RESOURCE_RECLAIM");
 if(disabled&&strcmp(disabled,"1")==0)return;
 long page=sysconf(_SC_PAGESIZE);if(page<=0)return;
 reclaimReady=pg_pages_init(&resourcePages,base,capacity,(uint64_t)page,resource_advice,NULL);
 pg_log(reclaimReady?"Native resource page reclamation ready; limited to freed overflow blocks under memory pressure.":"Native resource page reclamation unavailable; existing allocator retained.");
}
void pg_resource_reclaim_pressure(bool pressure){atomic_store(&reclaimPressure,pressure);}
bool pg_resource_reclaim_wants(uint64_t heap,uint64_t at){return reclaimReady&&heap==RESOURCE_HEAP&&at&&atomic_load(&reclaimPressure);}
bool pg_resource_reclaim_has_pages(uint64_t heap){return reclaimReady&&heap==RESOURCE_HEAP&&atomic_load(&resourcePages.pending)>0;}
static bool range(uint64_t at,uint64_t n,uint64_t limit){return at&&at<=limit&&n<=limit-at;}
static uint64_t read64(uint64_t at){uint64_t v;memcpy(&v,resourcePages.base+at,8);return v;}
void pg_resource_reclaim_free(uint64_t heap,uint64_t at,uint64_t size,uint64_t limit){
 if(limit>resourcePages.capacity||!pg_resource_reclaim_wants(heap,at)||!range(heap,16640,limit)||!range(at,size,limit)||!size)return;
 uint32_t count;memcpy(&count,resourcePages.base+heap+508,4);if(count<2||count>32)return;
 /* Retain the first segment, and retain every live block. Unlike upstream's
  * fixed gameResourceMB, this port keeps its existing dynamic headroom policy. */
 for(uint32_t i=1;i<count;i++){
  uint64_t base=read64(heap+16384+i*8),length=read64(heap+512+i*488+24);
  if(!range(base,length,limit)||!length||at<base||at-base>length||size>length-(at-base))continue;
  if(pg_pages_release(&resourcePages,at,size,limit)&&!atomic_exchange(&releaseLogged,true)){pg_log("Native resource allocator released freed overflow pages to iOS.");}
  return;
 }
}
bool pg_resource_reclaim_reuse(uint64_t heap,uint64_t at,uint64_t size,uint64_t limit){
 if(!reclaimReady||heap!=RESOURCE_HEAP||!at)return true;
 bool ok=pg_pages_reuse(&resourcePages,at,size,limit);
 if(!ok){atomic_store(&reclaimPressure,false);pg_log("Native resource page reuse failed; refusing to hand reclaimed pages to the game.");}
 return ok;
}
uint64_t PGResourceBytesReleased(void){return atomic_load(&resourcePages.released);}
uint64_t PGResourceBytesReused(void){return atomic_load(&resourcePages.reused);}
uint64_t PGResourceReclaimFailures(void){return atomic_load(&resourcePages.failures);}
