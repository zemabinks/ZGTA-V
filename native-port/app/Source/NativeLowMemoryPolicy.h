#pragma once
#include <stdint.h>

// Automatic memory management uses physical RAM, independently of graphics presets. Unknown RAM is not a low-memory
// device; never infer a restriction from a temporarily small process allowance.
static inline int pg_low_memory_device(uint64_t physicalBytes) {
 return physicalBytes && physicalBytes < (3400ull << 20);
}

// 0 automatic, 1 standard, 2 reduced. Invalid modes retain automatic policy.
static inline int pg_memory_profile(uint64_t physicalBytes, int mode) {
 return mode==2 ? 1 : mode==1 ? 0 : pg_low_memory_device(physicalBytes);
}

// Only used on the low-memory path. Leave at least 1.5 GiB of the measured app
// allowance for geometry, engine, app and transient allocations. The advertised
// texture budget is smaller when BC blocks need decoding. This is a streaming
// hint, not a hard GPU heap limit or a promise of an exact allocation ratio.
static inline uint64_t pg_low_memory_texture_mb(uint64_t processLimitMB, int nativeBC) {
 uint64_t physicalBudget=processLimitMB>1536 ? processLimitMB-1536 : 256;
 if(physicalBudget<256)physicalBudget=256;
 if(physicalBudget>512)physicalBudget=512;
 return nativeBC ? physicalBudget : physicalBudget/2;
}
