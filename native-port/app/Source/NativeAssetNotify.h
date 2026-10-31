#pragma once
#include "WasmFutex.h"
#include <stdbool.h>

// One process-lifetime, opt-in native asset doorbell observer. It runs after
// the futex lock is released and never changes notify's WASM waiter count.
// Kept outside WasmFutex.h: generated engine units need no new imports or ABI.
bool pg_atomic_observe_notify(wasm_rt_shared_memory_t *, uint64_t,
                             void (*)(void *), void *);
