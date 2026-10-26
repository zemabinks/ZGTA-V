/* Diagnostic hashes only: no text replacement, heap allocation or player data.
 * Caller serializes access. At most 128 distinct misses per engine lifetime.
 */
#pragma once
#include <stdint.h>
#define PG_TEXT_AUDIT_LIMIT 128
typedef struct { uint64_t slots[256]; unsigned count; } PGTextMissingAudit;
static inline int pg_text_missing_first(PGTextMissingAudit *audit, uint32_t hash) {
  if(audit->count>=PG_TEXT_AUDIT_LIMIT)return 0;
  uint64_t tag=(uint64_t)hash+1;
  unsigned at=hash&255u;
  for(unsigned n=0;n<256;n++,at=(at+1)&255u) {
    if(audit->slots[at]==tag)return 0;
    if(!audit->slots[at]) { audit->slots[at]=tag; audit->count++; return 1; }
  }
  return 0;
}
