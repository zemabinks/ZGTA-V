#pragma once
#include <stdlib.h>
#include <errno.h>

// Benchmark override. Keep the established two-worker default until a paired
// run supports changing it; host CPU counts are not equivalent to iPhone cores.
static inline unsigned pg_engine_core_configuration(const char *text) {
 if(!text||!*text)return 2;
 char *end;errno=0;long value=strtol(text,&end,10);
 if(errno||end==text||*end||value<1||value>8)return 2;
 return (unsigned)value;
}
