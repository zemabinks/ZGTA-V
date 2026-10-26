#pragma once
#include <stdint.h>
#include <stdbool.h>
void pg_resource_reclaim_init(void *base,uint64_t capacity);
void pg_resource_reclaim_pressure(bool pressure);
bool pg_resource_reclaim_has_pages(uint64_t heap);
bool pg_resource_reclaim_wants(uint64_t heap,uint64_t at);
void pg_resource_reclaim_free(uint64_t heap,uint64_t at,uint64_t size,uint64_t limit);
bool pg_resource_reclaim_reuse(uint64_t heap,uint64_t at,uint64_t size,uint64_t limit);
uint64_t PGResourceBytesReleased(void);
uint64_t PGResourceBytesReused(void);
uint64_t PGResourceReclaimFailures(void);
