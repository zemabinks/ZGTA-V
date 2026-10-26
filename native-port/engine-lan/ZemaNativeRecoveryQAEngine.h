#ifndef ZEMA_NATIVE_RECOVERY_QA_ENGINE_H
#define ZEMA_NATIVE_RECOVERY_QA_ENGINE_H
#include "ZemaNativeRecoveryQA.h"
/* Internal header: do not import into Swift or expose through UI controls. */
int ZemaNativeRecoveryQABindEngineMainThread(void *actual_instance);
void ZemaNativeRecoveryQAEngineMainEnded(void *actual_instance);
void ZemaNativeRecoveryQAPrimary(void *actual_instance,uint64_t pad);
void ZemaNativeRecoveryQAFrontend(void *actual_instance,uint32_t movie,uint64_t method,uint64_t args,uint32_t count);
#endif
