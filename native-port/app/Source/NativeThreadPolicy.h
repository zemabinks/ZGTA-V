/* Bounded RAGE thread-name decoding; Glue5 threads.rs b5d1faf (GPL-3.0). */
#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
static inline bool pg_engine_thread_name(const void *memory,uint64_t limit,uint64_t argument,char name[49]){
 name[0]=0;if(!memory||!argument||argument>limit||limit-argument<72)return false;
 const unsigned char *s=(const unsigned char *)memory+argument+24;
 for(unsigned i=0;i<48;i++){
  unsigned char c=s[i];if(!c){if(i<3){name[0]=0;return false;}name[i]=0;return true;}
  if(c<32||c>126){name[0]=0;return false;}name[i]=(char)c;
 }
 name[0]=0;return false;
}
static inline bool pg_engine_frame_control(const char *name){return strcmp(name,"[GTA] ControlMgr Update Thread")==0;}

#if defined(__APPLE__)
#include <pthread.h>
static inline int pg_engine_apply_thread_policy(const char *name){
 return pg_engine_frame_control(name)?pthread_set_qos_class_self_np(QOS_CLASS_USER_INTERACTIVE,0):0;
}
#endif
