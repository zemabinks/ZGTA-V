/* Generated from the exact pinned glue5 engine contract. */
#ifndef ZEMA_ONLINE_HOST_H
#define ZEMA_ONLINE_HOST_H
#include <stdint.h>
#include <stddef.h>
typedef struct ZemaOnlineOriginals {
  uint32_t (*rl_gamer_handle)(void* instance, uint64_t a0);
  uint32_t (*rl_offline_name)(void* instance, uint64_t a0);
  uint32_t (*rl_pc_initialized)(void* instance);
  void (*live_manager_init)(void* instance, uint32_t a0);
  void (*live_manager_update)(void* instance, uint32_t a0);
  uint32_t (*presence_online)(void* instance, uint32_t a0);
  void (*bail_on_multiplayer)(void* instance, uint32_t a0, uint32_t a1);
  uint32_t (*ros_privilege)(void* instance, uint64_t a0, uint32_t a1);
  uint32_t (*ros_privilege_end_date)(void* instance, uint64_t a0, uint32_t a1, uint64_t a2, uint64_t a3);
  uint32_t (*profile_setting_int)(void* instance, uint64_t a0, uint32_t a1);
  uint32_t (*can_access_network_features)(void* instance, uint32_t a0, uint64_t a1);
  uint32_t (*can_enter_multiplayer)(void* instance, uint64_t a0);
  void (*populate_store_data)(void* instance);
  uint32_t (*photo_to_jpeg)(void* instance, uint64_t a0, uint64_t a1, uint32_t a2, uint64_t a3, uint32_t a4, uint32_t a5, uint32_t a6, uint64_t a7);
  uint64_t (*script_program_loaded)(void* instance, uint64_t a0, uint64_t a1);
  void (*profanity_valid)(void* instance, uint64_t a0);
  void (*profanity_pending)(void* instance, uint64_t a0);
  void (*profanity_status)(void* instance, uint64_t a0);
  void (*savemigration_mp_enabled)(void* instance, uint64_t a0);
  void (*bad_pack_order)(void* instance, uint64_t a0);
  uint32_t (*xml_bool_attribute)(void* instance, uint64_t a0, uint64_t a1, uint32_t a2);
  void (*stats_init)(void* instance, uint32_t a0);
  void (*stats_update)(void* instance);
  uint32_t (*stats_queue_load)(void* instance);
  void (*stats_queue_save)(void* instance);
  uint32_t (*stats_load_failed)(void* instance, uint32_t a0);
  uint32_t (*stats_save)(void* instance, uint32_t a0, uint32_t a1, uint32_t a2, uint32_t a3);
  uint32_t (*stats_load)(void* instance, uint32_t a0);
  uint32_t (*cloud_available)(void* instance, uint32_t a0);
  uint32_t (*profile_stats_failed)(void* instance, uint64_t a0);
  uint32_t (*profile_stats_synced)(void* instance, uint32_t a0);
  uint32_t (*mpstats_load_update)(void* instance, uint64_t a0);
  uint32_t (*mpstats_save_update)(void* instance, uint64_t a0);
  uint32_t (*ros_credentials_valid)(void* instance, uint64_t a0);
  uint32_t (*post_member_file)(void* instance, uint32_t a0, uint32_t a1, uint64_t a2, uint64_t a3, uint32_t a4, uint64_t a5, uint64_t a6, uint64_t a7);
  uint32_t (*get_member_file)(void* instance, uint32_t a0, uint64_t a1, uint32_t a2, uint64_t a3, uint32_t a4, uint64_t a5, uint32_t a6, uint64_t a7, uint64_t a8, uint64_t a9, uint64_t a10, uint64_t a11);
  uint32_t (*ugc_query_content)(void* instance, uint32_t a0, uint32_t a1, uint64_t a2, uint64_t a3, uint32_t a4, uint32_t a5, uint64_t a6, uint64_t a7, uint64_t a8, uint64_t a9, uint64_t a10);
  uint32_t (*grow_buffer_append)(void* instance, uint64_t a0, uint64_t a1, uint32_t a2);
  void (*grow_buffer_file_name)(void* instance, uint64_t a0, uint32_t a1, uint64_t a2);
  uint32_t (*stat_find)(void* instance, uint64_t a0, uint64_t a1);
  uint32_t (*packed_key)(void* instance, uint64_t a0, uint32_t a1, uint32_t a2);
  uint32_t (*packed_get)(void* instance, uint64_t a0, uint32_t a1, uint32_t a2);
  void (*packed_set)(void* instance, uint32_t a0, uint32_t a1, uint32_t a2);
  uint32_t (*stat_get_int)(void* instance, uint32_t a0, uint64_t a1, uint32_t a2);
  uint32_t (*stat_get_float)(void* instance, uint32_t a0, uint64_t a1, uint32_t a2);
  uint32_t (*stat_get_bool)(void* instance, uint32_t a0, uint64_t a1, uint32_t a2);
  uint32_t (*stat_get_masked_int)(void* instance, uint32_t a0, uint64_t a1, uint32_t a2, uint32_t a3, uint32_t a4);
  uint32_t (*stat_set_int)(void* instance, uint32_t a0, uint32_t a1, uint32_t a2);
  uint32_t (*stat_set_float)(void* instance, uint32_t a0, float a1, uint32_t a2);
  uint32_t (*stat_set_bool)(void* instance, uint32_t a0, uint32_t a1, uint32_t a2);
  uint32_t (*stat_set_masked_int)(void* instance, uint32_t a0, uint32_t a1, uint32_t a2, uint32_t a3, uint32_t a4);
  void (*stat_delete_slot)(void* instance, uint32_t a0);
} ZemaOnlineOriginals;
typedef struct {
  uint32_t version;
  uint8_t* (*memory)(void*,uint64_t*);
  uint64_t (*allocate)(void*,uint64_t);
  void (*release)(void*,uint64_t);
  /* Must install signature-correct Social Club tables before returning 1.
   * A missing/unverified table must return 0; no generic function-pointer cast. */
  int (*prepare_interfaces)(void*);
  /* Synchronous atomic persistence of the whole isolated profile. Failure
   * must retain the previous disk snapshot and return 0. */
  int (*commit_profile)(void*);
  ZemaOnlineOriginals originals;
} ZemaOnlineHost;
int ZemaOnlineInstallHost(const ZemaOnlineHost*,size_t);
int ZemaOnlineConfigured(void);
int ZemaOnlineInterfacesReady(void);
uint32_t ZemaOnline_rl_gamer_handle(void* instance, uint64_t a0);
uint32_t ZemaOnline_rl_offline_name(void* instance, uint64_t a0);
uint32_t ZemaOnline_rl_pc_initialized(void* instance);
void ZemaOnline_live_manager_init(void* instance, uint32_t a0);
void ZemaOnline_live_manager_update(void* instance, uint32_t a0);
uint32_t ZemaOnline_presence_online(void* instance, uint32_t a0);
void ZemaOnline_bail_on_multiplayer(void* instance, uint32_t a0, uint32_t a1);
uint32_t ZemaOnline_ros_privilege(void* instance, uint64_t a0, uint32_t a1);
uint32_t ZemaOnline_ros_privilege_end_date(void* instance, uint64_t a0, uint32_t a1, uint64_t a2, uint64_t a3);
uint32_t ZemaOnline_profile_setting_int(void* instance, uint64_t a0, uint32_t a1);
uint32_t ZemaOnline_can_access_network_features(void* instance, uint32_t a0, uint64_t a1);
uint32_t ZemaOnline_can_enter_multiplayer(void* instance, uint64_t a0);
void ZemaOnline_populate_store_data(void* instance);
uint32_t ZemaOnline_photo_to_jpeg(void* instance, uint64_t a0, uint64_t a1, uint32_t a2, uint64_t a3, uint32_t a4, uint32_t a5, uint32_t a6, uint64_t a7);
uint64_t ZemaOnline_script_program_loaded(void* instance, uint64_t a0, uint64_t a1);
void ZemaOnline_profanity_valid(void* instance, uint64_t a0);
void ZemaOnline_profanity_pending(void* instance, uint64_t a0);
void ZemaOnline_profanity_status(void* instance, uint64_t a0);
void ZemaOnline_savemigration_mp_enabled(void* instance, uint64_t a0);
void ZemaOnline_bad_pack_order(void* instance, uint64_t a0);
uint32_t ZemaOnline_xml_bool_attribute(void* instance, uint64_t a0, uint64_t a1, uint32_t a2);
void ZemaOnline_stats_init(void* instance, uint32_t a0);
void ZemaOnline_stats_update(void* instance);
uint32_t ZemaOnline_stats_queue_load(void* instance);
void ZemaOnline_stats_queue_save(void* instance);
uint32_t ZemaOnline_stats_load_failed(void* instance, uint32_t a0);
uint32_t ZemaOnline_stats_save(void* instance, uint32_t a0, uint32_t a1, uint32_t a2, uint32_t a3);
uint32_t ZemaOnline_stats_load(void* instance, uint32_t a0);
uint32_t ZemaOnline_cloud_available(void* instance, uint32_t a0);
uint32_t ZemaOnline_profile_stats_failed(void* instance, uint64_t a0);
uint32_t ZemaOnline_profile_stats_synced(void* instance, uint32_t a0);
uint32_t ZemaOnline_mpstats_load_update(void* instance, uint64_t a0);
uint32_t ZemaOnline_mpstats_save_update(void* instance, uint64_t a0);
uint32_t ZemaOnline_ros_credentials_valid(void* instance, uint64_t a0);
uint32_t ZemaOnline_post_member_file(void* instance, uint32_t a0, uint32_t a1, uint64_t a2, uint64_t a3, uint32_t a4, uint64_t a5, uint64_t a6, uint64_t a7);
uint32_t ZemaOnline_get_member_file(void* instance, uint32_t a0, uint64_t a1, uint32_t a2, uint64_t a3, uint32_t a4, uint64_t a5, uint32_t a6, uint64_t a7, uint64_t a8, uint64_t a9, uint64_t a10, uint64_t a11);
uint32_t ZemaOnline_ugc_query_content(void* instance, uint32_t a0, uint32_t a1, uint64_t a2, uint64_t a3, uint32_t a4, uint32_t a5, uint64_t a6, uint64_t a7, uint64_t a8, uint64_t a9, uint64_t a10);
uint32_t ZemaOnline_grow_buffer_append(void* instance, uint64_t a0, uint64_t a1, uint32_t a2);
void ZemaOnline_grow_buffer_file_name(void* instance, uint64_t a0, uint32_t a1, uint64_t a2);
uint32_t ZemaOnline_stat_find(void* instance, uint64_t a0, uint64_t a1);
uint32_t ZemaOnline_packed_key(void* instance, uint64_t a0, uint32_t a1, uint32_t a2);
uint32_t ZemaOnline_packed_get(void* instance, uint64_t a0, uint32_t a1, uint32_t a2);
void ZemaOnline_packed_set(void* instance, uint32_t a0, uint32_t a1, uint32_t a2);
uint32_t ZemaOnline_stat_get_int(void* instance, uint32_t a0, uint64_t a1, uint32_t a2);
uint32_t ZemaOnline_stat_get_float(void* instance, uint32_t a0, uint64_t a1, uint32_t a2);
uint32_t ZemaOnline_stat_get_bool(void* instance, uint32_t a0, uint64_t a1, uint32_t a2);
uint32_t ZemaOnline_stat_get_masked_int(void* instance, uint32_t a0, uint64_t a1, uint32_t a2, uint32_t a3, uint32_t a4);
uint32_t ZemaOnline_stat_set_int(void* instance, uint32_t a0, uint32_t a1, uint32_t a2);
uint32_t ZemaOnline_stat_set_float(void* instance, uint32_t a0, float a1, uint32_t a2);
uint32_t ZemaOnline_stat_set_bool(void* instance, uint32_t a0, uint32_t a1, uint32_t a2);
uint32_t ZemaOnline_stat_set_masked_int(void* instance, uint32_t a0, uint32_t a1, uint32_t a2, uint32_t a3, uint32_t a4);
void ZemaOnline_stat_delete_slot(void* instance, uint32_t a0);
#endif
