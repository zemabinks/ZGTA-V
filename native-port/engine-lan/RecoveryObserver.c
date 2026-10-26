#include "RecoveryObserver.h"
#include <limits.h>
#include <math.h>
#include <string.h>
static bool text_eq(const uint8_t *base,uint64_t size,uint64_t p,const char *want){
 if(!base||!p||p>size||size-p<97)return false;
 for(unsigned i=0;i<97;i++){unsigned char b=base[p+i];if(b!=(unsigned char)want[i])return false;if(!b)return true;if(b<32||b>126)return false;}
 return false;
}
void q_original_preserving_frontend(QRecovery *q,void *engine,QOriginalFrontend original,QMemory memory,
 uint32_t movie,uint64_t method,uint64_t args,uint32_t count){
 original(engine,movie,method,args,count); /* original trap/nonlocal exit must propagate */
 uint64_t size=0;const uint8_t *base=memory(engine,&size);if(!base||movie>49)return;
 QEvent ev;
 if(text_eq(base,size,method,"PAUSE_MENU_READY_TO_RENDER")){q_observe(q,Q_EV_READY,(int)movie,NULL,0);return;}
 if(text_eq(base,size,method,"EXIT_PAUSE_MENU")){q_observe(q,Q_EV_EXIT,(int)movie,NULL,0);return;}
 if(text_eq(base,size,method,"LAYOUT_CHANGED"))ev=Q_EV_LAYOUT;
 else if(text_eq(base,size,method,"TRIGGER_PAUSE_MENU_EVENT"))ev=Q_EV_TRIGGER;
 else return;
 if(count<5||count>8||!args||args%8||args>size||(uint64_t)count*24>size-args)return;
 if(ev==Q_EV_TRIGGER&&count!=5)return;
 int32_t a[5];for(unsigned i=0;i<5;i++){
  uint32_t type;double value;memcpy(&type,base+args+24*i+8,4);memcpy(&value,base+args+24*i+16,8);
  if((type&143u)!=3||!isfinite(value)||value<INT32_MIN||value>INT32_MAX||trunc(value)!=value)return;
  a[i]=(int32_t)value;
 }
 q_observe(q,ev,(int)movie,a,ev==Q_EV_LAYOUT?count:5);
}
