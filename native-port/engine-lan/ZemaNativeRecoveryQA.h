#ifndef ZEMA_NATIVE_RECOVERY_QA_H
#define ZEMA_NATIVE_RECOVERY_QA_H
#include <stdint.h>
/* Optional QA bridge only. No function accepts an arbitrary engine pointer from UI. */
typedef struct {
 uint64_t admission_ticket,generation;
 uint32_t phase; int32_t status,movie,selected,context;
 uint32_t loading,loading_seen_after_confirm,loading_returned_after_confirm;
 uint32_t warning_active,warning_ready,warning_hash,bound_hash;
 int32_t confirm_press,confirm_release;
 uint32_t navigation_count,thread_refusals;
} ZemaNativeRecoveryQASnapshot;
enum { ZemaQAOpen=1,ZemaQARB=2,ZemaQAHeader=3,ZemaQADown=4,ZemaQAUp=5,ZemaQAFind=6,
 ZemaQAPublicVisible=7,ZemaQABindVisibleQuit=8,ZemaQAConfirmBoundQuit=9,ZemaQACancel=10 };
int ZemaNativeRecoveryQAEnabled(void);
uint64_t ZemaNativeRecoveryQAAdmitted(void); /* invoke only after validated admission; does not open UI */
void ZemaNativeRecoveryQADisconnected(void);
int ZemaNativeRecoveryQARead(ZemaNativeRecoveryQASnapshot *,uint32_t bytes);
int ZemaNativeRecoveryQARequest(uint32_t command,uint64_t expected_ticket,uint64_t expected_generation,uint32_t expected_warning_hash);
/* Settings intent/snapshot only; no UI method accepts an engine pointer. */
typedef struct { uint64_t ticket,generation; uint32_t step; int32_t status; } ZemaNativeReconnectSnapshot;
int ZemaNativeRecoveryReconnectStart(uint64_t expected_ticket,uint64_t expected_generation);
int ZemaNativeRecoveryReconnectRead(ZemaNativeReconnectSnapshot *,uint32_t bytes);
void ZemaNativeRecoveryReconnectCancel(void);
#endif
