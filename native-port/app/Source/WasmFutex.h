#pragma once
#include "wasm-rt.h"
#include <stdint.h>

uint32_t pg_atomic_wait32(wasm_rt_shared_memory_t *, uint64_t, uint32_t, uint64_t);
uint32_t pg_atomic_wait64(wasm_rt_shared_memory_t *, uint64_t, uint64_t, uint64_t);
uint32_t pg_atomic_notify(wasm_rt_shared_memory_t *, uint64_t, uint32_t);
