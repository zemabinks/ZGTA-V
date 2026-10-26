#include "ZemaNativeRecoveryQAEngine.h"
#include "RecoveryCore.h"
#include "RecoveryObserver.h"
#include <stddef.h>
#ifndef ZGTA_NATIVE_RECOVERY_QA
#define ZGTA_NATIVE_RECOVERY_QA 0
#endif
#if ZGTA_NATIVE_RECOVERY_QA
#include "game.h"
#include "ReconnectPlan.h"
static RReconnect reconnect_plan=R_RECONNECT_INIT;
#include <pthread.h>
#include <time.h>
#include <string.h>
/* Exact pinned generated ABI; also checked against game-impl.h in standalone syntax tests. */
extern void w2c_game_f36288(w2c_game *,u32);
extern u32 w2c_game_f56852(w2c_game *,u32,u32,f32);
extern u32 w2c_game_f36254(w2c_game *,u32);
extern u32 w2c_game_f36267(w2c_game *);
extern u32 w2c_game_f51856(w2c_game *);
extern u32 w2c_game_f51831(w2c_game *);
extern u32 w2c_game_f51820(w2c_game *);
extern u32 w2c_game_f51824(w2c_game *);
extern u32 w2c_game_f51826(w2c_game *);
extern u32 w2c_game_f34946(w2c_game *);
extern void ZemaNativeRecoveryQAOriginal_f37308(w2c_game *,u32,u64,u64,u32);
extern uint8_t *mugoat_memory_data(void *,uint64_t *);
extern int ZemaLabEnabled(void);
static _Atomic uint64_t next_ticket,last_now;
static _Atomic uint32_t current_loading,loading_seen,loading_returned,thread_refusals;
static atomic_flag owner_lock=ATOMIC_FLAG_INIT;
static bool owner_set;static pthread_t owner_thread;static void *owner_instance;
/* QA-only observed hash, not a shipping allowlist or proof of native wording. */
static const uint32_t observed_session_warning=0x05e96eccu;
int ZemaNativeRecoveryQABindEngineMainThread(void *instance){
 if(!instance||!ZemaLabEnabled()||atomic_flag_test_and_set_explicit(&owner_lock,memory_order_acquire))return 0;
 pthread_t here=pthread_self();bool ok=!owner_set||(owner_instance==instance&&pthread_equal(owner_thread,here));
 if(!owner_set){owner_thread=here;owner_instance=instance;owner_set=true;}
 atomic_flag_clear_explicit(&owner_lock,memory_order_release);return ok?1:0;
}
void ZemaNativeRecoveryQAEngineMainEnded(void *instance){
 if(atomic_flag_test_and_set_explicit(&owner_lock,memory_order_acquire))return;
 bool ours=owner_set&&owner_instance==instance&&pthread_equal(owner_thread,pthread_self());
 atomic_flag_clear_explicit(&owner_lock,memory_order_release);
 if(ours)q_admission_epoch(&zgta_qa_recovery,0); /* never rebind from UI or an arbitrary pad */
}
static bool primary_thread(void *instance){
 if(atomic_flag_test_and_set_explicit(&owner_lock,memory_order_acquire))return false;
 bool ok=owner_set&&owner_instance==instance&&pthread_equal(owner_thread,pthread_self());
 atomic_flag_clear_explicit(&owner_lock,memory_order_release);return ok;
}
static uint64_t now_ms(void){struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t)!=0)return 0;return (uint64_t)t.tv_sec*1000+(uint64_t)t.tv_nsec/1000000;}
static void open_menu(void *p,int policy){w2c_game_f36288(p,(u32)policy);}
static int set_next(void *p,int group,int control,float value){return (int)w2c_game_f56852(p,(u32)group,(u32)control,value);}
static bool active(void *p){return w2c_game_f36254(p,0)!=0;}
static bool valid(void *p){return w2c_game_f36267(p)!=0;}
static bool ready(void *p){return w2c_game_f51856(p)!=0;}
static uint32_t version(void *p){return w2c_game_f51831(p);}
static QWarning warning(void *p){QWarning w;w.active=w2c_game_f51826(p)!=0;w.ready=w2c_game_f51824(p)!=0;w.hash=w2c_game_f51820(p);return w;}
static const QEngineAPI api={open_menu,set_next,active,valid,ready,version,warning};
static void original(void *p,uint32_t movie,uint64_t method,uint64_t args,uint32_t count){ZemaNativeRecoveryQAOriginal_f37308(p,movie,method,args,count);}
static const uint8_t *memory(void *p,uint64_t *size){return mugoat_memory_data(p,size);}
int ZemaNativeRecoveryQAEnabled(void){return 1;}
uint64_t ZemaNativeRecoveryQAAdmitted(void){
 uint64_t ticket=atomic_fetch_add_explicit(&next_ticket,1,memory_order_relaxed)+1;
 q_admission_epoch(&zgta_qa_recovery,ticket);return ticket;
}
void ZemaNativeRecoveryQADisconnected(void){q_admission_epoch(&zgta_qa_recovery,0);}
int ZemaNativeRecoveryReconnectStart(uint64_t ticket,uint64_t generation){
 QState s;
 if(!ZemaLabEnabled()||!ticket||!q_snapshot(&zgta_qa_recovery,&s)||
    ticket!=atomic_load_explicit(&zgta_qa_recovery.admission_epoch,memory_order_acquire)||generation!=s.generation)return 0;
 return r_start(&reconnect_plan,ticket,generation)?1:0; /* enqueue only */
}
void ZemaNativeRecoveryReconnectCancel(void){
 QState s;r_cancel(&reconnect_plan);
 if(q_snapshot(&zgta_qa_recovery,&s))
  (void)q_cancel_checked(&zgta_qa_recovery,s.generation);
}
int ZemaNativeRecoveryReconnectRead(ZemaNativeReconnectSnapshot *out,uint32_t bytes){
 RSnapshot s;if(!out||bytes!=sizeof *out||!r_snapshot(&reconnect_plan,&s))return 0;
 *out=(ZemaNativeReconnectSnapshot){s.ticket,s.generation,(uint32_t)s.step,s.status};return 1;
}

int ZemaNativeRecoveryQARead(ZemaNativeRecoveryQASnapshot *out,uint32_t bytes){
 if(!out||bytes!=sizeof *out)return 0;QState s;if(!q_snapshot(&zgta_qa_recovery,&s))return 0;
 *out=(ZemaNativeRecoveryQASnapshot){.admission_ticket=atomic_load_explicit(&zgta_qa_recovery.admission_epoch,memory_order_acquire),.generation=s.generation,
 .phase=s.phase,.status=s.status,.movie=s.movie,.selected=s.selected,.context=s.context,
 .loading=atomic_load(&current_loading),.loading_seen_after_confirm=atomic_load(&loading_seen),.loading_returned_after_confirm=atomic_load(&loading_returned),
 .warning_active=s.warning.active,.warning_ready=s.warning.ready,.warning_hash=s.warning.hash,.bound_hash=s.bound_hash,
 .confirm_press=s.confirm_press,.confirm_release=s.confirm_release,.navigation_count=s.navigation_count,.thread_refusals=atomic_load(&thread_refusals)};return 1;
}
int ZemaNativeRecoveryQARequest(uint32_t command,uint64_t ticket,uint64_t generation,uint32_t hash){
 if(!ZemaLabEnabled()||command<Q_OPEN||command>Q_CANCEL)return 0;
 if((command==Q_BIND_VISIBLE_QUIT||command==Q_CONFIRM_BOUND_QUIT)&&hash!=observed_session_warning)return 0;
 return q_request_checked(&zgta_qa_recovery,ticket,generation,(QCommand)command,hash)?1:0;
}
void ZemaNativeRecoveryQAPrimary(void *instance,uint64_t pad){
 if(pad!=12840656||!instance)return;
 if(!primary_thread(instance)){atomic_fetch_add(&thread_refusals,1);return;}
 bool selected_lan=ZemaLabEnabled()!=0;
 if(!selected_lan){q_admission_epoch(&zgta_qa_recovery,0);QState pending;if(!q_snapshot(&zgta_qa_recovery,&pending)||!pending.pending_release)return;}
 uint64_t now=now_ms();if(!now){q_admission_epoch(&zgta_qa_recovery,0);now=atomic_load(&last_now);}else atomic_store(&last_now,now);
 /* Canonical getter only; no raw loading-state access. false does not prove a ready world. */
 bool loading=!selected_lan||w2c_game_f34946(instance)!=0;atomic_store(&current_loading,loading);
 q_primary_tick(&zgta_qa_recovery,instance,&api,now,loading);
 if(selected_lan)r_tick(&reconnect_plan,&zgta_qa_recovery,now,loading); /* only after known boot-owner gate and core release */
 QState s;if(q_snapshot(&zgta_qa_recovery,&s)){
  if(s.phase!=Q_DONE){atomic_store(&loading_seen,0);atomic_store(&loading_returned,0);}
  else if(loading)atomic_store(&loading_seen,1);
  else if(atomic_load(&loading_seen))atomic_store(&loading_returned,1);
 }
}
void ZemaNativeRecoveryQAFrontend(void *instance,uint32_t movie,uint64_t method,uint64_t args,uint32_t count){
 if(!ZemaLabEnabled()){original(instance,movie,method,args,count);return;}
 if(!primary_thread(instance)){atomic_fetch_add(&thread_refusals,1);original(instance,movie,method,args,count);return;}
 q_original_preserving_frontend(&zgta_qa_recovery,instance,original,memory,movie,method,args,count);
}
#else
int ZemaNativeRecoveryQABindEngineMainThread(void *p){(void)p;return 0;}
void ZemaNativeRecoveryQAEngineMainEnded(void *p){(void)p;}
int ZemaNativeRecoveryQAEnabled(void){return 0;}
uint64_t ZemaNativeRecoveryQAAdmitted(void){return 0;}
void ZemaNativeRecoveryQADisconnected(void){}
int ZemaNativeRecoveryReconnectStart(uint64_t t,uint64_t g){(void)t;(void)g;return 0;}
void ZemaNativeRecoveryReconnectCancel(void){}
int ZemaNativeRecoveryReconnectRead(ZemaNativeReconnectSnapshot *o,uint32_t n){(void)o;(void)n;return 0;}
int ZemaNativeRecoveryQARead(ZemaNativeRecoveryQASnapshot *out,uint32_t bytes){(void)out;(void)bytes;return 0;}
int ZemaNativeRecoveryQARequest(uint32_t c,uint64_t t,uint64_t g,uint32_t h){(void)c;(void)t;(void)g;(void)h;return 0;}
void ZemaNativeRecoveryQAPrimary(void *p,uint64_t pad){(void)p;(void)pad;}
void ZemaNativeRecoveryQAFrontend(void *p,uint32_t m,uint64_t s,uint64_t a,uint32_t c){(void)p;(void)m;(void)s;(void)a;(void)c;}
#endif
