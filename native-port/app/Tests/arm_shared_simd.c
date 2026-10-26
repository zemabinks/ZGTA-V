#include "SharedSIMD.h"
#include "NativeARM64Memory.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

void wasm_rt_trap(wasm_rt_trap_t trap) { fprintf(stderr,"Unexpected SIMD trap: %d\n",trap);abort(); }
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static unsigned char storage[4096];
static wasm_rt_shared_memory_t memory;
static simde_v128_t checkedNativeLoad(uint64_t at){
 if(at>memory.size||memory.size-at<16)wasm_rt_trap(WASM_RT_TRAP_OOB);
 return pg_arm64_load128(memory.data+at);
}
static void checkedNativeStore(uint64_t at,simde_v128_t value){
 if(at>memory.size||memory.size-at<16)wasm_rt_trap(WASM_RT_TRAP_OOB);
 pg_arm64_store128(memory.data+at,value);
}
static double copyBenchmark(int native,unsigned iterations){
 double start=now();
 for(unsigned i=0;i<iterations;i++){
  uint64_t at=(i&63)*17;
  simde_v128_t value=native?checkedNativeLoad(at):v128_load_shared(NULL,0,&memory,at);
  if(native)checkedNativeStore(2048+at,value);else v128_store_shared(NULL,0,&memory,2048+at,value);
 }
 return (now()-start)*1000;
}
int main(void){
 memory.data=(_Atomic volatile uint8_t *)storage;memory.size=sizeof storage;
 for(unsigned i=0;i<sizeof storage;i++)storage[i]=(unsigned char)(i*79+13);
 for(unsigned at=0;at<128;at++){
  unsigned char expected[16],actual[16],small[8];
  simde_wasm_v128_store(expected,v128_load_shared(NULL,0,&memory,at));
  simde_wasm_v128_store(actual,pg_arm64_load128(memory.data+at));
  assert(!memcmp(expected,actual,16));
  pg_arm64_load64(memory.data+at,small);assert(!memcmp(expected,small,8));
  pg_arm64_store128(memory.data+2048+at,simde_wasm_v128_load(actual));
  for(unsigned j=0;j<16;j++)assert(atomic_load(memory.data+2048+at+j)==actual[j]);
 }
 for(unsigned trial=0;trial<3;trial++){
  double scalar=copyBenchmark(0,2000000),native=copyBenchmark(1,2000000);
  printf("Shared SIMD copy trial %u: bytewise %.2f ms, ARM64 %.2f ms, ratio %.2fx\n",trial,scalar,native,scalar/native);
 }
 puts("PASS: ARM64 shared vector reads/writes and 64-bit reads at 128 unaligned offsets");
 return 0;
}
