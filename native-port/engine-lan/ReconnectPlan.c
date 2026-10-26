#include "ReconnectPlan.h"
static bool lock(RReconnect *r){return !atomic_flag_test_and_set_explicit(&r->lock,memory_order_acquire);}
static void unlock(RReconnect *r){atomic_flag_clear_explicit(&r->lock,memory_order_release);}
static bool active(RStep step){return step>=R_REQUESTED&&step<=R_FIND;}
bool r_start(RReconnect *r,uint64_t ticket,uint64_t generation){
 if(!ticket||!lock(r))return false;
 bool ok=!active(r->step);
 if(ok){r->step=R_REQUESTED;r->ticket=ticket;r->generation=generation;r->deadline_ms=0;r->status=1;r->awaiting=false;r->open_adopted=false;atomic_store_explicit(&r->cancelled,false,memory_order_release);}
 unlock(r);return ok;
}
bool r_snapshot(RReconnect *r,RSnapshot *out){if(!out||!lock(r))return false;*out=(RSnapshot){r->step,r->status,r->ticket,r->generation};unlock(r);return true;}
static void fail(RReconnect *r,int status){r->step=R_FAILED;r->status=status;r->awaiting=false;}
void r_cancel(RReconnect *r){atomic_store_explicit(&r->cancelled,true,memory_order_release);}
static bool enqueue(RReconnect *r,QRecovery *q,QCommand cmd,RStep next,QPhase phase,int selected){
 if(!q_request_checked(q,r->ticket,r->generation,cmd,0)){fail(r,-4);return false;}
 r->step=next;r->awaiting=true;r->expected_phase=phase;r->expected_selected=selected;return true;
}
void r_tick(RReconnect *r,QRecovery *q,uint64_t now,bool loading){
 /* No game API and no raw game memory accesses; command validation stays in the core. */
 if(!lock(r))return;
 if(!active(r->step)){unlock(r);return;}
 if(atomic_load_explicit(&r->cancelled,memory_order_acquire)){fail(r,-11);unlock(r);return;}
 QState s;if(!q_snapshot(q,&s)){unlock(r);return;}
 if(!now||loading||r->ticket!=atomic_load_explicit(&q->admission_epoch,memory_order_acquire)){fail(r,-2);unlock(r);return;}
 if(!r->deadline_ms)r->deadline_ms=now+120000;
 if(now>r->deadline_ms){fail(r,-6);unlock(r);return;}
 if(r->step==R_REQUESTED){
  if(s.generation!=r->generation||s.pending_release||s.command!=Q_CMD_NONE||
      (s.phase!=Q_IDLE&&s.phase!=Q_DONE&&s.phase!=Q_INVALID)){fail(r,-4);unlock(r);return;}
  if(s.phase!=Q_IDLE){enqueue(r,q,Q_CANCEL,R_CANCELLING,Q_IDLE,-1);unlock(r);return;}
  enqueue(r,q,Q_OPEN,R_OPEN,Q_MAP,-1);unlock(r);return;
 }
 if(s.phase==Q_INVALID||s.status<0){fail(r,s.status<0?s.status:-4);unlock(r);return;}
 if(r->step==R_OPEN&&!r->open_adopted){
  /* Open alone increments generation exactly once; no other owner may replace it. */
  if(s.generation==r->generation){unlock(r);return;}
  if(s.generation!=r->generation+1){fail(r,-4);unlock(r);return;}
  r->generation=s.generation;r->open_adopted=true;
 }
 if(s.generation!=r->generation){fail(r,-4);unlock(r);return;}
 if(s.pending_release||s.command!=Q_CMD_NONE){unlock(r);return;}
 if(r->awaiting){
  if(s.phase!=r->expected_phase){unlock(r);return;}
  if(r->expected_selected>=0&&s.selected!=r->expected_selected){fail(r,-4);unlock(r);return;}
  r->awaiting=false;
 }
 switch(r->step){
 case R_CANCELLING:enqueue(r,q,Q_OPEN,R_OPEN,Q_MAP,-1);break;
 case R_OPEN:enqueue(r,q,Q_RB,R_MAP,Q_ONLINE,-1);break;
 case R_MAP:enqueue(r,q,Q_HEADER,R_ONLINE,Q_CONTENT,0);break;
 case R_ONLINE:enqueue(r,q,Q_UP,R_ROW20,Q_CONTENT,20);break;
 case R_ROW20:enqueue(r,q,Q_UP,R_ROW15,Q_CONTENT,15);break;
 case R_ROW15:enqueue(r,q,Q_UP,R_ROW14,Q_CONTENT,14);break;
 case R_ROW14:enqueue(r,q,Q_FIND,R_FIND,Q_FIND_ACK,14);break;
 case R_FIND:
  if(s.ack_kind!=2||s.context!=1064||s.movie<0||s.movie>=50){fail(r,-4);break;}
  /* Find's trigger proves dispatch, NOT Public submenu render/selection readiness.
     Never enqueue Q_PUBLIC_VISIBLE, Bind or Confirm from this planner. */
  r->step=R_CONTINUE_IN_GTA;r->status=2;break;
 default:fail(r,-4);break;
 }
 unlock(r);
}
