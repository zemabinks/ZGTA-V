#ifndef ZGTA_SETTINGS_RECONNECT_PLAN_H
#define ZGTA_SETTINGS_RECONNECT_PLAN_H
#include "RecoveryCore.h"
/* Enqueue/snapshot only on UIKit; tick is called ONLY inside the bound PRIMARY hook. */
typedef enum { R_IDLE,R_REQUESTED,R_CANCELLING,R_OPEN,R_MAP,R_ONLINE,R_ROW20,R_ROW15,R_ROW14,R_FIND,R_CONTINUE_IN_GTA,R_FAILED } RStep;
typedef struct {
 atomic_flag lock; _Atomic bool cancelled; RStep step; uint64_t ticket,generation,deadline_ms;
 int status; bool awaiting,open_adopted; QPhase expected_phase; int expected_selected;
} RReconnect;
#define R_RECONNECT_INIT { .lock=ATOMIC_FLAG_INIT }
typedef struct { RStep step; int status; uint64_t ticket,generation; } RSnapshot;
bool r_start(RReconnect *,uint64_t ticket,uint64_t generation);
void r_cancel(RReconnect *);
bool r_snapshot(RReconnect *,RSnapshot *);
void r_tick(RReconnect *,QRecovery *,uint64_t now_ms,bool loading);
#endif
