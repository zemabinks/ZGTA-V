#include "ZemaLanBackend.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <time.h>
static unsigned char* bytes;
static unsigned char* retired;
static unsigned char* memory(void* i,uint64_t* size){(void)i;*size=14*1024*1024;return bytes;}
static uint32_t create(void* i,uint64_t s,uint32_t p,uint32_t n,uint32_t b,uint32_t f){(void)i;(void)s;(void)p;(void)n;(void)b;(void)f;retired=bytes;bytes=malloc(14*1024*1024);assert(bytes);memcpy(bytes,retired,14*1024*1024);return 17;}
static uint32_t profiler(void* i,uint64_t a,uint64_t b,uint32_t c){(void)i;(void)a;(void)b;(void)c;return 1;}
static uint32_t select_fn(void* i,uint32_t c,uint64_t r,uint64_t w,uint64_t e,uint64_t t){(void)i;(void)c;(void)r;(void)w;(void)e;(void)t;abort();}
int main(void){bytes=calloc(1,14*1024*1024);assert(bytes);uint32_t state=5;memcpy(bytes+13347088,&state,4);const ZemaLanHost host={.version=1,.memory=memory,.create=create,.profiler=profiler,.select=select_fn};assert(ZemaLanInstallHost(&host,sizeof host));assert(ZemaLanCreateSocket(NULL,100,6672,0,0,0)==17);memcpy(&state,bytes+13347088,4);assert(state==5);memcpy(&state,retired+13347088,4);assert(state==2);assert(ZemaLanConfigure(0x0a4d0001,9));ZemaLanConnected(1);uint16_t port=6672;memcpy(bytes+100+188,&port,2);assert(ZemaLanBind(NULL,100));uint64_t fdset=2,seconds=0;uint32_t micros=50000;memcpy(bytes+1000,&fdset,8);memcpy(bytes+1200,&seconds,8);memcpy(bytes+1208,&micros,4);struct timespec before,after;clock_gettime(CLOCK_MONOTONIC,&before);assert(ZemaLanSelect(NULL,2,1000,0,0,1200)==0);clock_gettime(CLOCK_MONOTONIC,&after);double elapsed=(after.tv_sec-before.tv_sec)+(after.tv_nsec-before.tv_nsec)/1e9;assert(elapsed>=0.02&&elapsed<2.0);free(bytes);free(retired);puts("SOCKET_MEMORY_RELOCATION_SAFE_PASS");return 0;}
