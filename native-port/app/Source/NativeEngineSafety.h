#pragma once
#include <stdint.h>
#include <string.h>

/* Engine layout is verified by engine_safety.py before any caller is patched.
 * Do not suppress arbitrary invalid pointers or execution failures. */
static inline int pg_safety_range(uint64_t size, uint64_t pointer, uint64_t bytes) {
  return pointer != 0 && bytes <= size && pointer <= size - bytes;
}
static inline uint64_t pg_safety_u64(const uint8_t *base, uint64_t at) {
  uint64_t value; memcpy(&value, base + at, sizeof value); return value;
}
static inline uint32_t pg_safety_u32(const uint8_t *base, uint64_t at) {
  uint32_t value; memcpy(&value, base + at, sizeof value); return value;
}
static inline uint16_t pg_safety_u16(const uint8_t *base, uint64_t at) {
  uint16_t value; memcpy(&value, base + at, sizeof value); return value;
}
static inline int pg_safety_deleted_entity(const uint8_t *base, uint64_t size, uint64_t entity) {
  return pg_safety_range(size, entity, 80) &&
    pg_safety_u64(base, entity + 8) == UINT64_C(0xdddddddddddddddd) &&
    pg_safety_u64(base, entity + 72) == UINT64_C(0xdddddddddddddddd);
}
static inline int pg_safety_draw_budget(const uint8_t *base, uint64_t size, uint64_t entity) {
  if (!pg_safety_range(size, entity, 41) || (base[entity + 40] != 3 && base[entity + 40] != 4)) return 0;
  if (!pg_safety_range(size, 11012104, 8) || !pg_safety_range(size, 11012152, 8)) return 0;
  uint64_t buffer = pg_safety_u64(base, 11012104);
  if (pg_safety_range(size, buffer, 16908)) {
    uint32_t count = pg_safety_u16(base, buffer + 16904), capacity = pg_safety_u16(base, buffer + 16906);
    if (capacity && count + 8 >= capacity) return 1;
  }
  uint64_t lists = pg_safety_u64(base, 11012152);
  return pg_safety_range(size, lists, 83812) && pg_safety_u32(base, lists + 83808) >= 480;
}
static inline void pg_safety_drop_destroyed_phases(uint8_t *base, uint64_t size) {
  if (!pg_safety_range(size, 11547128, 8)) return;
  uint64_t list = pg_safety_u64(base, 11547128);
  if (!pg_safety_range(size, list, 10)) return;
  uint64_t data = pg_safety_u64(base, list);
  uint16_t count = pg_safety_u16(base, list + 8), kept = 0;
  if (!pg_safety_range(size, data, (uint64_t)count * 8)) return;
  for (uint32_t i = 0; i < count; ++i) {
    uint64_t phase = pg_safety_u64(base, data + (uint64_t)i * 8);
    if (pg_safety_range(size, phase, 8) && pg_safety_u64(base, phase) == 4219920) continue;
    memcpy(base + data + (uint64_t)kept++ * 8, &phase, 8);
  }
  if (kept != count) memcpy(base + list + 8, &kept, 2);
}
static inline int pg_safety_stale_job(const uint8_t *base, uint64_t size, uint64_t job, uint64_t table_size) {
  if (!pg_safety_range(size, job, 147)) return 1;
  uint64_t function = pg_safety_u64(base, job + 96);
  return function >= table_size || ((base[job + 110] & 1) && pg_safety_u32(base, job + 112) > 268435456);
}
/* Park for half the remaining limiter time, at most 1 ms. Keep its last
 * 50 us and its original 5% frame margin; invalid timers never block. */
static inline uint64_t pg_safety_frame_idle_ns(float remaining) {
  if (!(remaining > 0.00005f && remaining < 1.0f)) return 0;
  double ns = (double)remaining * 500000000.0;
  return (uint64_t)(ns < 1000000.0 ? ns : 1000000.0);
}
/* The audio loop already measured its remaining 15 ms budget. Retain a
 * 20 us margin and its original timeout check, including paused behavior. */
static inline uint64_t pg_safety_audio_idle_ns(float remaining_ms) {
  if (!(remaining_ms > 0.02f && remaining_ms <= 15.0f)) return 0;
  return (uint64_t)(((double)remaining_ms - 0.02) * 1000000.0);
}
