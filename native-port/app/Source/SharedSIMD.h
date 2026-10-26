#pragma once
#include "wasm-rt.h"
#include <simde/wasm/simd128.h>
#include <stdatomic.h>
#ifndef WASM_RT_SIMD_TYPE_DEFINED
#define WASM_RT_SIMD_TYPE_DEFINED
typedef simde_v128_t v128;
#endif
#include "NativeARM64Memory.h"

// Ordinary Wasm SIMD accesses may tear and need not be 16-byte aligned. The
// ARM64 helpers preserve that contract without ordinary C accesses to shared
// storage. Other targets use relaxed atomic bytes. Actual atomics are unchanged.
static inline v128 v128_load_shared(uint8_t *base, uint64_t size,
                                    wasm_rt_shared_memory_t *memory, uint64_t at) {
  if (at > memory->size || memory->size - at < 16) wasm_rt_trap(WASM_RT_TRAP_OOB);
#if PG_PLAIN_SHARED
  return simde_wasm_v128_load((const void *)(uintptr_t)(memory->data + at));
#elif defined(PG_HAS_ARM64_SHARED_VECTORS) && !defined(PG_SHARED_SIMD_BYTEWISE)
  return pg_arm64_load128(memory->data+at);
#else
  uint8_t bytes[16];
  for (int i = 0; i < 16; i++) bytes[i] = atomic_load_explicit(memory->data + at + i, memory_order_relaxed);
  return simde_wasm_v128_load(bytes);
#endif
}
static inline void v128_store_shared(uint8_t *base, uint64_t size,
                                     wasm_rt_shared_memory_t *memory, uint64_t at, v128 value) {
  if (at > memory->size || memory->size - at < 16) wasm_rt_trap(WASM_RT_TRAP_OOB);
#if PG_PLAIN_SHARED
  simde_wasm_v128_store((void *)(uintptr_t)(memory->data + at), value);
#elif defined(PG_HAS_ARM64_SHARED_VECTORS) && !defined(PG_SHARED_SIMD_BYTEWISE)
  pg_arm64_store128(memory->data+at,value);
#else
  uint8_t bytes[16];
  simde_wasm_v128_store(bytes, value);
  for (int i = 0; i < 16; i++) atomic_store_explicit(memory->data + at + i, bytes[i], memory_order_relaxed);
#endif
}

#if defined(PG_HAS_ARM64_SHARED_VECTORS) && !defined(PG_SHARED_SIMD_BYTEWISE)
#define PG_SHARED_READ8(memory, at, bytes) pg_arm64_load64((memory)->data+(at),bytes)
#else
#define PG_SHARED_READ8(memory, at, bytes) \
  for (int i = 0; i < 8; i++) bytes[i] = atomic_load_explicit((memory)->data + (at) + i, memory_order_relaxed)
#endif
#define PG_SHARED_EXTENDING_LOAD(name, operation) \
static inline v128 name(uint8_t *base, uint64_t size, wasm_rt_shared_memory_t *memory, uint64_t at) { \
  if (at > memory->size || memory->size - at < 8) wasm_rt_trap(WASM_RT_TRAP_OOB); \
  uint8_t bytes[8]; \
  PG_SHARED_READ8(memory, at, bytes); \
  return operation(bytes); \
}
PG_SHARED_EXTENDING_LOAD(i32x4_load16x4_shared, simde_wasm_i32x4_load16x4)
PG_SHARED_EXTENDING_LOAD(u32x4_load16x4_shared, simde_wasm_u32x4_load16x4)
PG_SHARED_EXTENDING_LOAD(i64x2_load32x2_shared, simde_wasm_i64x2_load32x2)
#undef PG_SHARED_READ8
