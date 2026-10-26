#include "probe.h"
#include "NativeRuntime.h"
#include "wasm-rt-impl.h"
#include "wasm-rt-exceptions.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>

struct w2c_env { wasm_rt_shared_memory_t memory; };
wasm_rt_shared_memory_t *w2c_env_memory(struct w2c_env *e) { return &e->memory; }
static struct w2c_env env;
static _Atomic int finished;
static int recordedTrap;
void pg_record_trap(int code){recordedTrap=code;}

static void pauseBriefly(void) { struct timespec t = {0, 1000000}; nanosleep(&t, NULL); }
static void *waiter(void *unused) {
  wasm_rt_init_thread();
  w2c_probe probe;
  wasm2c_probe_instantiate(&probe, &env);
  assert(w2c_probe_wait32(&probe, 0, 7, (u64)-1) == 0);
  atomic_fetch_add(&finished, 1);
  wasm2c_probe_free(&probe);
  wasm_rt_free_thread();
  return NULL;
}

int main(void) {
  alarm(10);
  wasm_rt_init();
  wasm_rt_allocate_memory_shared(&env.memory, 1, 3, true, 65536);
  w2c_probe probe;
  wasm2c_probe_instantiate(&probe, &env);
  atomic_store((_Atomic uint32_t *)(void *)env.memory.data, 7);
  assert(w2c_probe_wait32(&probe, 0, 8, 0) == 1);
  assert(w2c_probe_wait32(&probe, 0, 7, 0) == 2);
  assert(w2c_probe_wait32(&probe, 0, 7, 1000000) == 2);
  assert(w2c_probe_wait64(&probe, 8, 1, 0) == 1);
  assert(w2c_probe_wait64(&probe, 8, 0, 0) == 2);
  w2c_probe_writeVector(&probe, 33, 0x12345678);
  assert(w2c_probe_readVector(&probe, 33) == 0x12345678);
  for(unsigned offset=0;offset<128;offset++){
    uint32_t value=0xcafebabeu+offset;
    w2c_probe_writeVector(&probe, 256+offset, value);
    assert(w2c_probe_readVector(&probe, 256+offset)==value);
  }
  pthread_t threads[3];
  for (int i = 0; i < 3; i++) pthread_create(threads + i, NULL, waiter, NULL);
  unsigned notified = 0;
  while (notified < 2) {
    notified += w2c_probe_notify(&probe, 0, 2 - notified);
    pauseBriefly();
  }
  while (atomic_load(&finished) < 2) pauseBriefly();
  assert(atomic_load(&finished) == 2);
  unsigned last = 0;
  while (!last) { last = w2c_probe_notify(&probe, 0, 1); pauseBriefly(); }
  assert(last == 1);
  for (int i = 0; i < 3; i++) pthread_join(threads[i], NULL);
  assert(atomic_load(&finished) == 3);
  wasm_rt_trap_t trap = wasm_rt_impl_try();
  if (!trap) { w2c_probe_readVector(&probe, 65528); assert(!"OOB SIMD must trap"); }
  assert(trap == WASM_RT_TRAP_OOB);
  assert(recordedTrap == WASM_RT_TRAP_OOB);
  trap = wasm_rt_impl_try();
  if (!trap) { w2c_probe_wait32(&probe, 1, 7, 0); assert(!"Misaligned wait must trap"); }
  assert(trap == WASM_RT_TRAP_UNALIGNED);
  assert(recordedTrap == WASM_RT_TRAP_UNALIGNED);
  wasm2c_probe_free(&probe);
  wasm_rt_free_memory_shared(&env.memory);
  wasm_rt_free();
  puts("PASS: converted memory64 wait/notify, timeout, partial wake, shared SIMD, and traps");
}
