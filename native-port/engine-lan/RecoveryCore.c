#include "RecoveryCore.h"
#include <string.h>
QRecovery zgta_qa_recovery=Q_RECOVERY_INIT;
static bool lock(QRecovery *q){return !atomic_flag_test_and_set_explicit(&q->lock,memory_order_acquire);}
static void unlock(QRecovery *q){atomic_flag_clear_explicit(&q->lock,memory_order_release);}
static bool warning_phase(QPhase p){return p==Q_WARNING_WAIT||p==Q_WARNING_READY||p==Q_WARNING_BOUND;}
static void invalid(QState *s,int status){s->phase=Q_INVALID;s->status=status;s->ack=false;s->bound_hash=0;/* pending release intentionally preserved */}
static bool tuple(const int32_t *a,unsigned n,int x,int y,int z,int w,int v){return a&&n==5&&a[0]==x&&a[1]==y&&a[2]==z&&a[3]==w&&a[4]==v;}
static bool pair(QPhase p,QPhase press,QPhase wait){return p==press||p==wait;}
static void reset(QState *s){uint64_t gen=s->generation;memset(s,0,sizeof *s);s->generation=gen;s->movie=s->selected=-1;s->press=s->release=s->confirm_press=s->confirm_release=-1;}
void q_admission_epoch(QRecovery *q,uint64_t epoch){atomic_store_explicit(&q->admission_epoch,epoch,memory_order_release);}
bool q_request_checked(QRecovery *q,uint64_t epoch,uint64_t generation,QCommand cmd,uint32_t expected_hash){
 if(cmd<=Q_CMD_NONE||cmd>Q_CANCEL||!lock(q))return false;
 bool warning_command=cmd==Q_BIND_VISIBLE_QUIT||cmd==Q_CONFIRM_BOUND_QUIT;
 bool ok=q->s.command==Q_CMD_NONE&&generation==q->s.generation&&(cmd==Q_CANCEL||(epoch!=0&&epoch==atomic_load_explicit(&q->admission_epoch,memory_order_acquire)))&&(!warning_command||(expected_hash!=0&&expected_hash==q->s.warning.hash));
 if(ok){q->s.command=cmd;q->s.command_epoch=epoch;q->s.command_generation=generation;q->s.command_hash=expected_hash;}unlock(q);return ok;
}
bool q_cancel_checked(QRecovery *q,uint64_t generation){
 if(!lock(q))return false;
 bool ok=q->s.generation==generation;
 if(ok){q->s.command=Q_CANCEL;q->s.command_epoch=atomic_load_explicit(&q->admission_epoch,memory_order_acquire);q->s.command_generation=generation;q->s.command_hash=0;}
 unlock(q);return ok;
}
bool q_request(QRecovery *q,uint64_t epoch,QCommand cmd){QState s;if(!q_snapshot(q,&s))return false;return q_request_checked(q,epoch,s.generation,cmd,s.warning.hash);}
bool q_snapshot(QRecovery *q,QState *out){if(!lock(q))return false;*out=q->s;unlock(q);return true;}
void q_observe(QRecovery *q,QEvent ev,int movie,const int32_t *a,unsigned n){
 if(!lock(q))return;QState *s=&q->s;
 if(s->phase==Q_IDLE||s->phase==Q_INVALID||s->phase==Q_DONE){unlock(q);return;}
 if(s->admission_epoch!=atomic_load_explicit(&q->admission_epoch,memory_order_acquire)){invalid(s,-10);unlock(q);return;}
 if(warning_phase(s->phase)||s->phase==Q_CONFIRM_RELEASE){
  if(ev==Q_EV_EXIT&&movie==s->movie)s->pause_exit=true;
  else if(ev!=Q_EV_EXIT)invalid(s,-4);
  unlock(q);return;
 }
 if(ev==Q_EV_READY){if(s->phase==Q_OPEN_WAIT&&movie>=0&&movie<50)s->movie=movie;else invalid(s,-4);unlock(q);return;}
 if(movie!=s->movie||s->movie<0){unlock(q);return;}
 if(ev==Q_EV_EXIT){if(pair(s->phase,Q_PUBLIC_RELEASE,Q_PUBLIC_WAIT)&&s->ack&&s->ack_kind==3)s->pause_exit=true;else invalid(s,-7);unlock(q);return;}
 if(ev==Q_EV_LAYOUT&&a&&n>=5&&a[0]==6){
  if(s->phase==Q_OPEN_WAIT&&a[2]==1000){s->context=1000;s->selected=-1;s->phase=Q_MAP;s->status=2;}
  else if(pair(s->phase,Q_RB_RELEASE,Q_ONLINE_WAIT)&&a[2]==1042){s->context=1042;s->selected=-1;s->ack=true;s->ack_kind=0;}
  else if(pair(s->phase,Q_NAV_RELEASE,Q_NAV_WAIT)&&a[1]==1064&&a[2]==1064&&a[4]==0){s->context=1064;s->selected=a[3];s->ack=true;s->ack_kind=0;}
  else if(s->phase==Q_ONLINE||s->phase==Q_CONTENT||s->phase==Q_FIND_ACK)invalid(s,-4);
 }else if(ev==Q_EV_TRIGGER){
  if(pair(s->phase,Q_HEADER_RELEASE,Q_HEADER_WAIT)&&tuple(a,n,6,1042,0,1064,0)){s->context=1064;s->selected=0;s->ack=true;s->ack_kind=1;}
  else if(pair(s->phase,Q_FIND_RELEASE,Q_FIND_WAIT)&&tuple(a,n,6,1064,14,-1,-1)){s->ack=true;s->ack_kind=2;}
  else if(pair(s->phase,Q_PUBLIC_RELEASE,Q_PUBLIC_WAIT)&&tuple(a,n,6,1064,0,-1,-1)){s->ack=true;s->ack_kind=3;}
  else if(s->phase==Q_ONLINE||s->phase==Q_CONTENT||s->phase==Q_FIND_ACK)invalid(s,-4);
 }
 unlock(q);
}
static void acknowledge(QState *s,uint64_t now){
 if(!s->ack||s->pending_release||s->press!=1||s->release!=1)return;
 if(s->phase==Q_ONLINE_WAIT){s->phase=Q_ONLINE;s->status=7;}
 else if(s->phase==Q_HEADER_WAIT){s->phase=Q_CONTENT;s->status=9;}
 else if(s->phase==Q_NAV_WAIT){s->phase=Q_CONTENT;s->status=9;}
 else if(s->phase==Q_FIND_WAIT){s->phase=Q_FIND_ACK;s->status=17;}
 else if(s->phase==Q_PUBLIC_WAIT){s->phase=Q_WARNING_WAIT;s->status=20;s->warning=(QWarning){0};s->bound_hash=0;s->warning_sampled=false;s->deadline_ms=now+30000;return;}
 else return;
 s->deadline_ms=now+120000;
}
static bool menu_ok(void *engine,const QEngineAPI *a){return a->pause_active(engine)&&a->pause_valid(engine)&&a->frontend_ready(engine)&&a->menu_version(engine)==3123948979u;}
static void sample_warning(QRecovery *q,void *engine,const QEngineAPI *a,uint64_t now,bool force){
 QState before;if(!q_snapshot(q,&before)||!warning_phase(before.phase))return;
 if(!force&&before.warning_sampled&&now-before.last_warning_ms<1000)return;
 QWarning w=a->warning(engine); /* no lock held; engine callback may observe safely */
 if(!lock(q))return;QState *s=&q->s;
 if(s->generation!=before.generation||s->admission_epoch!=before.admission_epoch||!warning_phase(s->phase)){unlock(q);return;}
 if(s->admission_epoch!=atomic_load_explicit(&q->admission_epoch,memory_order_acquire)){invalid(s,-10);unlock(q);return;}
 if(now>s->deadline_ms){invalid(s,-6);unlock(q);return;}
 if(s->phase!=Q_WARNING_WAIT&&(!w.active||!w.ready||w.hash==0||w.hash!=s->warning.hash)){invalid(s,-7);unlock(q);return;}
 s->warning=w;s->last_warning_ms=now;s->warning_sampled=true;
 if(s->phase==Q_WARNING_WAIT&&w.active&&w.ready&&w.hash){s->phase=Q_WARNING_READY;s->status=21;s->deadline_ms=now+120000;}
 unlock(q);
}
void q_primary_tick(QRecovery *q,void *engine,const QEngineAPI *a,uint64_t now,bool loading){
 /* Release always comes first, even when cancellation/lifecycle/loading is pending. */
 QState old;if(!q_snapshot(q,&old))return;
 if(old.pending_release){
  if(!lock(q))return;QState *s=&q->s;
  if(!s->pending_release){unlock(q);return;}
  int control=s->control;bool confirm=control==201&&s->release_to==Q_DONE;uint64_t gen=s->generation;
  s->pending_release=false;if(s->phase!=Q_INVALID)s->phase=(QPhase)s->release_to;unlock(q);
  int result=a->set_next(engine,2,control,0.0f);
  if(!lock(q))return;s=&q->s;
  if(s->generation==gen){if(confirm)s->confirm_release=result;else s->release=result;if(result!=1)s->status=-8;else if(confirm&&s->phase==Q_DONE)s->status=23;}
  unlock(q);
 }
 if(!lock(q))return;QState *s=&q->s;uint64_t epoch=atomic_load_explicit(&q->admission_epoch,memory_order_acquire);
 if(s->phase!=Q_IDLE&&s->phase!=Q_DONE&&s->phase!=Q_INVALID&&(s->admission_epoch!=epoch||now>s->deadline_ms))invalid(s,s->admission_epoch!=epoch?-10:-6);
 acknowledge(s,now);unlock(q);sample_warning(q,engine,a,now,false);
 if(!lock(q))return;s=&q->s;QCommand cmd=s->command;uint64_t requested=s->command_epoch,requested_generation=s->command_generation;uint32_t requested_hash=s->command_hash;s->command=Q_CMD_NONE;unlock(q);
 if(cmd==Q_CMD_NONE)return;
 if(cmd==Q_CANCEL){if(lock(q)){reset(&q->s);unlock(q);}return;}
 if(loading||requested==0||requested!=atomic_load_explicit(&q->admission_epoch,memory_order_acquire)){if(lock(q)){q->s.status=-2;unlock(q);}return;}
 if(cmd==Q_BIND_VISIBLE_QUIT||cmd==Q_CONFIRM_BOUND_QUIT)sample_warning(q,engine,a,now,true);
 bool menu=(cmd==Q_OPEN)?!a->pause_active(engine):(cmd>=Q_RB&&cmd<=Q_PUBLIC_VISIBLE)?menu_ok(engine,a):true;
 bool baseline=(cmd!=Q_PUBLIC_VISIBLE)||!a->warning(engine).active;
 if(!lock(q))return;s=&q->s;
 if(s->generation!=requested_generation||s->command_epoch!=requested||requested!=atomic_load_explicit(&q->admission_epoch,memory_order_acquire)||s->pending_release||!menu||!baseline){s->status=-4;unlock(q);return;}
 if(cmd==Q_OPEN){if(s->phase!=Q_IDLE){s->status=-4;unlock(q);return;}reset(s);s->generation++;s->admission_epoch=requested;s->phase=Q_OPEN_WAIT;s->deadline_ms=now+60000;s->status=1;unlock(q);a->open(engine,0);return;}
 if(s->admission_epoch!=requested||now>s->deadline_ms){invalid(s,-6);unlock(q);return;}
 int control=0;QPhase release=Q_INVALID,wait=Q_INVALID;
 switch(cmd){
 case Q_RB:if(s->phase==Q_MAP){control=206;release=Q_RB_RELEASE;wait=Q_ONLINE_WAIT;}break;
 case Q_HEADER:if(s->phase==Q_ONLINE){control=201;release=Q_HEADER_RELEASE;wait=Q_HEADER_WAIT;}break;
 case Q_DOWN:case Q_UP:case Q_FIND:
  if(s->phase==Q_CONTENT&&s->navigation_count<32&&(cmd!=Q_FIND||s->selected==14)){
   control=cmd==Q_DOWN?187:cmd==Q_UP?188:201;release=cmd==Q_FIND?Q_FIND_RELEASE:Q_NAV_RELEASE;wait=cmd==Q_FIND?Q_FIND_WAIT:Q_NAV_WAIT;s->navigation_count++;
  }break;
 case Q_PUBLIC_VISIBLE:if(s->phase==Q_FIND_ACK&&s->ack_kind==2){control=201;release=Q_PUBLIC_RELEASE;wait=Q_PUBLIC_WAIT;}break;
 case Q_BIND_VISIBLE_QUIT:
  if(s->phase==Q_WARNING_READY&&s->warning.hash==requested_hash&&s->warning.active&&s->warning.ready&&s->warning.hash){s->bound_hash=s->warning.hash;s->phase=Q_WARNING_BOUND;s->status=24;}else s->status=-4;
  unlock(q);return;
 case Q_CONFIRM_BOUND_QUIT:
  if(s->phase==Q_WARNING_BOUND&&s->warning.hash==requested_hash&&s->warning.active&&s->warning.ready&&s->warning.hash&&s->bound_hash==s->warning.hash){control=201;release=Q_CONFIRM_RELEASE;wait=Q_DONE;}break;
 default:break;
 }
 if(!control){s->status=-4;unlock(q);return;}
 s->phase=release;s->release_to=wait;s->control=control;s->pending_release=true;s->ack=false;s->press=s->release=-1;s->deadline_ms=now+30000;s->status=22;
 uint64_t gen=s->generation;unlock(q);int result=a->set_next(engine,2,control,1.0f);
 if(!lock(q))return;s=&q->s;if(s->generation==gen){if(wait==Q_DONE)s->confirm_press=result;else s->press=result;if(result!=1)s->status=-8;}unlock(q);
}
