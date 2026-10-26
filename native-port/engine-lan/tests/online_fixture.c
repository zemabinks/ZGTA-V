/* Synthetic originals: no game code or application data. */
#include "ZemaOnlineHost.h"
#include "ZemaProfile.h"
#include "ZemaLanBackend.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdatomic.h>
extern int32_t FixtureCommit(void);
static uint8_t* bytes;static uint8_t* retired; static unsigned calls,prepared,commits; static int found,fail_commit;
static uint32_t nested,credential_checks,packed_calls;
static uint8_t* mem(void* i,uint64_t* size){(void)i;*size=33554432;return bytes;}
static uint64_t alloc(void* i,uint64_t n){(void)i;return n<=1048576?31000000:0;}
static void release(void* i,uint64_t p){(void)i;assert(p==31000000);}
static int prepare(void* i){(void)i;prepared++;return 1;}
static int commit(void* i){(void)i;commits++;return fail_commit?0:FixtureCommit();}
static void put64(size_t at,uint64_t n){memcpy(bytes+at,&n,8);}
static void put32(size_t at,uint32_t n){memcpy(bytes+at,&n,4);}
static uint32_t u32(size_t at){uint32_t n;memcpy(&n,bytes+at,4);return n;}
static uint64_t u64(size_t at){uint64_t n;memcpy(&n,bytes+at,8);return n;}
static uint32_t o_rl_gamer_handle(void* i, uint64_t a0){(void)i;(void)a0;return 77;}
static uint32_t o_rl_offline_name(void* i, uint64_t a0){(void)i;(void)a0;return 77;}
static uint32_t o_rl_pc_initialized(void* i){(void)i;return 77;}
static void o_live_manager_init(void* i, uint32_t a0){(void)i;(void)a0;assert(prepared==1);calls++;put32(29309000,0);}
static void o_live_manager_update(void* i, uint32_t a0){(void)i;(void)a0;calls++;}
static uint32_t o_presence_online(void* i, uint32_t a0){(void)i;(void)a0;return 77;}
static void o_bail_on_multiplayer(void* i, uint32_t a0, uint32_t a1){(void)i;(void)a0;(void)a1;calls++;}
static uint32_t o_ros_privilege(void* i, uint64_t a0, uint32_t a1){(void)i;(void)a0;(void)a1;return 77;}
static uint32_t o_ros_privilege_end_date(void* i, uint64_t a0, uint32_t a1, uint64_t a2, uint64_t a3){(void)i;(void)a0;(void)a1;(void)a2;(void)a3;return 77;}
static uint32_t o_profile_setting_int(void* i, uint64_t a0, uint32_t a1){(void)i;(void)a0;(void)a1;return 77;}
static uint32_t o_can_access_network_features(void* i, uint32_t a0, uint64_t a1){(void)i;(void)a0;(void)a1;return 77;}
static uint32_t o_can_enter_multiplayer(void* i, uint64_t a0){(void)i;(void)a0;return 77;}
static void o_populate_store_data(void* i){(void)i;calls++;}
static uint32_t o_photo_to_jpeg(void* i, uint64_t a0, uint64_t a1, uint32_t a2, uint64_t a3, uint32_t a4, uint32_t a5, uint32_t a6, uint64_t a7){(void)i;(void)a0;(void)a1;(void)a2;(void)a3;(void)a4;(void)a5;(void)a6;(void)a7;return 77;}
static uint64_t o_script_program_loaded(void* i, uint64_t a0, uint64_t a1){(void)i;(void)a0;(void)a1;return a0;}
static void o_profanity_valid(void* i, uint64_t a0){(void)i;(void)a0;calls++;}
static void o_profanity_pending(void* i, uint64_t a0){(void)i;(void)a0;calls++;}
static void o_profanity_status(void* i, uint64_t a0){(void)i;(void)a0;calls++;}
static void o_savemigration_mp_enabled(void* i, uint64_t a0){(void)i;(void)a0;calls++;}
static void o_bad_pack_order(void* i, uint64_t a0){(void)i;(void)a0;calls++;}
static uint32_t o_xml_bool_attribute(void* i, uint64_t a0, uint64_t a1, uint32_t a2){(void)i;(void)a0;(void)a1;(void)a2;return 77;}
static void o_stats_init(void* i, uint32_t a0){(void)i;(void)a0;assert(u64(13346752)==0);calls++;ZemaOnline_stats_queue_load(i);assert(u64(13346752)==0);retired=bytes;bytes=malloc(33554432);assert(bytes);memcpy(bytes,retired,33554432);}
static void o_stats_update(void* i){(void)i;assert(u64(13346752)==0);calls++;}
static uint32_t o_stats_queue_load(void* i){(void)i;assert(u64(13346752)==0);calls++;return 7;}
static void o_stats_queue_save(void* i){(void)i;assert(u64(13346752)==0);calls++;}
static uint32_t o_stats_load_failed(void* i, uint32_t a0){(void)i;(void)a0;return 77;}
static uint32_t o_stats_save(void* i, uint32_t a0, uint32_t a1, uint32_t a2, uint32_t a3){(void)i;(void)a0;(void)a1;(void)a2;(void)a3;assert(u64(13346752)==0);calls++;return 7;}
static uint32_t o_stats_load(void* i, uint32_t a0){(void)i;(void)a0;assert(u64(13346752)==0);calls++;return 7;}
static uint32_t o_cloud_available(void* i, uint32_t a0){(void)i;(void)a0;return 77;}
static uint32_t o_profile_stats_failed(void* i, uint64_t a0){(void)i;(void)a0;return 77;}
static uint32_t o_profile_stats_synced(void* i, uint32_t a0){(void)i;(void)a0;return 77;}
static uint32_t o_mpstats_load_update(void* i, uint64_t a0){(void)i;(void)a0;assert(ZemaOnline_ros_credentials_valid(i,123)==1);credential_checks++;if(!nested++){assert(ZemaOnline_mpstats_save_update(i,1)==7);assert(ZemaOnline_ros_credentials_valid(i,123)==1);}return 7;}
static uint32_t o_mpstats_save_update(void* i, uint64_t a0){(void)i;(void)a0;assert(ZemaOnline_ros_credentials_valid(i,123)==1);credential_checks++;return 7;}
static uint32_t o_ros_credentials_valid(void* i, uint64_t a0){(void)i;(void)a0;return 0;}
static uint32_t o_post_member_file(void* i, uint32_t a0, uint32_t a1, uint64_t a2, uint64_t a3, uint32_t a4, uint64_t a5, uint64_t a6, uint64_t a7){(void)i;(void)a0;(void)a1;(void)a2;(void)a3;(void)a4;(void)a5;(void)a6;(void)a7;return 77;}
static uint32_t o_get_member_file(void* i, uint32_t a0, uint64_t a1, uint32_t a2, uint64_t a3, uint32_t a4, uint64_t a5, uint32_t a6, uint64_t a7, uint64_t a8, uint64_t a9, uint64_t a10, uint64_t a11){(void)i;(void)a0;(void)a1;(void)a2;(void)a3;(void)a4;(void)a5;(void)a6;(void)a7;(void)a8;(void)a9;(void)a10;(void)a11;return 77;}
static uint32_t o_ugc_query_content(void* i, uint32_t a0, uint32_t a1, uint64_t a2, uint64_t a3, uint32_t a4, uint32_t a5, uint64_t a6, uint64_t a7, uint64_t a8, uint64_t a9, uint64_t a10){(void)i;(void)a0;(void)a1;(void)a2;(void)a3;(void)a4;(void)a5;(void)a6;(void)a7;(void)a8;(void)a9;(void)a10;return 77;}
static uint32_t o_grow_buffer_append(void* i, uint64_t a0, uint64_t a1, uint32_t a2){(void)i;(void)a0;(void)a1;(void)a2;assert(a2<=1024);memcpy(bytes+a0,bytes+a1,a2);return 1;}
static void o_grow_buffer_file_name(void* i, uint64_t a0, uint32_t a1, uint64_t a2){(void)i;(void)a0;(void)a1;(void)a2;calls++;}
static uint32_t o_stat_find(void* i, uint64_t a0, uint64_t a1){(void)i;(void)a0;(void)a1;return found;}
static uint32_t o_packed_key(void* i, uint64_t a0, uint32_t a1, uint32_t a2){(void)i;(void)a1;(void)a2;packed_calls++;put32(a0,0xabc);return found;}
static uint32_t o_packed_get(void* i, uint64_t a0, uint32_t a1, uint32_t a2){(void)i;(void)a0;(void)a1;(void)a2;ZemaOnline_stat_find(i,0,0);return 77;}
static void o_packed_set(void* i, uint32_t a0, uint32_t a1, uint32_t a2){(void)i;(void)a0;(void)a1;(void)a2;ZemaOnline_stat_find(i,0,0);}
static uint32_t o_stat_get_int(void* i, uint32_t a0, uint64_t a1, uint32_t a2){(void)i;(void)a0;(void)a1;(void)a2;ZemaOnline_stat_find(i,0,0);return 77;}
static uint32_t o_stat_get_float(void* i, uint32_t a0, uint64_t a1, uint32_t a2){(void)i;(void)a0;(void)a1;(void)a2;ZemaOnline_stat_find(i,0,0);return 77;}
static uint32_t o_stat_get_bool(void* i, uint32_t a0, uint64_t a1, uint32_t a2){(void)i;(void)a0;(void)a1;(void)a2;ZemaOnline_stat_find(i,0,0);return 77;}
static uint32_t o_stat_get_masked_int(void* i, uint32_t a0, uint64_t a1, uint32_t a2, uint32_t a3, uint32_t a4){(void)i;(void)a0;(void)a1;(void)a2;(void)a3;(void)a4;ZemaOnline_stat_find(i,0,0);return 77;}
static uint32_t o_stat_set_int(void* i, uint32_t a0, uint32_t a1, uint32_t a2){(void)i;(void)a0;(void)a1;(void)a2;ZemaOnline_stat_find(i,0,0);return 77;}
static uint32_t o_stat_set_float(void* i, uint32_t a0, float a1, uint32_t a2){(void)i;(void)a0;(void)a1;(void)a2;ZemaOnline_stat_find(i,0,0);return 77;}
static uint32_t o_stat_set_bool(void* i, uint32_t a0, uint32_t a1, uint32_t a2){(void)i;(void)a0;(void)a1;(void)a2;ZemaOnline_stat_find(i,0,0);return 77;}
static uint32_t o_stat_set_masked_int(void* i, uint32_t a0, uint32_t a1, uint32_t a2, uint32_t a3, uint32_t a4){(void)i;(void)a0;(void)a1;(void)a2;(void)a3;(void)a4;ZemaOnline_stat_find(i,0,0);return 77;}
static void o_stat_delete_slot(void* i, uint32_t a0){(void)i;(void)a0;calls++;}
int FixtureRun(int restored){ bytes=calloc(1,33554432);assert(bytes);const ZemaOnlineHost host={.version=1,.memory=mem,.allocate=alloc,.release=release,.prepare_interfaces=prepare,.commit_profile=commit,.originals={.rl_gamer_handle=o_rl_gamer_handle,.rl_offline_name=o_rl_offline_name,.rl_pc_initialized=o_rl_pc_initialized,.live_manager_init=o_live_manager_init,.live_manager_update=o_live_manager_update,.presence_online=o_presence_online,.bail_on_multiplayer=o_bail_on_multiplayer,.ros_privilege=o_ros_privilege,.ros_privilege_end_date=o_ros_privilege_end_date,.profile_setting_int=o_profile_setting_int,.can_access_network_features=o_can_access_network_features,.can_enter_multiplayer=o_can_enter_multiplayer,.populate_store_data=o_populate_store_data,.photo_to_jpeg=o_photo_to_jpeg,.script_program_loaded=o_script_program_loaded,.profanity_valid=o_profanity_valid,.profanity_pending=o_profanity_pending,.profanity_status=o_profanity_status,.savemigration_mp_enabled=o_savemigration_mp_enabled,.bad_pack_order=o_bad_pack_order,.xml_bool_attribute=o_xml_bool_attribute,.stats_init=o_stats_init,.stats_update=o_stats_update,.stats_queue_load=o_stats_queue_load,.stats_queue_save=o_stats_queue_save,.stats_load_failed=o_stats_load_failed,.stats_save=o_stats_save,.stats_load=o_stats_load,.cloud_available=o_cloud_available,.profile_stats_failed=o_profile_stats_failed,.profile_stats_synced=o_profile_stats_synced,.mpstats_load_update=o_mpstats_load_update,.mpstats_save_update=o_mpstats_save_update,.ros_credentials_valid=o_ros_credentials_valid,.post_member_file=o_post_member_file,.get_member_file=o_get_member_file,.ugc_query_content=o_ugc_query_content,.grow_buffer_append=o_grow_buffer_append,.grow_buffer_file_name=o_grow_buffer_file_name,.stat_find=o_stat_find,.packed_key=o_packed_key,.packed_get=o_packed_get,.packed_set=o_packed_set,.stat_get_int=o_stat_get_int,.stat_get_float=o_stat_get_float,.stat_get_bool=o_stat_get_bool,.stat_get_masked_int=o_stat_get_masked_int,.stat_set_int=o_stat_set_int,.stat_set_float=o_stat_set_float,.stat_set_bool=o_stat_set_bool,.stat_set_masked_int=o_stat_set_masked_int,.stat_delete_slot=o_stat_delete_slot}};assert(ZemaOnlineInstallHost(&host,sizeof host));assert(!ZemaOnlineInstallHost(&host,sizeof host));

assert(ZemaOnline_rl_gamer_handle(NULL,100)==1);assert(u64(100)==123456);assert(bytes[108]==3);
assert(!ZemaOnline_rl_gamer_handle(NULL,UINT64_MAX));assert(ZemaOnline_rl_offline_name(NULL,200));assert(!strcmp((char*)bytes+200,"zema"));
assert(!ZemaOnline_can_enter_multiplayer(NULL,500));
ZemaOnline_live_manager_init(NULL,1);assert(ZemaOnlineInterfacesReady());assert(u32(29308996)==2&&bytes[29309000]==1);
/* Diagnostics never write session state or roster fields and log only changes. */
put64(29044456,30000000);put32(30099916,5);put32(28504084,2);
uint8_t* observed=malloc(33554432);assert(observed);memcpy(observed,bytes,33554432);
ZemaOnline_live_manager_update(NULL,1);ZemaOnline_live_manager_update(NULL,1);assert(!memcmp(observed,bytes,33554432));
put64(29044456,UINT64_MAX);ZemaOnline_live_manager_update(NULL,1);assert(u64(29044456)==UINT64_MAX);
put64(29044456,0);put32(28504084,0);ZemaOnline_live_manager_update(NULL,1);free(observed);

put64(13346752,0x12345678);ZemaOnline_stats_init(NULL,1);assert(u64(13346752)==0x12345678);uint64_t stale;memcpy(&stale,retired+13346752,8);assert(stale==0);free(retired);puts("MEMORY_RELOCATION_SAFE_PASS");
assert(!ZemaOnline_ros_credentials_valid(NULL,0));assert(ZemaOnline_mpstats_load_update(NULL,1)==7);assert(credential_checks==2);assert(!ZemaOnline_ros_credentials_valid(NULL,0));
assert(ZemaOnline_profile_setting_int(NULL,1,903)==1);assert(ZemaOnline_profile_setting_int(NULL,1,99)==77);
assert(!ZemaOnline_ros_privilege(NULL,0,7));assert(ZemaOnline_ros_privilege(NULL,0,1));
found=0;assert(!ZemaOnline_packed_key(NULL,300,12,1));assert(!ZemaOnline_packed_key(NULL,300,12,1));assert(packed_calls==1);put64(25461184,100);assert(!ZemaOnline_packed_key(NULL,300,12,1));assert(packed_calls==2);assert(ZemaOnline_stat_set_int(NULL,0x1234,0xffffffef,0));assert(ZemaOnline_stat_get_int(NULL,0x1234,300,0));assert(u32(300)==0xffffffef);
assert(ZemaOnline_stat_set_float(NULL,0x1235,-1.25f,0));assert(ZemaOnline_stat_get_float(NULL,0x1235,300,0));assert(u32(300)==0xbfa00000);
assert(ZemaOnline_stat_set_masked_int(NULL,0x1234,0xab,8,8,0));assert(ZemaOnline_stat_get_masked_int(NULL,0x1234,300,8,8,0));assert(u32(300)==0xab);
found=1;assert(ZemaOnline_stat_get_int(NULL,0x1234,300,0)==77);found=0;
ZemaOnline_packed_set(NULL,99,7,1);ZemaOnline_packed_set(NULL,77,7,2);ZemaOnline_stat_delete_slot(NULL,1);assert(ZemaOnline_packed_get(NULL,300,7,1)&&u32(300)==0);assert(ZemaOnline_packed_get(NULL,300,7,2)&&u32(300)==77);
strcpy((char*)bytes+512,"GTA5/saves/mpstats/char0001.save");
if(restored){assert(ZemaProfileStat((uint8_t*)"p2:7",4)==77);}
else {
ZemaOnline_get_member_file(NULL,0,0,0,512,0,0,0,8638336,2048,0,0,4096);assert(u32(4096)==2&&u32(4100)==404);assert(!ZemaOnline_stats_load_failed(NULL,1));
const uint8_t payload[]={0,255,128,0,42};memcpy(bytes+1024,payload,sizeof payload);
ZemaOnline_post_member_file(NULL,0,0,512,1024,sizeof payload,0,0,4096);assert(u32(4096)==3&&commits==1);assert(ZemaOnline_stats_load_failed(NULL,1)==77);
fail_commit=1;ZemaOnline_post_member_file(NULL,0,0,512,1024,sizeof payload,0,0,4096);assert(u32(4096)==2);fail_commit=0;
}
ZemaOnline_get_member_file(NULL,0,0,0,512,0,0,0,8638336,2048,0,0,4096);assert(u32(4096)==3);assert(!memcmp(bytes+2048,(uint8_t[]){0,255,128,0,42},5));
strcpy((char*)bytes+512,"../Story.save");ZemaOnline_get_member_file(NULL,0,0,0,512,0,0,0,8638336,2048,0,0,4096);assert(u32(4096)==2&&u32(4100)==0);
ZemaOnline_grow_buffer_file_name(NULL,600,40,0x123abc);assert(!strcmp((char*)bytes+600,"growbuffer:123abc"));
put64(10000+96,11000);strcpy((char*)bytes+11000,"MainTransition");put64(10000+16,12000);put32(10000+28,2600000);
put64(12000+(2510677/0x4000)*8,2000000);put64(12000+(2504003/0x4000)*8,2100000);
size_t patch=2000000+2510677%0x4000;memcpy(bytes+patch,(uint8_t[]){0x2c,1,3,0xab},4);
assert(ZemaOnline_script_program_loaded(NULL,10000,0)==10000);assert(bytes[patch]==113);bytes[patch]=55;ZemaOnline_script_program_loaded(NULL,10000,0);assert(bytes[patch]==55);
free(bytes);puts("ONLINE_CHARACTER_CALLBACKS_PASS");return 0;}
