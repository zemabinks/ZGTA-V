/* Local engine-LAN adaptation of mempage4k/glue5 online/cloud/stats behavior.
 * Exact interface/build provenance: ../app/Tests/glue5_engine_lan_contract.json.
 * No network, filesystem, generic vtable casts or existing-save access here.
 */
#include "ZemaOnlineHost.h"
#include "OnlineComplete.h"
#include "ZemaProfile.h"
#include "ZemaLanBackend.h"
#include <stdatomic.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <pthread.h>

static ZemaOnlineHost host;
static atomic_int installed, interfaces;
static atomic_uint new_slots;
static atomic_uint_fast64_t last_session_observation = ATOMIC_VAR_INIT(UINT64_MAX);
static _Thread_local unsigned in_stats;
static _Thread_local bool missing;
typedef struct { uint8_t* base; uint64_t size; } Memory;
static Memory memory(void* i) { Memory m={0}; if(atomic_load(&installed)==2)m.base=host.memory(i,&m.size);return m; }
static bool range(Memory m,uint64_t p,uint64_t n) {return m.base&&p<=m.size&&n<=m.size-p;}
static uint64_t readn(Memory m,uint64_t p,size_t n) {uint64_t v=0;if(range(m,p,n))memcpy(&v,m.base+p,n);return v;}
static bool put(Memory m,uint64_t p,uint64_t v,size_t n) {if(!range(m,p,n))return false;memcpy(m.base+p,&v,n);return true;}
static bool text(Memory m,uint64_t p,char* out,size_t cap) {
  if(!p||!range(m,p,1))return false;
  for(size_t n=0;n<cap;n++){if(!range(m,p,n+1))return false;out[n]=(char)m.base[p+n];if(!out[n])return true;}return false;
}
static bool write_text(Memory m,uint64_t p,const char* text,size_t cap) {
  if(!cap||!range(m,p,cap))return false;size_t n=strlen(text);if(n>=cap)n=cap-1;memcpy(m.base+p,text,n);m.base[p+n]=0;return true;
}
int ZemaOnlineInstallHost(const ZemaOnlineHost* h,size_t n) {
  if(!h||n!=sizeof(*h)||h->version!=1||!h->memory||!h->allocate||!h->release||!h->prepare_interfaces||!h->commit_profile||!ZemaProfileReady()||!ZEMA_ONLINE_COMPLETE(h))return 0;
  int expected=0;if(!atomic_compare_exchange_strong(&installed,&expected,1))return 0;
  host=*h;atomic_store(&installed,2);return 1;
}
int ZemaOnlineConfigured(void){return atomic_load(&installed)==2;}
int ZemaOnlineInterfacesReady(void){return atomic_load(&interfaces)==2;}
#define O(name,...) host.originals.name(__VA_ARGS__)
uint32_t ZemaOnline_rl_gamer_handle(void* i,uint64_t p) {
  Memory m=memory(i);if(!ZemaProfileReady()||!range(m,p,10))return 0;
  put(m,p,ZemaProfileId(),8);put(m,p+8,3,1);put(m,p+9,0,1);return 1;
}
uint32_t ZemaOnline_rl_offline_name(void* i,uint64_t p){Memory m=memory(i);if(!range(m,p,17))return 0;return ZemaProfileName(m.base+p,17)>=0;}
uint32_t ZemaOnline_rl_pc_initialized(void* i){(void)i;return 0;}
void ZemaOnline_live_manager_init(void* i,uint32_t mode){
  if(!ZemaOnlineConfigured())return;
  if(atomic_load(&interfaces)!=2){int expected=0;if(!atomic_compare_exchange_strong(&interfaces,&expected,1))return;
    if(!host.prepare_interfaces(i)){atomic_store(&interfaces,0);return;}atomic_store(&interfaces,2);}
  O(live_manager_init,i,mode);ZemaOnline_populate_store_data(i);
}
/* Read-only parity with browser session diagnostics. Pinned engine readers:
 * NetworkInterface::IsSessionEstablished (83019) and GetNumPlayers (54857).
 * Local state 5 does not prove that another player's entity synchronized.
 */
static void observe_session(void* i){
  Memory m=memory(i);if(!range(m,29044456,8)||!range(m,28504084,4))return;
  uint64_t p=readn(m,29044456,8);int32_t state=-1;
  if(p)state=p<=UINT64_MAX-99916&&range(m,p+99916,4)?(int32_t)readn(m,p+99916,4):-2;
  int32_t players=(int32_t)readn(m,28504084,4);
  uint64_t value=((uint64_t)(uint32_t)state<<32)|(uint32_t)players;
  if(atomic_exchange(&last_session_observation,value)!=value)fprintf(stderr,"[session] native-state/players %d/%d (observation only)\n",state,players);
}
void ZemaOnline_live_manager_update(void* i,uint32_t mode){if(!ZemaOnlineInterfacesReady())return;ZemaLanNetworkUp(i);O(live_manager_update,i,mode);ZemaLanNetworkUp(i);observe_session(i);}
void ZemaOnline_bail_on_multiplayer(void* i,uint32_t why,uint32_t context){if(why!=2||context!=0x3001)O(bail_on_multiplayer,i,why,context);}
uint32_t ZemaOnline_presence_online(void* i,uint32_t index){return index==0?1:O(presence_online,i,index);}
uint32_t ZemaOnline_ros_privilege(void* i,uint64_t credentials,uint32_t id){(void)i;(void)credentials;return id<32&&((0x6fef7fu>>id)&1);}
uint32_t ZemaOnline_ros_privilege_end_date(void* i,uint64_t c,uint32_t id,uint64_t ends,uint64_t date){(void)i;(void)c;(void)id;(void)ends;(void)date;return 0;}
uint32_t ZemaOnline_profile_setting_int(void* i,uint64_t p,uint32_t id){return id==903?1:O(profile_setting_int,i,p,id);}
uint32_t ZemaOnline_can_access_network_features(void* i,uint32_t area,uint64_t code){(void)area;return !code||put(memory(i),code,0,4);}
uint32_t ZemaOnline_can_enter_multiplayer(void* i,uint64_t session){
  if(!ZemaOnlineInterfacesReady()||!ZemaLanTransportReady())return 0;
  Memory m=memory(i);if(session>UINT64_MAX-99916||!range(m,session+99916,4)||!range(m,29309000,2)||!range(m,23275800,4))return 0;
  return O(can_enter_multiplayer,i,session)||(readn(m,29309000,1)&1 && !readn(m,29309001,1)&&!readn(m,23275800,4)&&!readn(m,session+99916,4));
}
void ZemaOnline_populate_store_data(void* i){Memory m=memory(i);if(!range(m,29308996,7))return;put(m,29308996,2,4);put(m,29309000,1,2);put(m,29309002,0,1);}
uint32_t ZemaOnline_photo_to_jpeg(void* i,uint64_t out,uint64_t size,uint32_t max,uint64_t pixels,uint32_t width,uint32_t height,uint32_t pitch,uint64_t photo){
  (void)out;(void)max;(void)pixels;(void)width;(void)height;(void)pitch;(void)photo;put(memory(i),size,0,4);return 0;
}
#define NATIVE_RESULT(name,value) void ZemaOnline_##name(void* i,uint64_t info){O(name,i,info);Memory m=memory(i);if(range(m,info,8))put(m,readn(m,info,8),value,4);}
NATIVE_RESULT(profanity_valid,1)
NATIVE_RESULT(profanity_pending,0)
NATIVE_RESULT(profanity_status,0)
NATIVE_RESULT(savemigration_mp_enabled,0)
NATIVE_RESULT(bad_pack_order,0)
/* Exact-byte script patches. No mismatching script page is written. */
static bool script_patch(Memory m,uint64_t pages,uint32_t size,uint32_t at,const uint8_t* old,const uint8_t* next,size_t n){
  if(at>size||n>size-at||at%0x4000+n>0x4000||pages>UINT64_MAX-(at/0x4000)*8)return false;
  uint64_t row=pages+(at/0x4000)*8;if(!range(m,row,8))return false;uint64_t base=readn(m,row,8);
  if(!base||base>UINT64_MAX-at%0x4000)return false;uint64_t code=base+at%0x4000;
  if(!range(m,code,n)||memcmp(m.base+code,old,n))return false;memcpy(m.base+code,next,n);return true;
}
uint64_t ZemaOnline_script_program_loaded(void* i,uint64_t this,uint64_t rsc){
  uint64_t result=O(script_program_loaded,i,this,rsc);Memory m=memory(i);char name[64];
  if(!range(m,this,104)||!text(m,readn(m,this+96,8),name,sizeof name)||strcmp(name,"MainTransition"))return result;
  uint64_t pages=readn(m,this+16,8);uint32_t size=(uint32_t)readn(m,this+28,4);
  const uint8_t a[]={0x2c,1,3,0xab},b[]={113,0,0,0};
  const uint8_t c[]={0x73,0x64,0x7c,0xde,0x12,0x66,0x2c,8,3,0x79},d[]={0x2c,0,0,0xf9,0,0,0,0,0,0};
  script_patch(m,pages,size,2510677,a,b,sizeof a);script_patch(m,pages,size,2504003,c,d,sizeof c);return result;
}
uint32_t ZemaOnline_xml_bool_attribute(void* i,uint64_t e,uint64_t n,uint32_t d){return n==1596083?0:O(xml_bool_attribute,i,e,n,d);}
/* Scoped engine flag, restored for nested operations. The engine owns ordering. */
#define LAN_BEGIN Memory m=memory(i);if(!range(m,13346752,8))return;uint64_t lan=readn(m,13346752,8);put(m,13346752,0,8)
#define LAN_BEGIN_RESULT Memory m=memory(i);if(!range(m,13346752,8))return 0;uint64_t lan=readn(m,13346752,8);put(m,13346752,0,8)
#define LAN_END m=memory(i);put(m,13346752,lan,8)
void ZemaOnline_stats_init(void* i,uint32_t mode){LAN_BEGIN;O(stats_init,i,mode);LAN_END;}
void ZemaOnline_stats_update(void* i){LAN_BEGIN;O(stats_update,i);LAN_END;if(range(m,25461316,4))put(m,25461316,readn(m,25461316,4)&~atomic_load(&new_slots),4);}
uint32_t ZemaOnline_stats_queue_load(void* i){LAN_BEGIN_RESULT;uint32_t r=O(stats_queue_load,i);LAN_END;return r;}
void ZemaOnline_stats_queue_save(void* i){LAN_BEGIN;O(stats_queue_save,i);LAN_END;}
uint32_t ZemaOnline_stats_save(void* i,uint32_t k,uint32_t s,uint32_t t,uint32_t r){LAN_BEGIN_RESULT;uint32_t v=O(stats_save,i,k,s,t,r);LAN_END;return v;}
uint32_t ZemaOnline_stats_load(void* i,uint32_t k){LAN_BEGIN_RESULT;uint32_t r=O(stats_load,i,k);LAN_END;return r;}
uint32_t ZemaOnline_stats_load_failed(void* i,uint32_t slot){uint32_t r=O(stats_load_failed,i,slot);return slot<32&&(atomic_load(&new_slots)&(1u<<slot))?0:r;}
uint32_t ZemaOnline_cloud_available(void* i,uint32_t p){(void)i;(void)p;return ZemaProfileReady();}
uint32_t ZemaOnline_profile_stats_failed(void* i,uint64_t code){(void)i;(void)code;return 0;}
uint32_t ZemaOnline_profile_stats_synced(void* i,uint32_t kind){(void)i;(void)kind;return ZemaProfileReady();}
uint32_t ZemaOnline_mpstats_load_update(void* i,uint64_t op){in_stats++;uint32_t r=O(mpstats_load_update,i,op);in_stats--;return r;}
uint32_t ZemaOnline_mpstats_save_update(void* i,uint64_t op){in_stats++;uint32_t r=O(mpstats_save_update,i,op);in_stats--;return r;}
uint32_t ZemaOnline_ros_credentials_valid(void* i,uint64_t c){return in_stats?1:O(ros_credentials_valid,i,c);}
static int slot(const char* name){size_t n=strlen(name);if(n<6||strcmp(name+n-5,".save"))return -1;size_t at=n-5,end=at;while(at&&name[at-1]>='0'&&name[at-1]<='9')at--;if(at==end||end-at>10)return -1;unsigned long v=strtoul(name+at,NULL,10);return v<32?(int)v:-1;}
static bool finish(Memory m,uint64_t p,uint32_t code,uint32_t result){if(!p)return true;if(!range(m,p,8))return false;put(m,p+4,result,4);put(m,p,code,4);return true;}
uint32_t ZemaOnline_post_member_file(void* i,uint32_t gamer,uint32_t service,uint64_t path,uint64_t data,uint32_t size,uint64_t info,uint64_t allocator,uint64_t status){
  (void)gamer;(void)service;(void)info;(void)allocator;Memory m=memory(i);char key[515]="f:";
  if((status&&!range(m,status,8))||size>1048576||!range(m,data,size)||!text(m,path,key+2,513)){finish(m,status,2,0);return 1;}
  int ok=ZemaProfileWrite((uint8_t*)key,strlen(key),m.base+data,size)&&host.commit_profile(i);int s=slot(key+2);
  if(ok&&s>=0)atomic_fetch_and(&new_slots,~(1u<<s));finish(m,status,ok?3:2,0);return 1;
}
uint32_t ZemaOnline_get_member_file(void* i,uint32_t gamer,uint64_t member,uint32_t service,uint64_t path,uint32_t security,uint64_t since,uint32_t options,uint64_t device,uint64_t handle,uint64_t info,uint64_t allocator,uint64_t status){
  (void)gamer;(void)member;(void)service;(void)security;(void)since;(void)options;(void)info;(void)allocator;
  Memory m=memory(i);char key[515]="f:";if((status&&!range(m,status,8))||device!=8638336||!text(m,path,key+2,513)){finish(m,status,2,0);return 1;}
  /* Bounded temporary host buffer; the engine allocator still owns append input. */
  uint8_t* bytes=malloc(1048576);if(!bytes){finish(m,status,2,0);return 1;}
  int count=ZemaProfileRead((uint8_t*)key,strlen(key),bytes,1048576);
  if(count<0){free(bytes);int s=slot(key+2);if(count==-1&&s>=0)atomic_fetch_or(&new_slots,1u<<s);finish(m,status,2,count==-1?404:0);return 1;}
  uint64_t at=host.allocate(i,count?count:1);m=memory(i);
  if(!at||!range(m,at,(uint32_t)count)){if(at)host.release(i,at);free(bytes);finish(m,status,2,0);return 1;}
  memcpy(m.base+at,bytes,(size_t)count);free(bytes);uint32_t ok=O(grow_buffer_append,i,handle,at,(uint32_t)count);host.release(i,at);finish(memory(i),status,ok?3:2,0);return 1;
}
uint32_t ZemaOnline_ugc_query_content(void* i,uint32_t g,uint32_t c,uint64_t q,uint64_t p,uint32_t o,uint32_t n,uint64_t f,uint64_t t,uint64_t d,uint64_t a,uint64_t s){(void)i;(void)g;(void)c;(void)q;(void)p;(void)o;(void)n;(void)f;(void)t;(void)d;(void)a;(void)s;return 0;}
uint32_t ZemaOnline_grow_buffer_append(void* i,uint64_t b,uint64_t p,uint32_t n){return O(grow_buffer_append,i,b,p,n);}
void ZemaOnline_grow_buffer_file_name(void* i,uint64_t p,uint32_t size,uint64_t buffer){char name[40];snprintf(name,sizeof name,"growbuffer:%llx",(unsigned long long)buffer);write_text(memory(i),p,name,size);}
uint32_t ZemaOnline_stat_find(void* i,uint64_t id,uint64_t iter){uint32_t r=O(stat_find,i,id,iter);missing=!r;return r;}
/* Bounded missing-packed-key cache, invalidated by the actual engine map.
 * Avoids repeated formatting/error output for ~27000 absent packed stats. */
typedef struct {uint32_t index,slot,hash;bool used;} Miss;
static Miss misses[65536];static uint32_t miss_count;
static uint64_t map_entries;static uint16_t map_count;static uint8_t map_sorted;
static pthread_mutex_t miss_lock=PTHREAD_MUTEX_INITIALIZER;
static void miss_map(Memory m){
  uint64_t entries=readn(m,25461184,8);uint16_t count=(uint16_t)readn(m,25461192,2);uint8_t sorted=(uint8_t)readn(m,25461176,1);
  if(entries!=map_entries||count!=map_count||sorted!=map_sorted){memset(misses,0,sizeof misses);miss_count=0;map_entries=entries;map_count=count;map_sorted=sorted;}
}
static Miss* miss_entry(uint32_t index,uint32_t slot){
  uint32_t at=(index*0x9e3779b1u+slot*0x85ebca6bu)&65535;
  for(unsigned n=0;n<65536;n++,at=(at+1)&65535){Miss* e=misses+at;if(!e->used||(e->index==index&&e->slot==slot))return e;}return NULL;
}
uint32_t ZemaOnline_packed_key(void* i,uint64_t id,uint32_t index,uint32_t slot){
  Memory m=memory(i);if(!range(m,id,4)||!range(m,25461176,18))return 0;
  pthread_mutex_lock(&miss_lock);miss_map(m);Miss* e=miss_entry(index,slot);
  if(e&&e->used){uint32_t hash=e->hash;pthread_mutex_unlock(&miss_lock);missing=true;put(m,id,hash,4);return 0;}
  uint64_t before_entries=map_entries;uint16_t before_count=map_count;uint8_t before_sorted=map_sorted;pthread_mutex_unlock(&miss_lock);
  uint32_t r=O(packed_key,i,id,index,slot);missing=!r;
  if(!r){m=memory(i);pthread_mutex_lock(&miss_lock);miss_map(m);
    if(before_entries==map_entries&&before_count==map_count&&before_sorted==map_sorted&&miss_count<32768){e=miss_entry(index,slot);if(e&&!e->used){*e=(Miss){index,slot,(uint32_t)readn(m,id,4),true};miss_count++;}}
    pthread_mutex_unlock(&miss_lock);}
  return r;
}
static void hash_key(char* out,uint32_t h){snprintf(out,32,"h%08x",h);}
static void packed_name(char* out,uint32_t index,uint32_t slot){snprintf(out,32,"p%d:%u",(int32_t)slot,index);}
static uint64_t stat_get(const char* key){return ZemaProfileStat((const uint8_t*)key,strlen(key));}
static uint32_t stat_put(const char* key,uint64_t bits){return ZemaProfileWrite((const uint8_t*)key,strlen(key),(const uint8_t*)&bits,8);}
static uint64_t mask(uint32_t bits){return bits>=64?UINT64_MAX:((1ull<<bits)-1);}
uint32_t ZemaOnline_packed_get(void* i,uint64_t out,uint32_t index,uint32_t slot){missing=false;uint32_t r=O(packed_get,i,out,index,slot);if(!missing)return r;char k[32];packed_name(k,index,slot);return put(memory(i),out,stat_get(k),4);}
void ZemaOnline_packed_set(void* i,uint32_t value,uint32_t index,uint32_t slot){missing=false;O(packed_set,i,value,index,slot);if(missing){char k[32];packed_name(k,index,slot);stat_put(k,(uint64_t)(int64_t)(int32_t)value);}}
#define STAT_GET(name,normalize) uint32_t ZemaOnline_##name(void* i,uint32_t hash,uint64_t out,uint32_t player){missing=false;uint32_t r=O(name,i,hash,out,player);if(!missing)return r;char k[32];hash_key(k,hash);uint64_t v=stat_get(k);return put(memory(i),out,(normalize),4);}
STAT_GET(stat_get_int,v)
STAT_GET(stat_get_float,v)
STAT_GET(stat_get_bool,v!=0)
uint32_t ZemaOnline_stat_get_masked_int(void* i,uint32_t h,uint64_t out,uint32_t start,uint32_t bits,uint32_t p){missing=false;uint32_t r=O(stat_get_masked_int,i,h,out,start,bits,p);if(!missing)return r;char k[32];hash_key(k,h);return put(memory(i),out,(stat_get(k)>>(start&63))&mask(bits),4);}
#define STAT_SET(name,expr) uint32_t ZemaOnline_##name(void* i,uint32_t hash,uint32_t value,uint32_t save){missing=false;uint32_t r=O(name,i,hash,value,save);if(!missing)return r;char k[32];hash_key(k,hash);return stat_put(k,(expr));}
STAT_SET(stat_set_int,(uint64_t)(int64_t)(int32_t)value)
STAT_SET(stat_set_bool,value!=0)
uint32_t ZemaOnline_stat_set_float(void* i,uint32_t h,float value,uint32_t save){missing=false;uint32_t r=O(stat_set_float,i,h,value,save);if(!missing)return r;char k[32];hash_key(k,h);uint32_t v;memcpy(&v,&value,4);return stat_put(k,v);}
uint32_t ZemaOnline_stat_set_masked_int(void* i,uint32_t h,uint32_t value,uint32_t start,uint32_t bits,uint32_t save){missing=false;uint32_t r=O(stat_set_masked_int,i,h,value,start,bits,save);if(!missing)return r;char k[32];hash_key(k,h);uint64_t field=mask(bits)<<(start&63);return stat_put(k,(stat_get(k)&~field)|(((uint64_t)value<<(start&63))&field));}
void ZemaOnline_stat_delete_slot(void* i,uint32_t slot){O(stat_delete_slot,i,slot);ZemaProfileDeleteSlot((int32_t)slot);}
