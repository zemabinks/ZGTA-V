/* Typed native adapters. Not linked into the existing app target. */
#include "ZemaOnlineHost.h"
#include "ZemaEngineLAN.h"
static uint32_t original_rl_gamer_handle(void* instance, uint64_t a0) { return w2c_game_f14442_zema_lan_original((w2c_game*)instance,a0); }
static u32 callback_rl_gamer_handle(w2c_game* instance, u64 a0) { return ZemaOnline_rl_gamer_handle((void*)instance, a0); }
static uint32_t original_rl_offline_name(void* instance, uint64_t a0) { return w2c_game_f14465_zema_lan_original((w2c_game*)instance,a0); }
static u32 callback_rl_offline_name(w2c_game* instance, u64 a0) { return ZemaOnline_rl_offline_name((void*)instance, a0); }
static uint32_t original_rl_pc_initialized(void* instance) { return w2c_game_f14320_zema_lan_original((w2c_game*)instance); }
static u32 callback_rl_pc_initialized(w2c_game* instance) { return ZemaOnline_rl_pc_initialized((void*)instance); }
static void original_live_manager_init(void* instance, uint32_t a0) { w2c_game_f82863_zema_lan_original((w2c_game*)instance,a0); }
static void callback_live_manager_init(w2c_game* instance, u32 a0) { ZemaOnline_live_manager_init((void*)instance, a0); }
static void original_live_manager_update(void* instance, uint32_t a0) { w2c_game_f82896_zema_lan_original((w2c_game*)instance,a0); }
static void callback_live_manager_update(w2c_game* instance, u32 a0) { ZemaOnline_live_manager_update((void*)instance, a0); }
static uint32_t original_presence_online(void* instance, uint32_t a0) { return w2c_game_f14354_zema_lan_original((w2c_game*)instance,a0); }
static u32 callback_presence_online(w2c_game* instance, u32 a0) { return ZemaOnline_presence_online((void*)instance, a0); }
static void original_bail_on_multiplayer(void* instance, uint32_t a0, uint32_t a1) { w2c_game_f82918_zema_lan_original((w2c_game*)instance,a0,a1); }
static void callback_bail_on_multiplayer(w2c_game* instance, u32 a0, u32 a1) { ZemaOnline_bail_on_multiplayer((void*)instance, a0, a1); }
static uint32_t original_ros_privilege(void* instance, uint64_t a0, uint32_t a1) { return w2c_game_f14836_zema_lan_original((w2c_game*)instance,a0,a1); }
static u32 callback_ros_privilege(w2c_game* instance, u64 a0, u32 a1) { return ZemaOnline_ros_privilege((void*)instance, a0, a1); }
static uint32_t original_ros_privilege_end_date(void* instance, uint64_t a0, uint32_t a1, uint64_t a2, uint64_t a3) { return w2c_game_f14886_zema_lan_original((w2c_game*)instance,a0,a1,a2,a3); }
static u32 callback_ros_privilege_end_date(w2c_game* instance, u64 a0, u32 a1, u64 a2, u64 a3) { return ZemaOnline_ros_privilege_end_date((void*)instance, a0, a1, a2, a3); }
static uint32_t original_profile_setting_int(void* instance, uint64_t a0, uint32_t a1) { return w2c_game_f36364_zema_lan_original((w2c_game*)instance,a0,a1); }
static u32 callback_profile_setting_int(w2c_game* instance, u64 a0, u32 a1) { return ZemaOnline_profile_setting_int((void*)instance, a0, a1); }
static uint32_t original_can_access_network_features(void* instance, uint32_t a0, uint64_t a1) { return w2c_game_f82943_zema_lan_original((w2c_game*)instance,a0,a1); }
static u32 callback_can_access_network_features(w2c_game* instance, u32 a0, u64 a1) { return ZemaOnline_can_access_network_features((void*)instance, a0, a1); }
static uint32_t original_can_enter_multiplayer(void* instance, uint64_t a0) { return w2c_game_f85869_zema_lan_original((w2c_game*)instance,a0); }
static u32 callback_can_enter_multiplayer(w2c_game* instance, u64 a0) { return ZemaOnline_can_enter_multiplayer((void*)instance, a0); }
static void original_populate_store_data(void* instance) { w2c_game_f83640_zema_lan_original((w2c_game*)instance); }
static void callback_populate_store_data(w2c_game* instance) { ZemaOnline_populate_store_data((void*)instance); }
static uint32_t original_photo_to_jpeg(void* instance, uint64_t a0, uint64_t a1, uint32_t a2, uint64_t a3, uint32_t a4, uint32_t a5, uint32_t a6, uint64_t a7) { return w2c_game_f43759_zema_lan_original((w2c_game*)instance,a0,a1,a2,a3,a4,a5,a6,a7); }
static u32 callback_photo_to_jpeg(w2c_game* instance, u64 a0, u64 a1, u32 a2, u64 a3, u32 a4, u32 a5, u32 a6, u64 a7) { return ZemaOnline_photo_to_jpeg((void*)instance, a0, a1, a2, a3, a4, a5, a6, a7); }
static uint64_t original_script_program_loaded(void* instance, uint64_t a0, uint64_t a1) { return w2c_game_f16924_zema_lan_original((w2c_game*)instance,a0,a1); }
static u64 callback_script_program_loaded(w2c_game* instance, u64 a0, u64 a1) { return ZemaOnline_script_program_loaded((void*)instance, a0, a1); }
static void original_profanity_valid(void* instance, uint64_t a0) { w2c_game_f59554_zema_lan_original((w2c_game*)instance,a0); }
static void callback_profanity_valid(w2c_game* instance, u64 a0) { ZemaOnline_profanity_valid((void*)instance, a0); }
static void original_profanity_pending(void* instance, uint64_t a0) { w2c_game_f59555_zema_lan_original((w2c_game*)instance,a0); }
static void callback_profanity_pending(w2c_game* instance, u64 a0) { ZemaOnline_profanity_pending((void*)instance, a0); }
static void original_profanity_status(void* instance, uint64_t a0) { w2c_game_f59557_zema_lan_original((w2c_game*)instance,a0); }
static void callback_profanity_status(w2c_game* instance, u64 a0) { ZemaOnline_profanity_status((void*)instance, a0); }
static void original_savemigration_mp_enabled(void* instance, uint64_t a0) { w2c_game_f59300_zema_lan_original((w2c_game*)instance,a0); }
static void callback_savemigration_mp_enabled(w2c_game* instance, u64 a0) { ZemaOnline_savemigration_mp_enabled((void*)instance, a0); }
static void original_bad_pack_order(void* instance, uint64_t a0) { w2c_game_f51368_zema_lan_original((w2c_game*)instance,a0); }
static void callback_bad_pack_order(w2c_game* instance, u64 a0) { ZemaOnline_bad_pack_order((void*)instance, a0); }
static uint32_t original_xml_bool_attribute(void* instance, uint64_t a0, uint64_t a1, uint32_t a2) { return w2c_game_f2203_zema_lan_original((w2c_game*)instance,a0,a1,a2); }
static u32 callback_xml_bool_attribute(w2c_game* instance, u64 a0, u64 a1, u32 a2) { return ZemaOnline_xml_bool_attribute((void*)instance, a0, a1, a2); }
static void original_stats_init(void* instance, uint32_t a0) { w2c_game_f77403_zema_lan_original((w2c_game*)instance,a0); }
static void callback_stats_init(w2c_game* instance, u32 a0) { ZemaOnline_stats_init((void*)instance, a0); }
static void original_stats_update(void* instance) { w2c_game_f77189_zema_lan_original((w2c_game*)instance); }
static void callback_stats_update(w2c_game* instance) { ZemaOnline_stats_update((void*)instance); }
static uint32_t original_stats_queue_load(void* instance) { return w2c_game_f77406_zema_lan_original((w2c_game*)instance); }
static u32 callback_stats_queue_load(w2c_game* instance) { return ZemaOnline_stats_queue_load((void*)instance); }
static void original_stats_queue_save(void* instance) { w2c_game_f77407_zema_lan_original((w2c_game*)instance); }
static void callback_stats_queue_save(w2c_game* instance) { ZemaOnline_stats_queue_save((void*)instance); }
static uint32_t original_stats_load_failed(void* instance, uint32_t a0) { return w2c_game_f77340_zema_lan_original((w2c_game*)instance,a0); }
static u32 callback_stats_load_failed(w2c_game* instance, u32 a0) { return ZemaOnline_stats_load_failed((void*)instance, a0); }
static uint32_t original_stats_save(void* instance, uint32_t a0, uint32_t a1, uint32_t a2, uint32_t a3) { return w2c_game_f77414_zema_lan_original((w2c_game*)instance,a0,a1,a2,a3); }
static u32 callback_stats_save(w2c_game* instance, u32 a0, u32 a1, u32 a2, u32 a3) { return ZemaOnline_stats_save((void*)instance, a0, a1, a2, a3); }
static uint32_t original_stats_load(void* instance, uint32_t a0) { return w2c_game_f77417_zema_lan_original((w2c_game*)instance,a0); }
static u32 callback_stats_load(w2c_game* instance, u32 a0) { return ZemaOnline_stats_load((void*)instance, a0); }
static uint32_t original_cloud_available(void* instance, uint32_t a0) { return w2c_game_f83008_zema_lan_original((w2c_game*)instance,a0); }
static u32 callback_cloud_available(w2c_game* instance, u32 a0) { return ZemaOnline_cloud_available((void*)instance, a0); }
static uint32_t original_profile_stats_failed(void* instance, uint64_t a0) { return w2c_game_f84423_zema_lan_original((w2c_game*)instance,a0); }
static u32 callback_profile_stats_failed(w2c_game* instance, u64 a0) { return ZemaOnline_profile_stats_failed((void*)instance, a0); }
static uint32_t original_profile_stats_synced(void* instance, uint32_t a0) { return w2c_game_f84424_zema_lan_original((w2c_game*)instance,a0); }
static u32 callback_profile_stats_synced(w2c_game* instance, u32 a0) { return ZemaOnline_profile_stats_synced((void*)instance, a0); }
static uint32_t original_mpstats_load_update(void* instance, uint64_t a0) { return w2c_game_f45381_zema_lan_original((w2c_game*)instance,a0); }
static u32 callback_mpstats_load_update(w2c_game* instance, u64 a0) { return ZemaOnline_mpstats_load_update((void*)instance, a0); }
static uint32_t original_mpstats_save_update(void* instance, uint64_t a0) { return w2c_game_f45383_zema_lan_original((w2c_game*)instance,a0); }
static u32 callback_mpstats_save_update(w2c_game* instance, u64 a0) { return ZemaOnline_mpstats_save_update((void*)instance, a0); }
static uint32_t original_ros_credentials_valid(void* instance, uint64_t a0) { return w2c_game_f14362_zema_lan_original((w2c_game*)instance,a0); }
static u32 callback_ros_credentials_valid(w2c_game* instance, u64 a0) { return ZemaOnline_ros_credentials_valid((void*)instance, a0); }
static uint32_t original_post_member_file(void* instance, uint32_t a0, uint32_t a1, uint64_t a2, uint64_t a3, uint32_t a4, uint64_t a5, uint64_t a6, uint64_t a7) { return w2c_game_f15050_zema_lan_original((w2c_game*)instance,a0,a1,a2,a3,a4,a5,a6,a7); }
static u32 callback_post_member_file(w2c_game* instance, u32 a0, u32 a1, u64 a2, u64 a3, u32 a4, u64 a5, u64 a6, u64 a7) { return ZemaOnline_post_member_file((void*)instance, a0, a1, a2, a3, a4, a5, a6, a7); }
static uint32_t original_get_member_file(void* instance, uint32_t a0, uint64_t a1, uint32_t a2, uint64_t a3, uint32_t a4, uint64_t a5, uint32_t a6, uint64_t a7, uint64_t a8, uint64_t a9, uint64_t a10, uint64_t a11) { return w2c_game_f15048_zema_lan_original((w2c_game*)instance,a0,a1,a2,a3,a4,a5,a6,a7,a8,a9,a10,a11); }
static u32 callback_get_member_file(w2c_game* instance, u32 a0, u64 a1, u32 a2, u64 a3, u32 a4, u64 a5, u32 a6, u64 a7, u64 a8, u64 a9, u64 a10, u64 a11) { return ZemaOnline_get_member_file((void*)instance, a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11); }
static uint32_t original_ugc_query_content(void* instance, uint32_t a0, uint32_t a1, uint64_t a2, uint64_t a3, uint32_t a4, uint32_t a5, uint64_t a6, uint64_t a7, uint64_t a8, uint64_t a9, uint64_t a10) { return w2c_game_f14971_zema_lan_original((w2c_game*)instance,a0,a1,a2,a3,a4,a5,a6,a7,a8,a9,a10); }
static u32 callback_ugc_query_content(w2c_game* instance, u32 a0, u32 a1, u64 a2, u64 a3, u32 a4, u32 a5, u64 a6, u64 a7, u64 a8, u64 a9, u64 a10) { return ZemaOnline_ugc_query_content((void*)instance, a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10); }
static uint32_t original_grow_buffer_append(void* instance, uint64_t a0, uint64_t a1, uint32_t a2) { return w2c_game_f1130_zema_lan_original((w2c_game*)instance,a0,a1,a2); }
static u32 callback_grow_buffer_append(w2c_game* instance, u64 a0, u64 a1, u32 a2) { return ZemaOnline_grow_buffer_append((void*)instance, a0, a1, a2); }
static void original_grow_buffer_file_name(void* instance, uint64_t a0, uint32_t a1, uint64_t a2) { w2c_game_f1605_zema_lan_original((w2c_game*)instance,a0,a1,a2); }
static void callback_grow_buffer_file_name(w2c_game* instance, u64 a0, u32 a1, u64 a2) { ZemaOnline_grow_buffer_file_name((void*)instance, a0, a1, a2); }
static uint32_t original_stat_find(void* instance, uint64_t a0, uint64_t a1) { return w2c_game_f77200_zema_lan_original((w2c_game*)instance,a0,a1); }
static u32 callback_stat_find(w2c_game* instance, u64 a0, u64 a1) { return ZemaOnline_stat_find((void*)instance, a0, a1); }
static uint32_t original_packed_key(void* instance, uint64_t a0, uint32_t a1, uint32_t a2) { return w2c_game_f86226_zema_lan_original((w2c_game*)instance,a0,a1,a2); }
static u32 callback_packed_key(w2c_game* instance, u64 a0, u32 a1, u32 a2) { return ZemaOnline_packed_key((void*)instance, a0, a1, a2); }
static uint32_t original_packed_get(void* instance, uint64_t a0, uint32_t a1, uint32_t a2) { return w2c_game_f86276_zema_lan_original((w2c_game*)instance,a0,a1,a2); }
static u32 callback_packed_get(w2c_game* instance, u64 a0, u32 a1, u32 a2) { return ZemaOnline_packed_get((void*)instance, a0, a1, a2); }
static void original_packed_set(void* instance, uint32_t a0, uint32_t a1, uint32_t a2) { w2c_game_f86277_zema_lan_original((w2c_game*)instance,a0,a1,a2); }
static void callback_packed_set(w2c_game* instance, u32 a0, u32 a1, u32 a2) { ZemaOnline_packed_set((void*)instance, a0, a1, a2); }
static uint32_t original_stat_get_int(void* instance, uint32_t a0, uint64_t a1, uint32_t a2) { return w2c_game_f59629_zema_lan_original((w2c_game*)instance,a0,a1,a2); }
static u32 callback_stat_get_int(w2c_game* instance, u32 a0, u64 a1, u32 a2) { return ZemaOnline_stat_get_int((void*)instance, a0, a1, a2); }
static uint32_t original_stat_get_float(void* instance, uint32_t a0, uint64_t a1, uint32_t a2) { return w2c_game_f59630_zema_lan_original((w2c_game*)instance,a0,a1,a2); }
static u32 callback_stat_get_float(w2c_game* instance, u32 a0, u64 a1, u32 a2) { return ZemaOnline_stat_get_float((void*)instance, a0, a1, a2); }
static uint32_t original_stat_get_bool(void* instance, uint32_t a0, uint64_t a1, uint32_t a2) { return w2c_game_f59631_zema_lan_original((w2c_game*)instance,a0,a1,a2); }
static u32 callback_stat_get_bool(w2c_game* instance, u32 a0, u64 a1, u32 a2) { return ZemaOnline_stat_get_bool((void*)instance, a0, a1, a2); }
static uint32_t original_stat_get_masked_int(void* instance, uint32_t a0, uint64_t a1, uint32_t a2, uint32_t a3, uint32_t a4) { return w2c_game_f59635_zema_lan_original((w2c_game*)instance,a0,a1,a2,a3,a4); }
static u32 callback_stat_get_masked_int(w2c_game* instance, u32 a0, u64 a1, u32 a2, u32 a3, u32 a4) { return ZemaOnline_stat_get_masked_int((void*)instance, a0, a1, a2, a3, a4); }
static uint32_t original_stat_set_int(void* instance, uint32_t a0, uint32_t a1, uint32_t a2) { return w2c_game_f59619_zema_lan_original((w2c_game*)instance,a0,a1,a2); }
static u32 callback_stat_set_int(w2c_game* instance, u32 a0, u32 a1, u32 a2) { return ZemaOnline_stat_set_int((void*)instance, a0, a1, a2); }
static uint32_t original_stat_set_float(void* instance, uint32_t a0, float a1, uint32_t a2) { return w2c_game_f59620_zema_lan_original((w2c_game*)instance,a0,a1,a2); }
static u32 callback_stat_set_float(w2c_game* instance, u32 a0, f32 a1, u32 a2) { return ZemaOnline_stat_set_float((void*)instance, a0, a1, a2); }
static uint32_t original_stat_set_bool(void* instance, uint32_t a0, uint32_t a1, uint32_t a2) { return w2c_game_f59621_zema_lan_original((w2c_game*)instance,a0,a1,a2); }
static u32 callback_stat_set_bool(w2c_game* instance, u32 a0, u32 a1, u32 a2) { return ZemaOnline_stat_set_bool((void*)instance, a0, a1, a2); }
static uint32_t original_stat_set_masked_int(void* instance, uint32_t a0, uint32_t a1, uint32_t a2, uint32_t a3, uint32_t a4) { return w2c_game_f59626_zema_lan_original((w2c_game*)instance,a0,a1,a2,a3,a4); }
static u32 callback_stat_set_masked_int(w2c_game* instance, u32 a0, u32 a1, u32 a2, u32 a3, u32 a4) { return ZemaOnline_stat_set_masked_int((void*)instance, a0, a1, a2, a3, a4); }
static void original_stat_delete_slot(void* instance, uint32_t a0) { w2c_game_f59763_zema_lan_original((w2c_game*)instance,a0); }
static void callback_stat_delete_slot(w2c_game* instance, u32 a0) { ZemaOnline_stat_delete_slot((void*)instance, a0); }
void ZemaOnlineBindOriginals(ZemaOnlineOriginals* originals,ZemaEngineLANHooks* hooks) {
  originals->rl_gamer_handle=original_rl_gamer_handle; hooks->rl_gamer_handle=callback_rl_gamer_handle;
  originals->rl_offline_name=original_rl_offline_name; hooks->rl_offline_name=callback_rl_offline_name;
  originals->rl_pc_initialized=original_rl_pc_initialized; hooks->rl_pc_initialized=callback_rl_pc_initialized;
  originals->live_manager_init=original_live_manager_init; hooks->live_manager_init=callback_live_manager_init;
  originals->live_manager_update=original_live_manager_update; hooks->live_manager_update=callback_live_manager_update;
  originals->presence_online=original_presence_online; hooks->presence_online=callback_presence_online;
  originals->bail_on_multiplayer=original_bail_on_multiplayer; hooks->bail_on_multiplayer=callback_bail_on_multiplayer;
  originals->ros_privilege=original_ros_privilege; hooks->ros_privilege=callback_ros_privilege;
  originals->ros_privilege_end_date=original_ros_privilege_end_date; hooks->ros_privilege_end_date=callback_ros_privilege_end_date;
  originals->profile_setting_int=original_profile_setting_int; hooks->profile_setting_int=callback_profile_setting_int;
  originals->can_access_network_features=original_can_access_network_features; hooks->can_access_network_features=callback_can_access_network_features;
  originals->can_enter_multiplayer=original_can_enter_multiplayer; hooks->can_enter_multiplayer=callback_can_enter_multiplayer;
  originals->populate_store_data=original_populate_store_data; hooks->populate_store_data=callback_populate_store_data;
  originals->photo_to_jpeg=original_photo_to_jpeg; hooks->photo_to_jpeg=callback_photo_to_jpeg;
  originals->script_program_loaded=original_script_program_loaded; hooks->script_program_loaded=callback_script_program_loaded;
  originals->profanity_valid=original_profanity_valid; hooks->profanity_valid=callback_profanity_valid;
  originals->profanity_pending=original_profanity_pending; hooks->profanity_pending=callback_profanity_pending;
  originals->profanity_status=original_profanity_status; hooks->profanity_status=callback_profanity_status;
  originals->savemigration_mp_enabled=original_savemigration_mp_enabled; hooks->savemigration_mp_enabled=callback_savemigration_mp_enabled;
  originals->bad_pack_order=original_bad_pack_order; hooks->bad_pack_order=callback_bad_pack_order;
  originals->xml_bool_attribute=original_xml_bool_attribute; hooks->xml_bool_attribute=callback_xml_bool_attribute;
  originals->stats_init=original_stats_init; hooks->stats_init=callback_stats_init;
  originals->stats_update=original_stats_update; hooks->stats_update=callback_stats_update;
  originals->stats_queue_load=original_stats_queue_load; hooks->stats_queue_load=callback_stats_queue_load;
  originals->stats_queue_save=original_stats_queue_save; hooks->stats_queue_save=callback_stats_queue_save;
  originals->stats_load_failed=original_stats_load_failed; hooks->stats_load_failed=callback_stats_load_failed;
  originals->stats_save=original_stats_save; hooks->stats_save=callback_stats_save;
  originals->stats_load=original_stats_load; hooks->stats_load=callback_stats_load;
  originals->cloud_available=original_cloud_available; hooks->cloud_available=callback_cloud_available;
  originals->profile_stats_failed=original_profile_stats_failed; hooks->profile_stats_failed=callback_profile_stats_failed;
  originals->profile_stats_synced=original_profile_stats_synced; hooks->profile_stats_synced=callback_profile_stats_synced;
  originals->mpstats_load_update=original_mpstats_load_update; hooks->mpstats_load_update=callback_mpstats_load_update;
  originals->mpstats_save_update=original_mpstats_save_update; hooks->mpstats_save_update=callback_mpstats_save_update;
  originals->ros_credentials_valid=original_ros_credentials_valid; hooks->ros_credentials_valid=callback_ros_credentials_valid;
  originals->post_member_file=original_post_member_file; hooks->post_member_file=callback_post_member_file;
  originals->get_member_file=original_get_member_file; hooks->get_member_file=callback_get_member_file;
  originals->ugc_query_content=original_ugc_query_content; hooks->ugc_query_content=callback_ugc_query_content;
  originals->grow_buffer_append=original_grow_buffer_append; hooks->grow_buffer_append=callback_grow_buffer_append;
  originals->grow_buffer_file_name=original_grow_buffer_file_name; hooks->grow_buffer_file_name=callback_grow_buffer_file_name;
  originals->stat_find=original_stat_find; hooks->stat_find=callback_stat_find;
  originals->packed_key=original_packed_key; hooks->packed_key=callback_packed_key;
  originals->packed_get=original_packed_get; hooks->packed_get=callback_packed_get;
  originals->packed_set=original_packed_set; hooks->packed_set=callback_packed_set;
  originals->stat_get_int=original_stat_get_int; hooks->stat_get_int=callback_stat_get_int;
  originals->stat_get_float=original_stat_get_float; hooks->stat_get_float=callback_stat_get_float;
  originals->stat_get_bool=original_stat_get_bool; hooks->stat_get_bool=callback_stat_get_bool;
  originals->stat_get_masked_int=original_stat_get_masked_int; hooks->stat_get_masked_int=callback_stat_get_masked_int;
  originals->stat_set_int=original_stat_set_int; hooks->stat_set_int=callback_stat_set_int;
  originals->stat_set_float=original_stat_set_float; hooks->stat_set_float=callback_stat_set_float;
  originals->stat_set_bool=original_stat_set_bool; hooks->stat_set_bool=callback_stat_set_bool;
  originals->stat_set_masked_int=original_stat_set_masked_int; hooks->stat_set_masked_int=callback_stat_set_masked_int;
  originals->stat_delete_slot=original_stat_delete_slot; hooks->stat_delete_slot=callback_stat_delete_slot;
}
