/* Actual Rust socket API plus the extracted production NativeShutdown callback. */
#include "ZemaLanBackend.h"
#include <assert.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static unsigned char bytes[14*1024*1024];
typedef void w2c_game;typedef uint64_t u64;
static pthread_mutex_t engine_lock=PTHREAD_MUTEX_INITIALIZER;
static unsigned locks,unlocks;
void w2c_game_f111(w2c_game* i,u64 at){(void)i;assert(at==160||at==672);pthread_mutex_lock(&engine_lock);locks++;}
void w2c_game_f113(w2c_game* i,u64 at){(void)i;assert(at==160||at==672);unlocks++;pthread_mutex_unlock(&engine_lock);}
/* PRODUCTION_CLOSE_CALLBACK */
static unsigned char* memory(void* i,uint64_t* size){(void)i;*size=sizeof bytes;return bytes;}
static uint32_t create(void* i,uint64_t s,uint32_t p,uint32_t n,uint32_t b,uint32_t f){(void)i;(void)s;(void)p;(void)n;(void)b;(void)f;return 1;}
static uint32_t profiler(void* i,uint64_t a,uint64_t b,uint32_t c){(void)i;(void)a;(void)b;(void)c;return 1;}
static uint32_t native_select(void* i,uint32_t c,uint64_t r,uint64_t w,uint64_t e,uint64_t t){(void)i;(void)c;(void)r;(void)w;(void)e;(void)t;abort();}
static uint64_t get64(size_t at){uint64_t value;memcpy(&value,bytes+at,8);return value;}
static void put64(size_t at,uint64_t value){memcpy(bytes+at,&value,8);}
static uint64_t bind_socket(size_t at,uint16_t port){memcpy(bytes+at+188,&port,2);assert(ZemaLanBind(NULL,at));return get64(at+8);}
static void packet(uint16_t port){unsigned char frame[]={71,53,1,3,10,77,0,1,26,16,10,77,0,2,0,0,42};frame[14]=port>>8;frame[15]=port;assert(ZemaLanDeliver(frame,sizeof frame));}
static void* close_later(void* at){struct timespec pause={0,30000000};nanosleep(&pause,NULL);close_socket(NULL,(uintptr_t)at);return NULL;}
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
int main(void){
 const ZemaLanHost host={.version=1,.memory=memory,.create=create,.profiler=profiler,.select=native_select};
 assert(ZemaLanInstallHost(&host,sizeof host));assert(ZemaLanConfigure(0x0a4d0002,9));ZemaLanConnected(1);
 for(unsigned i=0;i<4096;i++){uint64_t h=bind_socket(128,0);assert(h>0&&h<1024);close_socket(NULL,128);assert(get64(136)==UINT64_MAX);close_socket(NULL,128);}
 uint64_t one=bind_socket(128,6672),shared=bind_socket(640,6672);assert(one!=shared);packet(6672);
 /* Rebind during resume is idempotent, preserving queued data and the handle. */
 assert(ZemaLanBind(NULL,128)&&get64(136)==one);uint16_t requested=0;memcpy(bytes+316,&requested,2);
 assert(ZemaLanBind(NULL,128)&&get64(136)==one);requested=7788;memcpy(bytes+316,&requested,2);assert(!ZemaLanBind(NULL,128)&&get64(136)==one);
 close_socket(NULL,128);assert(get64(136)==UINT64_MAX);
 /* A closed alias may not consume the queue owned by the surviving handle. */
 assert(ZemaLanReceive(NULL,128,0,5000,32,0)==0);assert(ZemaLanReceive(NULL,640,0,5000,32,0)==1);
 packet(6672);close_socket(NULL,640);one=bind_socket(128,6672);assert(ZemaLanReceive(NULL,128,0,5000,32,0)==0);
 ZemaLanConnected(0);assert(get64(136)==one);assert(!ZemaLanBind(NULL,128));ZemaLanConnected(1);assert(ZemaLanBind(NULL,128)&&get64(136)==one);packet(6672);assert(ZemaLanReceive(NULL,128,0,5000,32,0)==1);
 /* Closing the selected handle must wake an unlimited select with EBADF. */
 memset(bytes+3000,0,128);put64(3000+(one/64)*8,1ull<<(one%64));pthread_t thread;
 assert(!pthread_create(&thread,NULL,close_later,(void*)128));double started=now();
 assert(ZemaLanSelect(NULL,1024,3000,0,0,0)==UINT32_MAX);assert(now()-started<2);pthread_join(thread,NULL);
 /* More than32 historical ports do not exhaust the live port budget. */
 for(uint16_t port=1000;port<1100;port++){bind_socket(128,port);close_socket(NULL,128);}
 assert(locks==unlocks);assert(ZemaLanClose(NULL,UINT64_MAX)==0);
 puts("NATIVE_SOCKET_LIFECYCLE_PASS");return 0;
}
