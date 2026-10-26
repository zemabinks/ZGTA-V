/* Pure registration probes: no streaming requests, file writes or spawn side effects.
 * pg_world_lock protects UI admission and the bounded engine-thread cache.
 */
enum { PG_MODEL_SLOTS=2048 };
static struct { uint32_t hash; int state; } pg_model_probes[PG_MODEL_SLOTS];
static _Atomic bool pg_model_probe_ready;
static bool pg_vehicle_registry_ready(void){return atomic_load(&pg_model_probe_ready);}
static unsigned pg_model_probe_cursor;
static bool pg_model_probe_pending;
int PGVehicleModelAvailability(const char* name) {
  if(!atomic_load(&pg_model_probe_ready)||!name)return -1;
  size_t length=strnlen(name,64);if(!length||length>=64||name[0]<'a'||name[0]>'z')return -1;
  for(size_t n=1;n<length;n++)if(!((name[n]>='a'&&name[n]<='z')||(name[n]>='0'&&name[n]<='9')||name[n]=='_'))return -1;
  uint32_t hash=pg_joaat(name);if(!hash)return -1;
  pthread_mutex_lock(&pg_world_lock);int result=-1;
  for(unsigned n=0;n<PG_MODEL_SLOTS;n++){
    unsigned at=(hash+n)%PG_MODEL_SLOTS;
    if(!pg_model_probes[at].hash){pg_model_probes[at].hash=hash;pg_model_probes[at].state=1;pg_model_probe_pending=true;result=2;break;}
    if(pg_model_probes[at].hash==hash){int state=pg_model_probes[at].state;result=state==1?2:state==2?0:state==3?1:state==4?-2:-1;break;}
  }
  pthread_mutex_unlock(&pg_world_lock);return result;
}
static void pg_process_vehicle_availability(w2c_game* instance) {
  // Same pinned original loading-state address/hash as browser_features.py.
  if(!PGWorldToolsMode()||*(uint32_t*)pg_pointer(&env,19473636,4)!=0){atomic_store(&pg_model_probe_ready,false);return;}
  bool ready=false;pthread_mutex_lock(&pg_world_lock);uint64_t previous=pg_world_enter_script(instance);
  if(!pg_world_script_active(instance)||!pg_world_signature("mp:IsModelInCdImage","1",1)||!pg_world_signature("mp:IsModelAVehicle","1",1))goto done;
  uint32_t ped=0,exists=0;
  if(!pg_world_call(instance,"mp:PlayerPedId",NULL,0,&ped)||!ped)goto done;
  MugoatValue entity[]={mg_u32(ped)};
  if(!pg_world_call(instance,"mp:DoesEntityExist",entity,1,&exists)||!exists)goto done;
  ready=true;atomic_store(&pg_model_probe_ready,true);
  if(!pg_model_probe_pending)goto done;
  pg_model_probe_pending=false;unsigned queried=0;
  for(unsigned checked=0;checked<PG_MODEL_SLOTS&&queried<8;checked++){
    unsigned at=pg_model_probe_cursor++%PG_MODEL_SLOTS;if(pg_model_probes[at].state!=1)continue;
    MugoatValue args[]={mg_u32(pg_model_probes[at].hash)};uint32_t present=0,isVehicle=0;
    bool ok=pg_world_call(instance,"mp:IsModelInCdImage",args,1,&present)&&pg_world_call(instance,"mp:IsModelAVehicle",args,1,&isVehicle);
    pg_model_probes[at].state=!ok?5:!present?2:isVehicle?3:4;queried++;
  }
  if(queried==8)pg_model_probe_pending=true;
done:if(!ready)atomic_store(&pg_model_probe_ready,false);pg_test_leave_script(instance,previous);pthread_mutex_unlock(&pg_world_lock);
}
