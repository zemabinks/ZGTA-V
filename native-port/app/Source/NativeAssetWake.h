#pragma once
#include <pthread.h>
#include <stdint.h>
#include <stdbool.h>
#include <errno.h>
#include <time.h>

// Native asset workers have different consumers of one engine doorbell. A
// separate generation broadcasts its notifications without changing WASM's
// notify(count) semantics or letting the hint worker consume a demand wake.
typedef struct {
 pthread_mutex_t mutex;
 pthread_cond_t condition;
 uint64_t generation;
} PGAssetWake;
#define PG_ASSET_WAKE_INITIALIZER {PTHREAD_MUTEX_INITIALIZER,PTHREAD_COND_INITIALIZER,0}

static inline uint64_t pg_asset_wake_snapshot(PGAssetWake *wake){
 pthread_mutex_lock(&wake->mutex);uint64_t generation=wake->generation;
 pthread_mutex_unlock(&wake->mutex);return generation;
}
static inline void pg_asset_wake_signal(void *context){
 PGAssetWake *wake=context;pthread_mutex_lock(&wake->mutex);
 wake->generation++;pthread_cond_broadcast(&wake->condition);
 pthread_mutex_unlock(&wake->mutex);
}
// The snapshot must precede the consumer's scan. An enqueue/completion between
// that scan and this wait changes generation and returns without sleeping.
// All waits stay bounded so pressure recovery and shutdown cannot depend on a
// notification from an engine that has stopped issuing new work.
static inline bool pg_asset_wake_wait(PGAssetWake *wake,uint64_t seen,uint64_t timeoutNS){
 struct timespec deadline;clock_gettime(CLOCK_MONOTONIC,&deadline);
 deadline.tv_sec+=(time_t)(timeoutNS/1000000000);
 deadline.tv_nsec+=(long)(timeoutNS%1000000000);
 if(deadline.tv_nsec>=1000000000){deadline.tv_sec++;deadline.tv_nsec-=1000000000;}
 pthread_mutex_lock(&wake->mutex);int result=0;
 while(wake->generation==seen&&!result){
  struct timespec now,remaining;clock_gettime(CLOCK_MONOTONIC,&now);
  remaining.tv_sec=deadline.tv_sec-now.tv_sec;remaining.tv_nsec=deadline.tv_nsec-now.tv_nsec;
  if(remaining.tv_nsec<0){remaining.tv_sec--;remaining.tv_nsec+=1000000000;}
  if(remaining.tv_sec<0)break;
#ifdef __APPLE__
  result=pthread_cond_timedwait_relative_np(&wake->condition,&wake->mutex,&remaining);
#else
  // Non-Apple test hosts use a realtime deadline for the relative remainder.
  struct timespec absolute;clock_gettime(CLOCK_REALTIME,&absolute);
  absolute.tv_sec+=remaining.tv_sec;absolute.tv_nsec+=remaining.tv_nsec;
  if(absolute.tv_nsec>=1000000000){absolute.tv_sec++;absolute.tv_nsec-=1000000000;}
  result=pthread_cond_timedwait(&wake->condition,&wake->mutex,&absolute);
#endif
 }
 bool changed=wake->generation!=seen;pthread_mutex_unlock(&wake->mutex);return changed;
}
