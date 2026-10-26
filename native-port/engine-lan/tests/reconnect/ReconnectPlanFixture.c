#include "ReconnectPlan.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned opens,presses,releases,public_presses;static bool menu,valid=true,ready=true;static uint32_t version=3123948979u;
static int controls[40];static uint64_t now=100;
static void open_menu(void *e,int p){(void)e;(void)p;opens++;menu=true;}
static int input(void *e,int group,int control,float value){(void)e;assert(group==2);if(value==1){controls[presses++]=control;if(presses>6)public_presses++;}else releases++;return 1;}
static bool active(void *e){(void)e;return menu;}static bool is_valid(void *e){(void)e;return valid;}static bool is_ready(void *e){(void)e;return ready;}static uint32_t ver(void *e){(void)e;return version;}static QWarning warn(void *e){(void)e;return (QWarning){0};}
static QEngineAPI api={open_menu,input,active,is_valid,is_ready,ver,warn};
static void tick(RReconnect *r,QRecovery *q){q_primary_tick(q,NULL,&api,++now,false);r_tick(r,q,now,false);}
static void event(QRecovery *q,QEvent ev,int a,int b,int c,int d,int e){int32_t args[]={a,b,c,d,e};q_observe(q,ev,14,args,5);}
static void initial(RReconnect *r,QRecovery *q){q_admission_epoch(q,1);assert(r_start(r,1,0));r_tick(r,q,now,false);tick(r,q);q_observe(q,Q_EV_READY,14,NULL,0);event(q,Q_EV_LAYOUT,6,1000,1000,0,0);tick(r,q);}
static void ack(RReconnect *r,QRecovery *q,QEvent ev,int a,int b,int c,int d,int e){tick(r,q);event(q,ev,a,b,c,d,e);tick(r,q);}
static void reset_fixture(void){opens=presses=releases=public_presses=0;menu=false;valid=ready=true;version=3123948979u;memset(controls,0,sizeof controls);}
int main(void){unsigned cases=0;
 {reset_fixture();RReconnect r=R_RECONNECT_INIT;QRecovery q=Q_RECOVERY_INIT;initial(&r,&q);
 ack(&r,&q,Q_EV_LAYOUT,6,1042,1042,0,0);
 ack(&r,&q,Q_EV_TRIGGER,6,1042,0,1064,0);
 ack(&r,&q,Q_EV_LAYOUT,6,1064,1064,20,0);
 ack(&r,&q,Q_EV_LAYOUT,6,1064,1064,15,0);
 ack(&r,&q,Q_EV_LAYOUT,6,1064,1064,14,0);
 ack(&r,&q,Q_EV_TRIGGER,6,1064,14,-1,-1);
 RSnapshot s;assert(r_snapshot(&r,&s)&&s.step==R_CONTINUE_IN_GTA);assert(opens==1&&presses==6&&releases==6&&public_presses==0);int want[]={206,201,188,188,188,201};assert(!memcmp(controls,want,sizeof want));
 for(int i=0;i<200;i++)tick(&r,&q);assert(presses==6&&releases==6);cases++;}
 {RReconnect r=R_RECONNECT_INIT;assert(!r_start(&r,0,0));cases++;}
 {RReconnect r=R_RECONNECT_INIT;assert(r_start(&r,1,0)&&!r_start(&r,1,0));cases++;}
 {reset_fixture();RReconnect r=R_RECONNECT_INIT;QRecovery q=Q_RECOVERY_INIT;q_admission_epoch(&q,2);assert(r_start(&r,1,0));r_tick(&r,&q,++now,false);RSnapshot s;assert(r_snapshot(&r,&s)&&s.step==R_FAILED&&opens==0);cases++;}
 {reset_fixture();RReconnect r=R_RECONNECT_INIT;QRecovery q=Q_RECOVERY_INIT;q_admission_epoch(&q,1);assert(r_start(&r,1,0));r_tick(&r,&q,++now,true);RSnapshot s;assert(r_snapshot(&r,&s)&&s.step==R_FAILED&&opens==0);cases++;}
 {reset_fixture();RReconnect r=R_RECONNECT_INIT;QRecovery q=Q_RECOVERY_INIT;initial(&r,&q);for(int i=0;i<5;i++)tick(&r,&q);assert(presses==1);r_tick(&r,&q,now+120001,false);RSnapshot s;assert(r_snapshot(&r,&s)&&s.step==R_FAILED);cases++;}
 {reset_fixture();RReconnect r=R_RECONNECT_INIT;QRecovery q=Q_RECOVERY_INIT;initial(&r,&q);ack(&r,&q,Q_EV_LAYOUT,6,1042,1042,0,0);ack(&r,&q,Q_EV_TRIGGER,6,1042,0,1064,0);ack(&r,&q,Q_EV_LAYOUT,6,1064,1064,19,0);RSnapshot s;assert(r_snapshot(&r,&s)&&s.step==R_FAILED&&presses==3);cases++;}
 {reset_fixture();RReconnect r=R_RECONNECT_INIT;QRecovery q=Q_RECOVERY_INIT;initial(&r,&q);tick(&r,&q);q_admission_epoch(&q,0);tick(&r,&q);assert(releases==1&&presses==1);RSnapshot s;assert(r_snapshot(&r,&s)&&s.step==R_FAILED);cases++;}
 {reset_fixture();RReconnect r=R_RECONNECT_INIT;QRecovery q=Q_RECOVERY_INIT;initial(&r,&q);version=1;tick(&r,&q);assert(presses==0);RSnapshot s;assert(r_snapshot(&r,&s)&&s.step==R_FAILED);cases++;}
 {reset_fixture();RReconnect r=R_RECONNECT_INIT;QRecovery q=Q_RECOVERY_INIT;q_admission_epoch(&q,1);q.s.phase=Q_CONTENT;assert(r_start(&r,1,0));r_tick(&r,&q,++now,false);RSnapshot s;assert(r_snapshot(&r,&s)&&s.step==R_FAILED&&opens==0);cases++;}
 {reset_fixture();RReconnect r=R_RECONNECT_INIT;QRecovery q=Q_RECOVERY_INIT;q_admission_epoch(&q,1);q.s.phase=Q_INVALID;assert(r_start(&r,1,0));r_tick(&r,&q,++now,false);tick(&r,&q);tick(&r,&q);assert(opens==1);cases++;}
 {reset_fixture();RReconnect r=R_RECONNECT_INIT;QRecovery q=Q_RECOVERY_INIT;initial(&r,&q);tick(&r,&q);q_observe(&q,Q_EV_EXIT,14,NULL,0);tick(&r,&q);RSnapshot s;assert(r_snapshot(&r,&s)&&s.step==R_FAILED&&releases==1);cases++;}
 {reset_fixture();RReconnect r=R_RECONNECT_INIT;QRecovery q=Q_RECOVERY_INIT;initial(&r,&q);assert(q.s.command==Q_RB);r_cancel(&r);assert(q_cancel_checked(&q,q.s.generation));tick(&r,&q);assert(presses==0&&q.s.phase==Q_IDLE);cases++;}
 {reset_fixture();RReconnect r=R_RECONNECT_INIT;QRecovery q=Q_RECOVERY_INIT;initial(&r,&q);tick(&r,&q);assert(presses==1&&releases==0);r_cancel(&r);assert(q_cancel_checked(&q,q.s.generation));tick(&r,&q);assert(presses==1&&releases==1&&q.s.phase==Q_IDLE);cases++;}
 {QRecovery q=Q_RECOVERY_INIT;q.s.generation=3;assert(!q_cancel_checked(&q,2)&&q.s.command==Q_CMD_NONE);cases++;}
 printf("{\"result\":\"PASS\",\"cases\":%u,\"public_bind_confirm_inputs\":0}\n",cases);
}
