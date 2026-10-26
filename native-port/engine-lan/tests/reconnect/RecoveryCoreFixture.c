#include "RecoveryCore.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef struct {int control;float value;} Call;
typedef struct {bool active,valid,ready;uint32_t version;int result,opens,gets,n;uint64_t now;bool loading;QWarning warning;Call calls[256];} Fixture;
static void open_menu(void *p,int v){Fixture *f=p;assert(v==0);f->opens++;}
static int set_next(void *p,int g,int c,float v){Fixture *f=p;assert(g==2);assert(c==201||c==206||c==187||c==188);assert(f->n<256);f->calls[f->n++]=(Call){c,v};return f->result;}
static bool active(void *p){return ((Fixture*)p)->active;}
static bool valid(void *p){return ((Fixture*)p)->valid;}
static bool ready(void *p){return ((Fixture*)p)->ready;}
static uint32_t version(void *p){return ((Fixture*)p)->version;}
static QWarning warning(void *p){Fixture *f=p;f->gets++;return f->warning;}
static const QEngineAPI api={open_menu,set_next,active,valid,ready,version,warning};
static QState snap(void){QState s;assert(q_snapshot(&zgta_qa_recovery,&s));return s;}
static void tick(Fixture *f){q_primary_tick(&zgta_qa_recovery,f,&api,f->now,f->loading);}
static void request(Fixture *f,QCommand cmd){assert(q_request(&zgta_qa_recovery,7,cmd));tick(f);}
static void init(Fixture *f){memset(f,0,sizeof *f);f->valid=f->ready=true;f->version=3123948979u;f->result=1;f->now=10000;q_admission_epoch(&zgta_qa_recovery,7);assert(q_request(&zgta_qa_recovery,7,Q_CANCEL));tick(f);}
static void event(QEvent e,int movie,int a,int b,int c,int d,int x){int32_t v[]={a,b,c,d,x};q_observe(&zgta_qa_recovery,e,movie,v,5);}
static void map(Fixture *f){request(f,Q_OPEN);assert(f->opens==1);f->active=true;q_observe(&zgta_qa_recovery,Q_EV_READY,14,NULL,0);event(Q_EV_LAYOUT,14,6,0,1000,-1,1);assert(snap().phase==Q_MAP);}
static void online(Fixture *f){map(f);request(f,Q_RB);event(Q_EV_LAYOUT,14,6,1000,1042,-1,1);tick(f);assert(snap().phase==Q_ONLINE);}
static void content(Fixture *f){online(f);request(f,Q_HEADER);event(Q_EV_TRIGGER,14,6,1042,0,1064,0);tick(f);assert(snap().phase==Q_CONTENT&&snap().selected==0);}
static void select(Fixture *f,QCommand cmd,int item){request(f,cmd);event(Q_EV_LAYOUT,14,6,1064,1064,item,0);tick(f);assert(snap().phase==Q_CONTENT&&snap().selected==item);}
static void find(Fixture *f){content(f);select(f,Q_DOWN,2);select(f,Q_UP,0);select(f,Q_UP,20);select(f,Q_UP,15);select(f,Q_UP,14);request(f,Q_FIND);event(Q_EV_TRIGGER,14,6,1064,14,-1,-1);tick(f);assert(snap().phase==Q_FIND_ACK);}
static void public_owned(Fixture *f){find(f);request(f,Q_PUBLIC_VISIBLE);event(Q_EV_TRIGGER,14,6,1064,0,-1,-1);f->active=f->valid=f->ready=false;f->version=0;q_observe(&zgta_qa_recovery,Q_EV_EXIT,14,NULL,0);tick(f);assert(snap().phase==Q_WARNING_WAIT&&snap().pause_exit);}
static void warning_visible(Fixture *f){public_owned(f);f->warning=(QWarning){true,true,0xfabc1234u};f->now+=1000;tick(f);assert(snap().phase==Q_WARNING_READY);}
static void bound(Fixture *f){warning_visible(f);request(f,Q_BIND_VISIBLE_QUIT);assert(snap().phase==Q_WARNING_BOUND&&snap().bound_hash==0xfabc1234u);}
int main(void){Fixture f;
 init(&f);bound(&f);int before=f.n;request(&f,Q_CONFIRM_BOUND_QUIT);assert(snap().phase==Q_CONFIRM_RELEASE&&snap().confirm_press==1);f.loading=true;f.active=f.valid=f.ready=false;q_admission_epoch(&zgta_qa_recovery,8);tick(&f);assert(f.n==before+2&&f.calls[f.n-1].control==201&&f.calls[f.n-1].value==0&&snap().confirm_release==1);assert(snap().phase==Q_DONE);tick(&f);assert(f.n==before+2);
 init(&f);warning_visible(&f);before=f.n;request(&f,Q_CONFIRM_BOUND_QUIT);assert(f.n==before&&snap().status==-4);
 init(&f);bound(&f);before=f.n;f.warning.hash++;request(&f,Q_CONFIRM_BOUND_QUIT);assert(f.n==before&&snap().phase==Q_INVALID);
 init(&f);bound(&f);before=f.n;f.warning.ready=false;request(&f,Q_CONFIRM_BOUND_QUIT);assert(f.n==before&&snap().phase==Q_INVALID);
 init(&f);bound(&f);before=f.n;f.now+=120001;request(&f,Q_CONFIRM_BOUND_QUIT);assert(f.n==before&&snap().phase==Q_INVALID);
 init(&f);bound(&f);before=f.n;event(Q_EV_TRIGGER,14,6,1064,1,-1,-1);request(&f,Q_CONFIRM_BOUND_QUIT);assert(f.n==before&&snap().phase==Q_INVALID);
 init(&f);bound(&f);request(&f,Q_CONFIRM_BOUND_QUIT);assert(q_request(&zgta_qa_recovery,7,Q_CANCEL));tick(&f);assert(f.calls[f.n-1].value==0&&snap().phase==Q_IDLE);
 init(&f);bound(&f);f.result=0;request(&f,Q_CONFIRM_BOUND_QUIT);tick(&f);before=f.n;request(&f,Q_CONFIRM_BOUND_QUIT);assert(f.n==before&&snap().confirm_press==0&&snap().confirm_release==0);
 init(&f);public_owned(&f);before=f.gets;tick(&f);tick(&f);tick(&f);assert(f.gets==before);f.now+=1000;tick(&f);assert(f.gets==before+1);
 init(&f);find(&f);f.warning=(QWarning){true,true,12};before=f.n;request(&f,Q_PUBLIC_VISIBLE);assert(f.n==before&&snap().phase==Q_FIND_ACK);
 init(&f);content(&f);before=f.n;request(&f,Q_FIND);assert(f.n==before&&snap().status==-4);
 init(&f);online(&f);request(&f,Q_HEADER);event(Q_EV_TRIGGER,13,6,1042,0,1064,0);tick(&f);before=f.n;request(&f,Q_DOWN);assert(f.n==before&&snap().phase==Q_HEADER_WAIT);
 init(&f);online(&f);request(&f,Q_HEADER);event(Q_EV_TRIGGER,14,6,1042,1,1064,0);tick(&f);assert(snap().phase==Q_HEADER_WAIT);
 init(&f);online(&f);request(&f,Q_HEADER);q_admission_epoch(&zgta_qa_recovery,8);tick(&f);assert(f.calls[f.n-1].value==0&&snap().phase==Q_INVALID);
 init(&f);assert(q_request(&zgta_qa_recovery,7,Q_OPEN));assert(!q_request(&zgta_qa_recovery,7,Q_OPEN));tick(&f);assert(f.opens==1);
 init(&f);assert(!q_request(&zgta_qa_recovery,8,Q_OPEN));assert(!q_request(&zgta_qa_recovery,0,Q_OPEN));
 init(&f);map(&f);f.version=0;before=f.n;request(&f,Q_RB);assert(f.n==before&&snap().phase==Q_MAP);
 init(&f);map(&f);request(&f,Q_RB);f.now+=30001;tick(&f);assert(f.calls[f.n-1].value==0&&snap().phase==Q_INVALID);
 init(&f);content(&f);for(int i=0;i<32;i++)select(&f,Q_UP,15);before=f.n;request(&f,Q_UP);assert(f.n==before&&snap().navigation_count==32);
 puts("Standalone provisional native core:19 flow/ownership/ABI-boundary parity scenarios PASS; no engine/app build or real recovery claim");return 0;
}
