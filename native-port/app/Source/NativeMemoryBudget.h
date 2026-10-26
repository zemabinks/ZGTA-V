#pragma once
#include <stdint.h>

// Keep a 256 MiB resource-pool growth step plus transient upload headroom.
// The virtual heap capacity is unchanged; this only informs streaming eviction.
// Two thresholds: streaming stops growing `band` bytes above the reserve, and only evicts below
// the reserve itself. One shared threshold made the engine evict and reload the same textures
// whenever memory hovered around it.
static inline uint64_t pg_streaming_headroom_budget(uint64_t engineAvailable,uint64_t processAvailable,uint64_t reserve,uint64_t band){
 uint64_t grow=reserve>UINT64_MAX-band?UINT64_MAX:reserve+band;
 uint64_t available=processAvailable>grow?processAvailable-grow:0;
 return engineAvailable<available?engineAvailable:available;
}

// The resource budget is signed. Below the reserve, a negative answer asks
// the existing streamer to evict that many bytes; zero only stops growth.
static inline int64_t pg_streaming_resource_budget(int64_t engineAvailable,uint64_t processAvailable,uint64_t reserve,uint64_t band){
 uint64_t grow=reserve>UINT64_MAX-band?UINT64_MAX:reserve+band;
 int64_t available;
 if(processAvailable>=grow){
  uint64_t remaining=processAvailable-grow;
  available=remaining>INT64_MAX?INT64_MAX:(int64_t)remaining;
 }else if(processAvailable>=reserve){
  available=0;
 }else{
  uint64_t deficit=reserve-processAvailable;
  available=deficit>INT64_MAX?INT64_MIN:-(int64_t)deficit;
 }
 return engineAvailable<available?engineAvailable:available;
}
