/* Production native select with synthetic memory and local in-process datagrams only. */
#include "ZemaLanBackend.h"
#include <assert.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <time.h>
static unsigned char memory_bytes[14*1024*1024];
static unsigned char* memory(void* i,uint64_t* n){(void)i;*n=sizeof memory_bytes;return memory_bytes;}
static uint32_t create(void* i,uint64_t s,uint32_t p,uint32_t n,uint32_t b,uint32_t f){(void)i;(void)s;(void)p;(void)n;(void)b;(void)f;return 1;}
static uint32_t profiler(void* i,uint64_t a,uint64_t b,uint32_t c){(void)i;(void)a;(void)b;(void)c;return 1;}
static uint32_t forbidden_select(void* i,uint32_t c,uint64_t r,uint64_t w,uint64_t e,uint64_t t){(void)i;(void)c;(void)r;(void)w;(void)e;(void)t;abort();}
static uint64_t get64(uint64_t at){uint64_t v;memcpy(&v,memory_bytes+at,8);return v;}
static void put64(uint64_t at,uint64_t v){memcpy(memory_bytes+at,&v,8);}
static void set(uint64_t at,uint64_t bits){memset(memory_bytes+at,0,128);put64(at,bits);}
static void timeout(uint64_t sec,uint32_t micro){put64(3600,sec);memcpy(memory_bytes+3608,&micro,4);}
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static void packet(uint16_t port){unsigned char frame[]={71,53,1,3,10,77,0,1,26,16,10,77,0,2,0,0,42};frame[14]=(unsigned char)(port>>8);frame[15]=(unsigned char)port;assert(ZemaLanDeliver(frame,sizeof frame)==1);}
static void* wake(void* mode){struct timespec pause={0,30000000};nanosleep(&pause,NULL);if(mode==(void*)2){unsigned char frame[2048];assert(ZemaLanTakeOutgoing(frame,sizeof frame)>0);}else if(mode)ZemaLanConnected(0);else packet(7788);return NULL;}
int main(void){
  const ZemaLanHost host={.version=1,.memory=memory,.create=create,.profiler=profiler,.select=forbidden_select};
  assert(ZemaLanConfigure(0x0a4d0002,9));ZemaLanConnected(1);assert(ZemaLanInstallHost(&host,sizeof host));
  for(unsigned i=0;i<3;i++){uint16_t port=i==1?7788:6672;uint64_t at=128+i*512;memcpy(memory_bytes+at+188,&port,2);assert(ZemaLanBind(NULL,at));assert(get64(at+8)==i+1);}
  uint32_t destination=0x0a4d0001;uint16_t destination_port=6672;memcpy(memory_bytes+1200,&destination,4);memcpy(memory_bytes+1220,&destination_port,2);memory_bytes[1300]=42;
  for(unsigned n=0;n<256;n++)assert(ZemaLanSend(NULL,128,1200,1300,1,0));assert(!ZemaLanSend(NULL,128,1200,1300,1,0));
  set(3200,2);timeout(0,0);assert(ZemaLanSelect(NULL,4,0,3200,0,3600)==0&&get64(3200)==0);
  assert(ZemaLanTakeOutgoing(NULL,0)<0);set(3200,2);assert(ZemaLanSelect(NULL,4,0,3200,0,3600)==0);
  set(3200,2);timeout(1,0);pthread_t drain;assert(!pthread_create(&drain,NULL,wake,(void*)2));double drain_start=now();assert(ZemaLanSelect(NULL,4,0,3200,0,3600)==1);assert(now()-drain_start>=0.015&&now()-drain_start<2);pthread_join(drain,NULL);assert(get64(3200)==2);
  timeout(0,10000);double start=now();assert(ZemaLanSelect(NULL,0,0,0,0,3600)==0);assert(now()-start>=0.005);
  set(3000,2);timeout(0,30000);start=now();assert(ZemaLanSelect(NULL,4,3000,0,0,3600)==0);assert(now()-start>=0.015&&now()-start<2);assert(get64(3000)==0);
  packet(6672);set(3000,14);set(3200,4);set(3400,14);timeout(0,0);
  assert(ZemaLanSelect(NULL,4,3000,3200,3400,3600)==3);assert(get64(3000)==10&&get64(3200)==4&&get64(3400)==0);
  for(unsigned i=4;i<=70;i++){uint16_t port=6672;uint64_t at=6000+i*512;memcpy(memory_bytes+at+188,&port,2);assert(ZemaLanBind(NULL,at));assert(get64(at+8)==i);}
  set(3000,2);put64(3008,1ull<<6);assert(ZemaLanSelect(NULL,71,3000,0,0,3600)==2);assert(get64(3008)==(1ull<<6));
  /* Reading another port must not wake from an unrelated queued packet. */
  set(3000,4);timeout(1,0);pthread_t t;assert(!pthread_create(&t,NULL,wake,NULL));assert(ZemaLanSelect(NULL,4,3000,0,0,3600)==1);assert(get64(3000)==4);pthread_join(t,NULL);
  /* A handle selected in both sets contributes two bits, as libc select does. */
  set(3000,4);set(3200,4);assert(ZemaLanSelect(NULL,4,3000,3200,0,3600)==2);
  /* Unknown handle and malformed timeout fail without mutating caller sets. */
  set(3000,0);put64(3008,1ull<<36);assert(ZemaLanSelect(NULL,101,3000,0,0,3600)==UINT32_MAX&&get64(3008)==(1ull<<36));
  set(3000,2);timeout(UINT64_MAX,0);assert(ZemaLanSelect(NULL,4,3000,0,0,3600)==UINT32_MAX&&get64(3000)==2);
  timeout(0,1000000);assert(ZemaLanSelect(NULL,4,3000,0,0,3600)==UINT32_MAX);
  assert(ZemaLanSelect(NULL,1025,3000,0,0,0)==UINT32_MAX);
  assert(ZemaLanSelect(NULL,4,sizeof memory_bytes-64,0,0,0)==UINT32_MAX);
  /* Drain both ports, then disconnect wakes an otherwise infinite wait promptly. */
  unsigned char output[32];(void)output;
  assert(ZemaLanReceive(NULL,128,0,5000,32,0)==1);assert(ZemaLanReceive(NULL,640,0,5000,32,0)==1);
  set(3000,2);set(3200,0);assert(!pthread_create(&t,NULL,wake,(void*)1));start=now();assert(ZemaLanSelect(NULL,4,3000,3200,0,0)==0);assert(now()-start<2);pthread_join(t,NULL);assert(get64(3000)==0&&get64(3200)==0);
  puts("NATIVE_VIRTUAL_SELECT_ACTUAL_READINESS_PASS");return 0;
}
