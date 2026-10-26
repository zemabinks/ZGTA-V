#include "NativeThreadPolicy.h"
#include <assert.h>
#include <stdio.h>
static qos_class_t current(void){qos_class_t q;assert(!pthread_get_qos_class_np(pthread_self(),&q,NULL));return q;}
static void *check(void *unused){
 (void)unused;
 assert(!pthread_set_qos_class_self_np(QOS_CLASS_USER_INITIATED,0));
 qos_class_t prior=current();
 assert(!pg_engine_apply_thread_policy("[RAGE] RenderThread"));assert(current()==prior);
 assert(!pg_engine_apply_thread_policy("[GTA] ControlMgr Update Thread extra"));assert(current()==prior);
 assert(!pg_engine_apply_thread_policy("[GTA] ControlMgr Update Thread"));assert(current()==QOS_CLASS_USER_INTERACTIVE);
 return NULL;
}
int main(void){pthread_t t;assert(!pthread_create(&t,NULL,check,NULL));assert(!pthread_join(t,NULL));puts("PASS: production control policy applies actual Darwin QoS only to exact thread name");return 0;}
