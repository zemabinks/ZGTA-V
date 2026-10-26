#ifndef ZGTA_QA_RECOVERY_CORE_H
#define ZGTA_QA_RECOVERY_CORE_H
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
/* Standalone provisional QA model. No application integration. */
typedef enum { Q_IDLE,Q_OPEN_WAIT,Q_MAP,Q_RB_RELEASE,Q_ONLINE_WAIT,Q_ONLINE,
 Q_HEADER_RELEASE,Q_HEADER_WAIT,Q_CONTENT,Q_NAV_RELEASE,Q_NAV_WAIT,
 Q_FIND_RELEASE,Q_FIND_WAIT,Q_FIND_ACK,Q_PUBLIC_RELEASE,Q_PUBLIC_WAIT,
 Q_WARNING_WAIT,Q_WARNING_READY,Q_WARNING_BOUND,Q_CONFIRM_RELEASE,Q_DONE,Q_INVALID } QPhase;
typedef enum { Q_CMD_NONE,Q_OPEN,Q_RB,Q_HEADER,Q_DOWN,Q_UP,Q_FIND,
 Q_PUBLIC_VISIBLE,Q_BIND_VISIBLE_QUIT,Q_CONFIRM_BOUND_QUIT,Q_CANCEL } QCommand;
typedef enum { Q_EV_READY,Q_EV_LAYOUT,Q_EV_TRIGGER,Q_EV_EXIT } QEvent;
typedef struct { bool active,ready; uint32_t hash; } QWarning;
typedef struct {
 void (*open)(void *engine, int policy);
 int (*set_next)(void *engine,int group,int control,float value);
 bool (*pause_active)(void *engine);
 bool (*pause_valid)(void *engine);
 bool (*frontend_ready)(void *engine);
 uint32_t (*menu_version)(void *engine);
 QWarning (*warning)(void *engine); /* adapter calls only the3 pure getters */
} QEngineAPI;
typedef struct {
 QPhase phase; uint64_t generation,admission_epoch,deadline_ms,last_warning_ms;
 int movie,selected,context,status,ack_kind; unsigned navigation_count;
 bool pending_release,ack,warning_sampled,pause_exit;
 int release_to,control,press,release,confirm_press,confirm_release;
 QWarning warning; uint32_t bound_hash;
 QCommand command; uint64_t command_epoch,command_generation; uint32_t command_hash;
 unsigned dropped_observations;
} QState;
typedef struct { atomic_flag lock; _Atomic uint64_t admission_epoch; QState s; } QRecovery;
#define Q_RECOVERY_INIT { .lock=ATOMIC_FLAG_INIT,.admission_epoch=ATOMIC_VAR_INIT(0),.s={.movie=-1,.selected=-1,.press=-1,.release=-1,.confirm_press=-1,.confirm_release=-1} }
extern QRecovery zgta_qa_recovery; /* ONE process-global instance, never perWASM instance */
void q_admission_epoch(QRecovery *,uint64_t epoch); /* no game/API calls */
bool q_request_checked(QRecovery *,uint64_t expected_epoch,uint64_t expected_generation,QCommand,uint32_t expected_warning_hash);
bool q_cancel_checked(QRecovery *,uint64_t expected_generation); /* cancellation supersedes only a queued local command */
bool q_request(QRecovery *,uint64_t expected_epoch,QCommand); /* UIKit/network enqueue only */
void q_observe(QRecovery *,QEvent,int movie,const int32_t *a,unsigned count); /* after original callback */
void q_primary_tick(QRecovery *,void *actual_engine,const QEngineAPI *,uint64_t monotonic_ms,bool loading);
bool q_snapshot(QRecovery *,QState *out);
#endif
