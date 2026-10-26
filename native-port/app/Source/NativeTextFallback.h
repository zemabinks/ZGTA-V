/* Bounded original-first text compatibility. No host pointers escape into WASM.
 * Caller serializes cache access; zero allocations for known engine translations.
 */
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include "NativeTextLabels.inc"
typedef struct { uint64_t pointers[PG_TEXT_LABEL_COUNT]; } PGTextFallbackCache;
typedef uint64_t (*PGTextAllocate)(void *, size_t);
typedef int (*PGTextCopy)(void *, uint64_t, const char *, size_t);
static inline int pg_text_label_index(uint32_t hash) {
  size_t lo=0, hi=PG_TEXT_LABEL_COUNT;
  while(lo<hi) { size_t mid=lo+(hi-lo)/2; if(pg_text_labels[mid].hash<hash)lo=mid+1;else hi=mid; }
  return lo<PG_TEXT_LABEL_COUNT && pg_text_labels[lo].hash==hash ? (int)lo : -1;
}
static inline uint64_t pg_text_fallback(PGTextFallbackCache *cache, uint32_t hash,
    uint64_t original, PGTextAllocate allocate, PGTextCopy copy, void *context) {
  if(original)return original;
  int index=pg_text_label_index(hash);
  if(index<0)return 0;
  if(cache->pointers[index])return cache->pointers[index];
  size_t size=strlen(pg_text_labels[index].text)+1;
  uint64_t pointer=allocate(context,size);
  if(!pointer || !copy(context,pointer,pg_text_labels[index].text,size))return 0;
  cache->pointers[index]=pointer;
  return pointer;
}
