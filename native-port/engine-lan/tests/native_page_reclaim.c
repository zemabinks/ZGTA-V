#include "NativePageReclaim.h"
#include "NativeThreadPolicy.h"
#include <assert.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>

typedef struct {int fail;uint64_t calls,first,last;} Advice;
static int fake_advice(void *ctx,void *at,size_t size,bool reuse){
 Advice *a=ctx;(void)reuse;a->calls++;a->first=(uintptr_t)at;a->last=(uintptr_t)at+size;return a->fail?-1:0;
}
typedef struct {PGPageReclaim *pages;uint64_t at,page,limit;} Worker;
static void *cycle(void *ctx){
 Worker *w=ctx;
 for(int n=0;n<3000;n++){
  assert(pg_pages_release(w->pages,w->at,3*w->page+137,w->limit));
  assert(pg_pages_reuse(w->pages,w->at,3*w->page+137,w->limit));
  memset(w->pages->base+w->at,0x45,(size_t)(3*w->page+137));
 }
 return NULL;
}
static int real_advice(void *ctx,void *at,size_t size,bool reuse){
 (void)ctx;
#if defined(__APPLE__)
 return madvise(at,size,reuse?MADV_FREE_REUSE:MADV_FREE_REUSABLE);
#else
 (void)reuse;return madvise(at,size,MADV_DONTNEED);
#endif
}
int main(void){
 uint64_t page=(uint64_t)sysconf(_SC_PAGESIZE),cap=128*page;
 uint8_t *base=mmap(NULL,(size_t)cap,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0);assert(base!=MAP_FAILED);
 PGPageReclaim s={0};Advice a={0};assert(pg_pages_init(&s,base,cap,page,fake_advice,&a));
 memset(base,0x6a,(size_t)cap);
 assert(pg_pages_release(&s,page+17,3*page,cap));
 assert(a.first==(uintptr_t)base+2*page&&a.last==(uintptr_t)base+4*page);
 assert(atomic_load(&s.pending)==2);
 assert(!pg_pages_release(&s,page+17,3*page,cap));
 assert(pg_pages_reuse(&s,page+17,3*page,cap));assert(!atomic_load(&s.pending));
 assert(base[page+16]==0x6a&&base[4*page+17]==0x6a);
 uint64_t before=a.calls;
 assert(!pg_pages_release(&s,UINT64_MAX-3,100,cap));assert(!pg_pages_release(&s,cap-10,20,cap));
 assert(!pg_pages_release(&s,0,page,cap));assert(!pg_pages_release(&s,page,0,cap));
 assert(!pg_pages_release(&s,page+1,page-1,cap));assert(!pg_pages_release(&s,page,page,cap+page));assert(a.calls==before);
 a.fail=1;assert(!pg_pages_release(&s,10*page,2*page,cap));assert(!atomic_load(&s.pending));
 a.fail=0;assert(pg_pages_release(&s,10*page,2*page,cap));a.fail=1;
 assert(!pg_pages_reuse(&s,10*page,2*page,cap));assert(atomic_load(&s.pending)==2);
 a.fail=0;assert(pg_pages_reuse(&s,10*page,2*page,cap));assert(!atomic_load(&s.pending));assert(atomic_load(&s.failures)==2);
 pthread_t threads[8];Worker work[8];
 for(int i=0;i<8;i++){work[i]=(Worker){&s,(uint64_t)(20+i*10)*page+7,page,cap};assert(!pthread_create(&threads[i],NULL,cycle,&work[i]));}
 for(int i=0;i<8;i++)assert(!pthread_join(threads[i],NULL));
 assert(!atomic_load(&s.pending));assert(atomic_load(&s.released)==atomic_load(&s.reused));pg_pages_destroy(&s);
 PGPageReclaim os={0};assert(pg_pages_init(&os,base,cap,page,real_advice,NULL));
 memset(base,0x6a,(size_t)cap);assert(pg_pages_release(&os,2*page+17,5*page,cap));
 assert(base[3*page-1]==0x6a&&base[7*page]==0x6a);
 assert(pg_pages_reuse(&os,2*page+17,5*page,cap));memset(base+2*page+17,0x32,(size_t)(5*page));
 assert(base[2*page+16]==0x6a&&base[7*page+17]==0x6a);pg_pages_destroy(&os);
 for(uint64_t simulated=4096;simulated<=16384;simulated*=4){
  uint64_t bytes=256*simulated;void *raw=NULL;assert(!posix_memalign(&raw,(size_t)simulated,(size_t)bytes));
  PGPageReclaim model={0};Advice recorded={0};assert(pg_pages_init(&model,raw,bytes,simulated,fake_advice,&recorded));
  assert(pg_pages_release(&model,63*simulated,3*simulated,bytes));assert(atomic_load(&model.pending)==3);
  assert(pg_pages_reuse(&model,64*simulated+3,1,bytes));assert(atomic_load(&model.pending)==2);
  assert(!pg_pages_marked(&model,64)&&pg_pages_marked(&model,63)&&pg_pages_marked(&model,65));
  assert(pg_pages_reuse(&model,63*simulated,3*simulated,bytes));assert(!atomic_load(&model.pending));
  pg_pages_destroy(&model);free(raw);
 }
 char name[49];uint8_t memory[128]={0};strcpy((char *)memory+32,"[GTA] ControlMgr Update Thread");
 assert(pg_engine_thread_name(memory,sizeof memory,8,name)&&pg_engine_frame_control(name));
 assert(!pg_engine_thread_name(memory,60,8,name));assert(!pg_engine_thread_name(memory,sizeof memory,UINT64_MAX,name));
 memset(memory+32,'X',48);assert(!pg_engine_thread_name(memory,sizeof memory,8,name));memory[32]=1;assert(!pg_engine_thread_name(memory,sizeof memory,8,name));
 assert(!pg_engine_frame_control("[GTA] ControlMgr Update Thread extra"));assert(!pg_engine_frame_control("North Audio Update"));assert(!pg_engine_frame_control("[RAGE] RenderThread"));
 assert(!munmap(base,(size_t)cap));puts("PASS: page bounds, advice failures/retry, 24000 concurrent cycles, real OS reclaim/reuse and exact thread policy");return 0;
}
