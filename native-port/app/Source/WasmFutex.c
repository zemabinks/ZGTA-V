#include "WasmFutex.h"
#include <pthread.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <errno.h>
#include <time.h>

// One queue shared by all instances of a module's imported shared memory.
// Per-waiter condition variables let notify wake exactly the requested count.
typedef struct Waiter {
  const void *address;
  bool notified;
  pthread_cond_t condition;
  struct Waiter *next;
} Waiter;

static pthread_mutex_t queueLock = PTHREAD_MUTEX_INITIALIZER;
static Waiter *waiters;

static void *checkedAddress(wasm_rt_shared_memory_t *memory, uint64_t offset,
                            uint32_t width) {
  if (offset % width) wasm_rt_trap(WASM_RT_TRAP_UNALIGNED);
  if (offset > memory->size || memory->size - offset < width)
    wasm_rt_trap(WASM_RT_TRAP_OOB);
  return (uint8_t *)(void *)memory->data + offset;
}

static uint32_t waitFor(wasm_rt_shared_memory_t *memory, uint64_t offset,
                        uint64_t expected, uint64_t timeoutBits, uint32_t width) {
  void *address = checkedAddress(memory, offset, width);
  pthread_mutex_lock(&queueLock);
  uint64_t value = width == 4 ? atomic_load((_Atomic uint32_t *)address)
                              : atomic_load((_Atomic uint64_t *)address);
  if (value != expected) {
    pthread_mutex_unlock(&queueLock);
    return 1;
  }
  int64_t timeout = (int64_t)timeoutBits;
  if (!timeout) {
    pthread_mutex_unlock(&queueLock);
    return 2;
  }
  Waiter waiter = {.address = address, .notified = false, .next = waiters};
  pthread_cond_init(&waiter.condition, NULL);
  waiters = &waiter;
  struct timespec deadline;
  if (timeout > 0) {
    clock_gettime(CLOCK_MONOTONIC, &deadline);
    deadline.tv_sec += timeout / 1000000000;
    deadline.tv_nsec += timeout % 1000000000;
    if (deadline.tv_nsec >= 1000000000) {
      deadline.tv_sec++;
      deadline.tv_nsec -= 1000000000;
    }
  }
  int result = 0;
  while (!waiter.notified && !result) {
    if (timeout < 0) {
      result = pthread_cond_wait(&waiter.condition, &queueLock);
    } else {
      // Apple's relative wait uses monotonic time, so wall-clock changes cannot
      // extend or shorten an engine sleep. Recalculate after a spurious wakeup.
      struct timespec now, remaining;
      clock_gettime(CLOCK_MONOTONIC, &now);
      remaining.tv_sec = deadline.tv_sec - now.tv_sec;
      remaining.tv_nsec = deadline.tv_nsec - now.tv_nsec;
      if (remaining.tv_nsec < 0) { remaining.tv_sec--; remaining.tv_nsec += 1000000000; }
      if (remaining.tv_sec < 0) result = ETIMEDOUT;
      else result = pthread_cond_timedwait_relative_np(&waiter.condition, &queueLock, &remaining);
    }
  }
  Waiter **link = &waiters;
  while (*link != &waiter) link = &(*link)->next;
  *link = waiter.next;
  bool notified = waiter.notified;
  pthread_mutex_unlock(&queueLock);
  pthread_cond_destroy(&waiter.condition);
  return notified ? 0 : 2;
}

uint32_t pg_atomic_wait32(wasm_rt_shared_memory_t *m, uint64_t a, uint32_t v,
                           uint64_t timeout) { return waitFor(m, a, v, timeout, 4); }
uint32_t pg_atomic_wait64(wasm_rt_shared_memory_t *m, uint64_t a, uint64_t v,
                           uint64_t timeout) { return waitFor(m, a, v, timeout, 8); }

uint32_t pg_atomic_notify(wasm_rt_shared_memory_t *m, uint64_t offset,
                           uint32_t count) {
  void *address = checkedAddress(m, offset, 4);
  uint32_t total = 0;
  pthread_mutex_lock(&queueLock);
  for (Waiter *w = waiters; w && total < count; w = w->next) {
    if (w->address == address && !w->notified) {
      w->notified = true;
      pthread_cond_signal(&w->condition);
      total++;
    }
  }
  pthread_mutex_unlock(&queueLock);
  return total;
}
