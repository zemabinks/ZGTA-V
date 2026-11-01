/* Included after NativeWorldTools.inc. Position is sampled on the existing
 * game control thread, with the same validated freemode script context used by
 * world tools. Never call engine natives from an audio/network/UI thread. */
static void pg_process_voice_position(w2c_game *instance) {
  if(!ZemaLabEnabled())return;
  static double last;
  double now=timeMS(CLOCK_MONOTONIC);if(now-last<100)return;last=now;
  bool valid=false;float x=0,y=0,z=0;
  pthread_mutex_lock(&pg_world_lock);
  uint64_t previous=pg_world_enter_script(instance);
  if(pg_world_script_active(instance)&&pg_world_storage(instance)&&
     pg_world_signature("mp:PlayerPedId","",1)&&pg_world_signature("mp:DoesEntityExist","1",1)&&
     pg_world_signature("mp:GetEntityCoords","211",0)){
    uint32_t ped=0,exists=0;
    if(pg_world_call(instance,"mp:PlayerPedId",NULL,0,&ped)&&ped){
      MugoatValue entity[]={mg_u32(ped)};
      if(pg_world_call(instance,"mp:DoesEntityExist",entity,1,&exists)&&exists){
        MugoatValue args[]={mg_u64(pg_world_vectors+96),mg_u32(ped),mg_u32(1)};
        if(pg_world_call(instance,"mp:GetEntityCoords",args,3,NULL)){
          float *v=pg_pointer(&env,pg_world_vectors+96,24);x=v[0];y=v[2];z=v[4];valid=pg_world_coords_valid(x,y,z);
        }
      }
    }
  }
  pg_test_leave_script(instance,previous);pthread_mutex_unlock(&pg_world_lock);
  ZemaVoiceSetPosition(x,y,z,valid);
}
