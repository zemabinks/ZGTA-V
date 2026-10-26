#pragma once
#include <simde/wasm/simd128.h>
#include <stdatomic.h>
#include <stdint.h>
#include <string.h>

#if defined(__aarch64__) && defined(SIMDE_ARM_NEON_A32V7_NATIVE)
// Wasm's ordinary vector accesses may tear. These instructions access shared
// bytes outside C's non-atomic access rules; the compiler memory clobber keeps
// them ordered with the surrounding runtime operations. Bounds checks belong
// to the caller. Actual Wasm atomic instructions continue using C11 atomics.
// https://webassembly.github.io/threads/core/exec/relaxed.html
#define PG_HAS_ARM64_SHARED_VECTORS 1
static inline simde_v128_t pg_arm64_load128(const _Atomic volatile uint8_t *address) {
 simde_v128_t value;
 __asm__ volatile("ldr %q0, [%1]" : "=w"(value) : "r"(address) : "memory");
 return value;
}
static inline void pg_arm64_store128(_Atomic volatile uint8_t *address,simde_v128_t value) {
 __asm__ volatile("str %q0, [%1]" : : "w"(value),"r"(address) : "memory");
}
static inline void pg_arm64_load64(const _Atomic volatile uint8_t *address,uint8_t bytes[8]) {
 uint64_t value;
 __asm__ volatile("ldr %0, [%1]" : "=r"(value) : "r"(address) : "memory");
 memcpy(bytes,&value,8);
}
#endif
