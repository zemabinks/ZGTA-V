#include "../Source/NativeEngineSafety.h"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#define SIZE (UINT64_C(1)<<25)
static uint8_t *memory;
static void u64(uint64_t at,uint64_t value){memcpy(memory+at,&value,8);}
static void u32(uint64_t at,uint32_t value){memcpy(memory+at,&value,4);}
static void u16(uint64_t at,uint16_t value){memcpy(memory+at,&value,2);}
int main(void){
  memory=calloc(1,SIZE);if(!memory)return 2;
  printf("[");
  printf("%d,",pg_safety_range(SIZE,UINT64_MAX,80));
  printf("%d,",pg_safety_range(SIZE,SIZE-80,80));
  memset(memory+4096,0xdd,80);
  printf("%d,",pg_safety_deleted_entity(memory,SIZE,4096));
  u64(4096+8,0);printf("%d,",pg_safety_deleted_entity(memory,SIZE,4096));
  printf("%d,",pg_safety_deleted_entity(memory,SIZE,UINT64_MAX));
  memset(memory+4096,0,80);memory[4096+40]=4;
  u64(11012104,40000);u16(40000+16906,400);u16(40000+16904,391);
  printf("%d,",pg_safety_draw_budget(memory,SIZE,4096));
  u16(40000+16904,392);printf("%d,",pg_safety_draw_budget(memory,SIZE,4096));
  memory[4096+40]=2;printf("%d,",pg_safety_draw_budget(memory,SIZE,4096));
  memory[4096+40]=3;u16(40000+16906,0);u64(11012152,80000);u32(80000+83808,479);
  printf("%d,",pg_safety_draw_budget(memory,SIZE,4096));
  u32(80000+83808,480);printf("%d,",pg_safety_draw_budget(memory,SIZE,4096));
  u32(80000+83808,UINT32_MAX);printf("%d,",pg_safety_draw_budget(memory,SIZE,4096));
  u64(11012104,UINT64_MAX);u64(11012152,UINT64_MAX);printf("%d,",pg_safety_draw_budget(memory,SIZE,4096));
  u64(11547128,2048);u64(2048,3072);u16(2056,6);
  uint64_t phases[]={5000,5100,0,UINT64_MAX,5100,5200};
  memcpy(memory+3072,phases,sizeof phases);u64(5000,4219921);u64(5100,4219920);u64(5200,4219922);
  pg_safety_drop_destroyed_phases(memory,SIZE);
  printf("%u,",pg_safety_u16(memory,2056));
  for(unsigned i=0;i<6;i++)printf("\"%llu\",",(unsigned long long)pg_safety_u64(memory,3072+i*8));
  uint64_t job=10000;u64(job+96,15);
  printf("%d,",pg_safety_stale_job(memory,SIZE,job,16));
  memory[job+110]=1;u32(job+112,268435456);printf("%d,",pg_safety_stale_job(memory,SIZE,job,16));
  u32(job+112,268435457);printf("%d,",pg_safety_stale_job(memory,SIZE,job,16));
  memory[job+110]=0;printf("%d,",pg_safety_stale_job(memory,SIZE,job,16));
  u64(job+96,16);printf("%d,",pg_safety_stale_job(memory,SIZE,job,16));
  printf("%d,",pg_safety_stale_job(memory,SIZE,UINT64_MAX,16));
  /* Fixtures use slot 14 for a wrong function type and 0 for null. Native
   * production also checks the actual slot's func_type against w2c_game_t4. */
  u64(job+96,14);printf("%d,",pg_safety_stale_job(memory,SIZE,job,16) || pg_safety_u64(memory,job+96)!=15);
  u64(job+96,0);printf("%d,",pg_safety_stale_job(memory,SIZE,job,16) || pg_safety_u64(memory,job+96)!=15);
  float waits[]={0,0.00005f,0.0001f,0.002f,NAN,INFINITY,-1,1,0.99f};
  for(unsigned i=0;i<sizeof waits/sizeof *waits;i++)printf("\"%llu\"%s",(unsigned long long)pg_safety_frame_idle_ns(waits[i]),i+1==sizeof waits/sizeof *waits?"":",");
  puts("]");free(memory);return 0;
}
