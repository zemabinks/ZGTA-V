/* Synthetic engine memory only; calls production Rust socket hooks. */
#include "../ZemaLanBackend.h"
#include "ZemaLanFixture.h"
#include <string.h>
#include <stdatomic.h>
static _Alignas(8) uint8_t bytes[14*1024*1024];
static atomic_int ready=0;
static uint8_t* memory(void* i,uint64_t* size){(void)i;*size=sizeof bytes;return bytes;}
static uint32_t create(void* i,uint64_t s,uint32_t p,uint32_t n,uint32_t b,uint32_t f){(void)i;(void)s;(void)p;(void)n;(void)b;(void)f;return 1;}
static uint32_t profiler(void* i,uint64_t p,uint64_t n,uint32_t f){(void)i;(void)p;(void)n;(void)f;return 1;}
static uint32_t select_socket(void* i,uint32_t c,uint64_t r,uint64_t w,uint64_t e,uint64_t t){(void)i;(void)c;(void)r;(void)w;(void)e;(void)t;return 1;}
int FixtureInstall(void){
  const ZemaLanHost host={.version=1,.memory=memory,.create=create,.profiler=profiler,.select=select_socket};
  if(!ZemaLanInstallHost(&host,sizeof host))return 0;
  uint16_t port=6672;memcpy(bytes+128+188,&port,2);
  int result=ZemaLanNetworkUp(bytes)&&ZemaLanBind(bytes,128);atomic_store_explicit(&ready,result,memory_order_release);return result;
}
int FixtureSend(void){
  uint32_t destination=0xffffffff;uint16_t port=6672;
  memcpy(bytes+1024,&destination,4);memcpy(bytes+1044,&port,2);
  const uint8_t prefix[]={0,255,128,66};const char* text="native-to-browser";
  memcpy(bytes+2048,prefix,4);memcpy(bytes+2052,text,strlen(text));
  return ZemaLanSend(bytes,128,1024,2048,(uint32_t)strlen(text)+4,1100);
}
int FixtureReceived(void){
  if(!atomic_load_explicit(&ready,memory_order_acquire))return 0;
  uint32_t n=ZemaLanReceive(bytes,128,1200,4096,256,1100);
  const char* text="browser-to-native";
  const uint8_t prefix[]={0,254,129,67};
  return n==strlen(text)+4&&!memcmp(bytes+4096,prefix,4)&&!memcmp(bytes+4100,text,strlen(text));
}
