#include "ZemaNativeRecoveryQAEngine.h"
#include "RecoveryCore.h"
#include "game.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
static w2c_game actual;static pthread_t engine_thread;
static int engine_calls,opens,sets,original_calls,memory_reads;static bool loading,clock_fail,pause_active;static _Atomic int lan=0;
static uint64_t milliseconds=10000;static uint8_t bytes[4096];
int clock_gettime(clockid_t clock,struct timespec *out){assert(clock==CLOCK_MONOTONIC);if(clock_fail)return -1;out->tv_sec=(time_t)(milliseconds/1000);out->tv_nsec=(long)(milliseconds%1000)*1000000;return 0;}
static void check(w2c_game *p){assert(p==&actual&&pthread_equal(pthread_self(),engine_thread));engine_calls++;}
int ZemaLabEnabled(void){return atomic_load(&lan);}
void w2c_game_f36288(w2c_game *p,u32 policy){check(p);assert(policy==0);opens++;pause_active=true;}
u32 w2c_game_f56852(w2c_game *p,u32 g,u32 c,f32 v){check(p);assert(g==2&&(c==206||c==201||c==187||c==188)&&(v==0||v==1));sets++;return 1;}
u32 w2c_game_f36254(w2c_game *p,u32 f){check(p);assert(f==0);return pause_active;}
u32 w2c_game_f36267(w2c_game *p){check(p);return 1;}
u32 w2c_game_f51856(w2c_game *p){check(p);return 1;}
u32 w2c_game_f51831(w2c_game *p){check(p);return 3123948979u;}
u32 w2c_game_f34946(w2c_game *p){check(p);return loading;}
u32 w2c_game_f51820(w2c_game *p){check(p);return 0;}
u32 w2c_game_f51824(w2c_game *p){check(p);return 0;}
u32 w2c_game_f51826(w2c_game *p){check(p);return 0;}
void ZemaNativeRecoveryQAOriginal_f37308(w2c_game *p,u32 movie,u64 method,u64 args,u32 n){assert(p!=NULL&&movie==14);(void)method;(void)args;(void)n;original_calls++;}
uint8_t *mugoat_memory_data(void *p,uint64_t *size){assert(p==&actual);memory_reads++;*size=sizeof bytes;return bytes;}
static ZemaNativeRecoveryQASnapshot read_status(void){ZemaNativeRecoveryQASnapshot s;assert(ZemaNativeRecoveryQARead(&s,sizeof s)==1);return s;}
static void *foreign_primary(void *unused){(void)unused;assert(!ZemaNativeRecoveryQABindEngineMainThread(&actual));ZemaNativeRecoveryQAPrimary(&actual,12840656);return NULL;}
static void *foreign_frontend(void *unused){(void)unused;ZemaNativeRecoveryQAFrontend(&actual,14,128,1024,0);return NULL;}
static void emit(const char *method,int32_t *a,unsigned n){memset(bytes+128,0,97);memcpy(bytes+128,method,strlen(method));for(unsigned i=0;i<n;i++){uint32_t t=3;double d=a[i];memcpy(bytes+1024+24*i+8,&t,4);memcpy(bytes+1024+24*i+16,&d,8);}ZemaNativeRecoveryQAFrontend(&actual,14,128,1024,n);}
int main(void){engine_thread=pthread_self();assert(ZemaNativeRecoveryQAEnabled()==1);assert(!ZemaNativeRecoveryQARead(NULL,0));assert(!ZemaNativeRecoveryQARead(&(ZemaNativeRecoveryQASnapshot){0},1));
 uint64_t ticket=ZemaNativeRecoveryQAAdmitted();assert(ticket==1&&engine_calls==0);ZemaNativeRecoveryQASnapshot s=read_status();assert(s.admission_ticket==ticket&&s.generation==0);assert(!ZemaNativeRecoveryQARequest(ZemaQAOpen,ticket,s.generation,0));assert(!ZemaNativeRecoveryQABindEngineMainThread(&actual));assert(engine_calls==0);atomic_store(&lan,1);
 ZemaNativeRecoveryQAPrimary(&actual,123);assert(engine_calls==0);ZemaNativeRecoveryQAPrimary(&actual,12840656);assert(engine_calls==0);assert(ZemaNativeRecoveryQABindEngineMainThread(&actual));ZemaNativeRecoveryQAPrimary(&actual,12840656);int count=engine_calls;
 pthread_t other;assert(pthread_create(&other,NULL,foreign_primary,NULL)==0);assert(pthread_join(other,NULL)==0);assert(engine_calls==count&&read_status().thread_refusals==2);
 assert(ZemaNativeRecoveryQARequest(ZemaQAOpen,ticket,s.generation,0)==1);assert(engine_calls==count);loading=true;ZemaNativeRecoveryQAPrimary(&actual,12840656);assert(opens==0&&read_status().status==-2);
 loading=false;assert(ZemaNativeRecoveryQARequest(ZemaQAOpen,ticket,s.generation,0)==1);ZemaNativeRecoveryQAPrimary(&actual,12840656);assert(opens==1);s=read_status();assert(s.generation==1);assert(!ZemaNativeRecoveryQARequest(ZemaQARB,ticket,0,0));
 memset(bytes+128,0,97);memcpy(bytes+128,"PAUSE_MENU_READY_TO_RENDER",25);int old_original=original_calls,old_reads=memory_reads;QState pending;assert(q_snapshot(&zgta_qa_recovery,&pending));
 assert(pthread_create(&other,NULL,foreign_frontend,NULL)==0);assert(pthread_join(other,NULL)==0);assert(original_calls==old_original+1&&memory_reads==old_reads);assert(read_status().movie==pending.movie&&read_status().phase==(uint32_t)pending.phase);
 w2c_game foreign_instance={0};ZemaNativeRecoveryQAFrontend(&foreign_instance,14,128,1024,0);assert(original_calls==old_original+2&&memory_reads==old_reads);assert(read_status().movie==pending.movie&&read_status().phase==(uint32_t)pending.phase);assert(read_status().thread_refusals==4);
 emit("PAUSE_MENU_READY_TO_RENDER",NULL,0);emit("LAYOUT_CHANGED",(int32_t[]){6,0,1000,-1,1},5);assert(original_calls==4&&memory_reads==2&&read_status().phase==Q_MAP);
 s=read_status();assert(ZemaNativeRecoveryQARequest(ZemaQARB,ticket,s.generation,0));ZemaNativeRecoveryQAPrimary(&actual,12840656);assert(sets==1);clock_fail=true;ZemaNativeRecoveryQAPrimary(&actual,12840656);assert(sets==2&&read_status().phase==Q_INVALID);clock_fail=false;
 ZemaNativeRecoveryQADisconnected();s=read_status();assert(s.admission_ticket==0);assert(!ZemaNativeRecoveryQARequest(ZemaQAOpen,ticket,s.generation,0));
 uint64_t ticket2=ZemaNativeRecoveryQAAdmitted();assert(ticket2==2);assert(!ZemaNativeRecoveryQARequest(ZemaQAOpen,ticket,s.generation,0));assert(ZemaNativeRecoveryQARequest(ZemaQACancel,ticket2,s.generation,0));ZemaNativeRecoveryQAPrimary(&actual,12840656);s=read_status();assert(s.phase==Q_IDLE);
 count=engine_calls;assert(!ZemaNativeRecoveryQARequest(ZemaQABindVisibleQuit,ticket2,s.generation,0x1234));assert(!ZemaNativeRecoveryQARequest(ZemaQAConfirmBoundQuit,ticket2,s.generation,0x05e96ecc));assert(engine_calls==count);
 pause_active=false;s=read_status();assert(ZemaNativeRecoveryQARequest(ZemaQAOpen,ticket2,s.generation,0));ZemaNativeRecoveryQAPrimary(&actual,12840656);emit("PAUSE_MENU_READY_TO_RENDER",NULL,0);emit("LAYOUT_CHANGED",(int32_t[]){6,0,1000,-1,1},5);s=read_status();assert(ZemaNativeRecoveryQARequest(ZemaQARB,ticket2,s.generation,0));ZemaNativeRecoveryQAPrimary(&actual,12840656);count=engine_calls;int pressed_sets=sets;atomic_store(&lan,0);ZemaNativeRecoveryQAPrimary(&actual,12840656);assert(sets==pressed_sets+1&&engine_calls==count+1&&read_status().phase==Q_INVALID);count=engine_calls;
 atomic_store(&lan,0);uint64_t prelaunch=ZemaNativeRecoveryQAAdmitted();assert(prelaunch==3);assert(!ZemaNativeRecoveryQARequest(ZemaQAOpen,prelaunch,s.generation,0));ZemaNativeRecoveryQAPrimary(&actual,12840656);assert(engine_calls==count);
 puts("QA bridge:19 ABI/UI-no-engine/explicit-entry-bind/PRIMARY/thread/epoch/generation/loading/observer/clock/release/default-policy checks PASS");return 0;
}
