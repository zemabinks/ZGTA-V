#ifndef ZGTA_QA_RECOVERY_OBSERVER_H
#define ZGTA_QA_RECOVERY_OBSERVER_H
#include "RecoveryCore.h"
#include <stddef.h>
typedef void (*QOriginalFrontend)(void *,uint32_t,uint64_t,uint64_t,uint32_t);
typedef const uint8_t *(*QMemory)(void *,uint64_t *);
/* ABI-equivalent adapter model: original is called exactly once, before observation. */
void q_original_preserving_frontend(QRecovery *,void *actual_engine,QOriginalFrontend,QMemory,
 uint32_t movie,uint64_t method,uint64_t args,uint32_t count);
#endif
