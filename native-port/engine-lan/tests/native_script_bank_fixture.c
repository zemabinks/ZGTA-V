/* Typed synthetic originals only; no real game instance or audio/network data. */
#include "ZemaNativeScriptBank.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
static _Thread_local u32 fixture_status=2;
static atomic_uint requests,statuses,notes;
static atomic_bool entered,released;
static const u64 wide_slot=UINT64_C(0xf000000100000080);
void pg_log(const char* line){assert(strstr(line,"failed optional bank"));assert(strstr(line,"audio data remains unavailable"));atomic_fetch_add(&notes,1);}
u32 w2c_game_f7226_zema_script_bank_original(w2c_game* i,u64 slot,u32 bank){assert(i);assert(slot==wide_slot);(void)bank;atomic_fetch_add(&statuses,1);return fixture_status;}
u32 w2c_game_f21855_zema_script_bank_original(w2c_game* i,u32 bank,u32 network,u32 players){
  assert(i&&network==1&&players==17);atomic_fetch_add(&requests,1);
  if(bank==100)return 73; /* Original request result must never be replaced. */
  if(bank==10){assert(w2c_game_f21855(i,11,network,players)==0);assert(w2c_game_f7226(i,wide_slot,bank)==0);}
  if(bank==22){atomic_store(&entered,true);while(!atomic_load(&released)){struct timespec t={0,1000000};nanosleep(&t,NULL);}}
  return w2c_game_f7226(i,wide_slot,bank);
}
static void* worker(void* p){assert(w2c_game_f21855(p,22,1,17)==0);assert(w2c_game_f7226(p,wide_slot,22)==2);return NULL;}
int main(void){
  w2c_game instance={0};
  assert(w2c_game_f7226(&instance,wide_slot,4328)==2);assert(atomic_load(&notes)==0);
  for(u32 value=0;value<8;value++){
    fixture_status=value;assert(w2c_game_f21855(&instance,4328,1,17)==(value==2?0:value));
    assert(w2c_game_f7226(&instance,wide_slot,4328)==value);
  }
  fixture_status=2;assert(w2c_game_f21855(&instance,10,1,17)==0);assert(w2c_game_f7226(&instance,wide_slot,10)==2);
  assert(w2c_game_f21855(&instance,100,1,17)==73);assert(w2c_game_f7226(&instance,wide_slot,100)==2);
  pthread_t thread;assert(!pthread_create(&thread,NULL,worker,&instance));
  while(!atomic_load(&entered)){struct timespec t={0,1000000};nanosleep(&t,NULL);}
  assert(w2c_game_f7226(&instance,wide_slot,22)==2); /* Other thread's request scope is private. */
  atomic_store(&released,true);assert(!pthread_join(thread,NULL));
  assert(w2c_game_f7226(&instance,wide_slot,22)==2);assert(atomic_load(&notes)==1);
  assert(atomic_load(&requests)==12);assert(atomic_load(&statuses)>atomic_load(&requests));
  puts("NATIVE_SCRIPT_BANK_TYPED_TLS_NESTED_ORIGINAL_STATUS_PASS");return 0;
}
