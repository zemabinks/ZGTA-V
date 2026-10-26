/* Queued world tools. Included by EngineHost.c after its typed command helpers.
 * All engine calls run on the existing local control-update thread, never UIKit.
 */
static bool pg_vehicle_registry_ready(void);
static pthread_mutex_t pg_world_lock=PTHREAD_MUTEX_INITIALIZER;
static _Atomic int pg_world_active;
static _Atomic int pg_spawn_status,pg_waypoint_status;
static char pg_spawn_model_name[64];
static uint32_t pg_spawn_model_hash;
static char pg_spawn_next_name[64];
static uint32_t pg_spawn_next_hash;
static bool pg_spawn_next;
static int pg_spawn_frames;
static double pg_world_started;
static bool pg_spawn_requested,pg_waypoint_scene;
static uint32_t pg_world_pending_model;
static bool pg_world_pending_scene;
static uint64_t pg_world_vectors;
static uint32_t pg_waypoint_ped,pg_waypoint_entity,pg_waypoint_vehicle;
static unsigned pg_waypoint_frames;
static float pg_waypoint_x,pg_waypoint_y;

static bool pg_world_signature(const char* name,const char* signature,unsigned result) {
  uint32_t params[8]={0},actual=0;const size_t count=strlen(signature);
  if(mugoat_command_info(name,params,8,&actual)!=(int)count||actual!=result)return false;
  for(size_t i=0;i<count;i++)if(params[i]!=(unsigned)(signature[i]-'0'))return false;
  return true;
}
static bool pg_world_call(w2c_game* instance,const char* name,const MugoatValue* args,unsigned count,uint32_t* value) {
  MugoatValue result={0};
  if(!mugoat_command_call(instance,name,args,count,&result))return false;
  if(value)*value=(uint32_t)result.bits;
  return true;
}
static bool pg_world_coords_valid(float x,float y,float z) {
  return isfinite(x)&&isfinite(y)&&isfinite(z)&&fabsf(x)<=20000&&fabsf(y)<=20000&&z>=-100&&z<=2000;
}
static bool pg_world_storage(w2c_game* instance) {
  // One bounded reusable allocation shared by both tools; no allocation per request.
  if(!pg_world_vectors)pg_world_vectors=w2c_game_f100(instance,128);
  return pg_world_vectors!=0;
}
static void pg_world_vector(uint64_t at,float x,float y,float z) {
  float* v=pg_pointer(&env,at,24);v[0]=x;v[1]=0;v[2]=y;v[3]=0;v[4]=z;v[5]=0;
}
static bool pg_world_control(w2c_game* instance,uint32_t entity) {
  if(PGWorldToolsMode()!=2)return true;
  uint32_t networked=0,control=0;MugoatValue args[]={mg_u32(entity)};
  if(!pg_world_call(instance,"mp:NetworkGetEntityIsNetworked",args,1,&networked))return false;
  return !networked||(pg_world_call(instance,"mp:NetworkHasControlOfEntity",args,1,&control)&&control!=0);
}
static bool pg_world_script_active(w2c_game* instance) {
  u64* base=w2c_game_mugoat0x3Atls0x2Dbase(instance);
  return base&&*(uint64_t*)pg_pointer(&env,*base+3088,8)!=0;
}
static uint64_t pg_world_enter_script(w2c_game* instance) {
  if(PGWorldToolsMode()!=2)return pg_enter_script(instance,true);
  // CreateVehicle(isNetwork=true) needs an actual network script handler. The
  // offline "main"/first-script fallback is not a valid owner in Engine LAN.
  u64* base=w2c_game_mugoat0x3Atls0x2Dbase(instance);if(!base)return 0;
  uint64_t* active=pg_pointer(&env,*base+3088,8),previous=*active;*active=0;
  uint64_t threads=*(uint64_t*)pg_pointer(&env,15409704,8);
  uint16_t count=*(uint16_t*)pg_pointer(&env,15409712,2);
  if(count>1024||!pg_world_signature("mp:NetworkGetThisScriptIsNetworkScript","",1))return previous;
  for(uint16_t i=0;i<count;i++){
    uint64_t thread=*(uint64_t*)pg_pointer(&env,threads+8ull*i,8);if(!thread)continue;
    if(strcmp(pg_string(&env,thread+428),"freemode"))continue;
    *active=thread;uint32_t networked=0;
    if(pg_world_call(instance,"mp:NetworkGetThisScriptIsNetworkScript",NULL,0,&networked)&&networked)return previous;
    *active=0;
  }
  return previous;
}
static void pg_world_finish(w2c_game* instance,int tool,int status) {
  // A disappearing script must never turn cleanup into an unsafe native call.
  // Remember at most one owned model/scene until a valid engine script returns.
  if(tool==1&&pg_spawn_requested){
    MugoatValue args[]={mg_u32(pg_spawn_model_hash)};
    if(!pg_world_script_active(instance)||!pg_world_call(instance,"mp:SetModelAsNoLongerNeeded",args,1,NULL))pg_world_pending_model=pg_spawn_model_hash;
    pg_spawn_requested=false;
  }
  if(tool==2&&pg_waypoint_scene){
    if(!pg_world_script_active(instance)||!pg_world_call(instance,"mp:NewLoadSceneStop",NULL,0,NULL))pg_world_pending_scene=true;
    pg_waypoint_scene=false;
  }
  atomic_store(tool==1?&pg_spawn_status:&pg_waypoint_status,status);
  atomic_store(&pg_world_active,0);
}
static void pg_process_world_cleanup(w2c_game* instance) {
  pthread_mutex_lock(&pg_world_lock);
  if(pg_world_pending_model||pg_world_pending_scene){
    uint64_t previous=pg_world_enter_script(instance);
    if(pg_world_script_active(instance)){
      if(pg_world_pending_model){MugoatValue args[]={mg_u32(pg_world_pending_model)};if(pg_world_call(instance,"mp:SetModelAsNoLongerNeeded",args,1,NULL))pg_world_pending_model=0;}
      if(pg_world_pending_scene&&pg_world_call(instance,"mp:NewLoadSceneStop",NULL,0,NULL))pg_world_pending_scene=false;
    }
    pg_test_leave_script(instance,previous);
  }
  pthread_mutex_unlock(&pg_world_lock);
}
static bool pg_world_mode_signatures(int mode) {
  return mode!=2||(pg_world_signature("mp:NetworkGetThisScriptIsNetworkScript","",1)&&pg_world_signature("mp:NetworkGetEntityIsNetworked","1",1)&&pg_world_signature("mp:NetworkHasControlOfEntity","1",1));
}

int PGQueueSpawnVehicle(const char* modelName) {
  pthread_mutex_lock(&pg_world_lock);
  char clean[64];uint32_t hash=0;
  int result=PGVehicleSpawnInvalidModel;
  if(!PGWorldToolsMode()){result=PGVehicleSpawnUnavailable;goto rejected;}
  if(!modelName)goto rejected;
  // Bound the read and reject oversized names instead of spawning a truncated name.
  size_t raw=strnlen(modelName,128);if(raw==128)goto rejected;
  while(raw&&strchr(" \t\r\n",*modelName)){modelName++;raw--;}
  while(raw&&strchr(" \t\r\n",modelName[raw-1]))raw--;
  if(!raw||raw>=sizeof pg_spawn_model_name)goto rejected;
  for(size_t i=0;i<raw;i++){
    unsigned char c=(unsigned char)modelName[i];
    clean[i]=(char)(c>='A'&&c<='Z'?c+('a'-'A'):c);
  }
  clean[raw]=0;
  if(!strcmp(clean,"mbs1k"))strcpy(clean,"mbslk");
  if(clean[0]=='0'&&clean[1]=='x'){
    if(raw<3||raw>10)goto rejected;
    for(size_t i=2;i<raw;i++)if(!strchr("0123456789abcdef",clean[i]))goto rejected;
    char* end=NULL;unsigned long parsed=strtoul(clean,&end,16);
    if(!end||*end||!parsed||parsed>UINT32_MAX)goto rejected;hash=(uint32_t)parsed;
  }else{
    if(clean[0]<'a'||clean[0]>'z')goto rejected;
    for(size_t i=1;i<raw;i++){char c=clean[i];if(!((c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='_'))goto rejected;}
    hash=pg_joaat(clean);if(!hash)goto rejected;
  }
  if(atomic_load(&pg_world_active)==2||pg_world_pending_scene){result=PGVehicleSpawnBusy;goto rejected;}
  if(atomic_load(&pg_world_active)==1||pg_world_pending_model||pg_spawn_next){
    // Mailbox only: UIKit never releases or mutates the engine's current model.
    strcpy(pg_spawn_next_name,clean);pg_spawn_next_hash=hash;pg_spawn_next=true;
    atomic_store(&pg_spawn_status,1);pthread_mutex_unlock(&pg_world_lock);return 1;
  }
  strcpy(pg_spawn_model_name,clean);pg_spawn_model_hash=hash;
  pg_spawn_frames=0;pg_world_started=timeMS(CLOCK_MONOTONIC);pg_spawn_requested=false;atomic_store(&pg_world_active,1);atomic_store(&pg_spawn_status,1);
  pthread_mutex_unlock(&pg_world_lock);return 1;
rejected:
  pthread_mutex_unlock(&pg_world_lock);return result;
}
bool PGSpawnVehicle(const char* modelName){return PGQueueSpawnVehicle(modelName)==1;}
int PGSpawnVehicleStatus(void){return atomic_load(&pg_spawn_status);}

static bool pg_spawn_signatures(int mode) {
  return pg_world_mode_signatures(mode)&&pg_world_signature("mp:RequestModel","1",0)&&pg_world_signature("mp:HasModelLoaded","1",1)&&
    pg_world_signature("mp:SetModelAsNoLongerNeeded","1",0)&&pg_world_signature("mp:PlayerPedId","",1)&&
    pg_world_signature("mp:DoesEntityExist","1",1)&&pg_world_signature("mp:GetEntityCoords","211",0)&&
    pg_world_signature("mp:GetEntityHeading","1",3)&&pg_world_signature("mp:CreateVehicle","123111",1)&&
    pg_world_signature("mp:IsPedInAnyVehicle","11",1)&&pg_world_signature("mp:GetVehiclePedIsIn","11",1)&&
    pg_world_signature("mp:TaskLeaveVehicle","111",0)&&pg_world_signature("mp:ClearPedTasksImmediately","1",0)&&
    pg_world_signature("mp:SetPedIntoVehicle","111",0)&&pg_world_signature("mp:SetVehicleEngineOn","1111",0);
}
static void pg_process_vehicle_spawn(w2c_game* instance) {
  pg_process_world_cleanup(instance);
  pthread_mutex_lock(&pg_world_lock);
  if(pg_spawn_next){
    if(atomic_load(&pg_world_active)==1){
      uint64_t previous=pg_world_enter_script(instance);
      // Keep the accepted replacement's status pending even during old cleanup.
      pg_world_finish(instance,1,1);
      pg_test_leave_script(instance,previous);
    }
    atomic_store(&pg_spawn_status,1);
    if(pg_world_pending_model||pg_world_pending_scene){pthread_mutex_unlock(&pg_world_lock);return;}
    strcpy(pg_spawn_model_name,pg_spawn_next_name);pg_spawn_model_hash=pg_spawn_next_hash;
    pg_spawn_next=false;pg_spawn_frames=0;pg_world_started=timeMS(CLOCK_MONOTONIC);pg_spawn_requested=false;
    atomic_store(&pg_world_active,1);
  }
  if(atomic_load(&pg_world_active)!=1){pthread_mutex_unlock(&pg_world_lock);return;}
  double now=timeMS(CLOCK_MONOTONIC);if(!pg_world_started)pg_world_started=now;
  bool expired=++pg_spawn_frames>1800||now-pg_world_started>=30000;
  uint64_t previous=pg_world_enter_script(instance);int mode=PGWorldToolsMode();
  if(expired){pg_log("Spawn vehicle: model streaming timed out; releasing its owned request when script context is available.");pg_world_finish(instance,1,PGVehicleSpawnTimedOut);goto done;}
  if(!pg_world_script_active(instance))goto done;
  if(!mode||!pg_spawn_signatures(mode)||!pg_world_storage(instance)){pg_world_finish(instance,1,PGVehicleSpawnUnavailable);goto done;}
  MugoatValue model[]={mg_u32(pg_spawn_model_hash)};uint32_t loaded=0;
  if(pg_vehicle_registry_ready()&&pg_world_signature("mp:IsModelInCdImage","1",1)&&pg_world_signature("mp:IsModelAVehicle","1",1)){
    uint32_t present=0,isVehicle=0;
    if(pg_world_call(instance,"mp:IsModelInCdImage",model,1,&present)&&pg_world_call(instance,"mp:IsModelAVehicle",model,1,&isVehicle)&&(!present||!isVehicle)){pg_world_finish(instance,1,PGVehicleSpawnModelMissing);goto done;}
  }
  if(!pg_world_call(instance,"mp:RequestModel",model,1,NULL)){pg_world_finish(instance,1,PGVehicleSpawnUnavailable);goto done;}pg_spawn_requested=true;
  if(!pg_world_call(instance,"mp:HasModelLoaded",model,1,&loaded)){pg_world_finish(instance,1,PGVehicleSpawnUnavailable);goto done;}if(!loaded)goto done;
  uint32_t ped=0,exists=0;
  if(!pg_world_call(instance,"mp:PlayerPedId",NULL,0,&ped)||!ped){pg_world_finish(instance,1,PGVehicleSpawnNoPlayer);goto done;}
  MugoatValue entity[]={mg_u32(ped)};
  if(!pg_world_call(instance,"mp:DoesEntityExist",entity,1,&exists)||!exists){pg_world_finish(instance,1,PGVehicleSpawnNoPlayer);goto done;}
  if(!pg_world_control(instance,ped)){pg_world_finish(instance,1,PGVehicleSpawnNoControl);goto done;}
  MugoatValue coordsArgs[]={mg_u64(pg_world_vectors),mg_u32(ped),mg_u32(1)};
  if(!pg_world_call(instance,"mp:GetEntityCoords",coordsArgs,3,NULL)){pg_world_finish(instance,1,PGVehicleSpawnUnavailable);goto done;}
  float* coords=pg_pointer(&env,pg_world_vectors,24);float px=coords[0],py=coords[2],pz=coords[4];
  float heading=mg_call_f32(instance,"mp:GetEntityHeading",entity,1);
  if(!pg_world_coords_valid(px,py,pz)||!isfinite(heading)){pg_world_finish(instance,1,PGVehicleSpawnInvalidPosition);goto done;}
  float rad=heading*0.0174532925f;uint64_t vector=pg_world_vectors+32;
  pg_world_vector(vector,px-sinf(rad)*4.5f,py+cosf(rad)*4.5f,pz+0.5f);
  // Networked entity, without requiring this client to host freemode.
  // Pinned CreateVehicle ABI: model, vector, heading, isNetwork, bScriptHostVeh, dynamic.
  MugoatValue args[]={mg_u32(pg_spawn_model_hash),mg_u64(vector),mg_f32(heading),mg_u32(mode==2),mg_u32(0),mg_u32(0)};uint32_t vehicle=0;
  if(!pg_world_call(instance,"mp:CreateVehicle",args,6,&vehicle)){pg_world_finish(instance,1,PGVehicleSpawnUnavailable);goto done;}
  if(!vehicle){pg_world_vector(vector,px-sinf(rad)*4.5f,py+cosf(rad)*4.5f,pz+1.2f);pg_world_call(instance,"mp:CreateVehicle",args,6,&vehicle);}
  if(!vehicle){pg_world_finish(instance,1,PGVehicleSpawnCreateFailed);goto done;}
  if(!pg_world_control(instance,vehicle)){pg_log("Spawn vehicle: local ownership unavailable; player unchanged.");pg_world_finish(instance,1,PGVehicleSpawnNoControl);goto done;}
  MugoatValue inVehicle[]={mg_u32(ped),mg_u32(0)};uint32_t inside=0,old=0;
  if(!pg_world_call(instance,"mp:IsPedInAnyVehicle",inVehicle,2,&inside)){pg_world_finish(instance,1,PGVehicleSpawnUnavailable);goto done;}
  if(inside){pg_world_call(instance,"mp:GetVehiclePedIsIn",inVehicle,2,&old);if(old){MugoatValue leave[]={mg_u32(ped),mg_u32(old),mg_u32(16)};pg_world_call(instance,"mp:TaskLeaveVehicle",leave,3,NULL);}}
  pg_world_call(instance,"mp:ClearPedTasksImmediately",entity,1,NULL);
  MugoatValue sit[]={mg_u32(ped),mg_u32(vehicle),mg_u32(UINT32_MAX)},engine[]={mg_u32(vehicle),mg_u32(1),mg_u32(1),mg_u32(0)};
  if(!pg_world_call(instance,"mp:SetPedIntoVehicle",sit,3,NULL)||!pg_world_call(instance,"mp:SetVehicleEngineOn",engine,4,NULL)){pg_world_finish(instance,1,PGVehicleSpawnUnavailable);goto done;}
  pg_log("Spawn vehicle: created locally controlled vehicle; model request released.");pg_world_finish(instance,1,2);
done:pg_test_leave_script(instance,previous);pthread_mutex_unlock(&pg_world_lock);
}

bool PGTeleportToWaypoint(void) {
  pthread_mutex_lock(&pg_world_lock);
  if(!PGWorldToolsMode()){atomic_store(&pg_waypoint_status,PGWaypointUnavailable);pthread_mutex_unlock(&pg_world_lock);return false;}
  if(atomic_load(&pg_world_active)||pg_world_pending_model||pg_world_pending_scene||pg_spawn_next){if(atomic_load(&pg_world_active)!=2)atomic_store(&pg_waypoint_status,PGWaypointBusy);pthread_mutex_unlock(&pg_world_lock);return false;}
  pg_waypoint_ped=pg_waypoint_entity=pg_waypoint_vehicle=0;pg_waypoint_scene=false;pg_waypoint_frames=0;pg_world_started=timeMS(CLOCK_MONOTONIC);
  atomic_store(&pg_waypoint_status,PGWaypointPending);atomic_store(&pg_world_active,2);pthread_mutex_unlock(&pg_world_lock);return true;
}
int PGTeleportToWaypointStatus(void){return atomic_load(&pg_waypoint_status);}
static bool pg_waypoint_signatures(int mode) {
  return pg_world_mode_signatures(mode)&&pg_world_signature("mp:PlayerPedId","",1)&&pg_world_signature("mp:DoesEntityExist","1",1)&&
    pg_world_signature("mp:IsPedDeadOrDying","11",1)&&pg_world_signature("mp:GetFirstBlipInfoId","1",1)&&pg_world_signature("mp:DoesBlipExist","1",1)&&
    pg_world_signature("mp:GetBlipInfoIdCoord","21",0)&&pg_world_signature("mp:IsPedInAnyVehicle","11",1)&&pg_world_signature("mp:GetVehiclePedIsIn","11",1)&&
    pg_world_signature("mp:GetPedInVehicleSeat","111",1)&&pg_world_signature("mp:IsNewLoadSceneActive","",1)&&pg_world_signature("mp:NewLoadSceneStartSphere","231",1)&&
    pg_world_signature("mp:IsNewLoadSceneLoaded","",1)&&pg_world_signature("mp:NewLoadSceneStop","",0)&&pg_world_signature("mp:RequestCollisionAtCoord","2",0)&&
    pg_world_signature("mp:GetGroundZFor3dCoord","2211",1)&&pg_world_signature("mp:SetEntityCoordsNoOffset","12111",0)&&pg_world_signature("mp:SetEntityVelocity","12",0);
}
static int pg_waypoint_local_entity(w2c_game* instance,uint32_t* ped,uint32_t* vehicle,uint32_t* entity) {
  uint32_t exists=0,dead=0,inside=0;
  if(!pg_world_call(instance,"mp:PlayerPedId",NULL,0,ped)||!*ped)return PGWaypointNoLocalPlayer;
  MugoatValue p[]={mg_u32(*ped)},p2[]={mg_u32(*ped),mg_u32(0)};
  if(!pg_world_call(instance,"mp:DoesEntityExist",p,1,&exists)||!exists||!pg_world_call(instance,"mp:IsPedDeadOrDying",p2,2,&dead)||dead)return PGWaypointNoLocalPlayer;
  if(!pg_world_control(instance,*ped))return PGWaypointNoControl;
  if(!pg_world_call(instance,"mp:IsPedInAnyVehicle",p2,2,&inside))return PGWaypointUnavailable;
  *vehicle=0;*entity=*ped;
  if(inside){
    if(!pg_world_call(instance,"mp:GetVehiclePedIsIn",p2,2,vehicle)||!*vehicle)return PGWaypointNoControl;
    MugoatValue seat[]={mg_u32(*vehicle),mg_u32(UINT32_MAX),mg_u32(0)},v[]={mg_u32(*vehicle)};uint32_t driver=0;
    if(!pg_world_call(instance,"mp:DoesEntityExist",v,1,&exists)||!exists||!pg_world_call(instance,"mp:GetPedInVehicleSeat",seat,3,&driver)||driver!=*ped||!pg_world_control(instance,*vehicle))return PGWaypointNoControl;
    *entity=*vehicle;
  }
  return 0;
}
static void pg_process_waypoint_teleport(w2c_game* instance) {
  if(atomic_load(&pg_world_active)!=2)return;
  pthread_mutex_lock(&pg_world_lock);
  if(atomic_load(&pg_world_active)!=2){pthread_mutex_unlock(&pg_world_lock);return;}
  double now=timeMS(CLOCK_MONOTONIC);if(!pg_world_started)pg_world_started=now;
  bool expired=++pg_waypoint_frames>900||now-pg_world_started>=15000;
  uint64_t previous=pg_world_enter_script(instance);int mode=PGWorldToolsMode();
  if(expired){pg_world_finish(instance,2,PGWaypointTimedOut);goto done;}
  if(!pg_world_script_active(instance))goto done;
  if(!mode||!pg_waypoint_signatures(mode)||!pg_world_storage(instance)){pg_world_finish(instance,2,PGWaypointUnavailable);goto done;}
  uint32_t ped=0,vehicle=0,entity=0;int failure=pg_waypoint_local_entity(instance,&ped,&vehicle,&entity);
  if(failure){pg_world_finish(instance,2,failure);goto done;}
  if(!pg_waypoint_scene){
    uint32_t blip=0,exists=0,active=0;MugoatValue waypoint[]={mg_u32(8)};
    if(!pg_world_call(instance,"mp:GetFirstBlipInfoId",waypoint,1,&blip)){pg_world_finish(instance,2,PGWaypointUnavailable);goto done;}
    MugoatValue b[]={mg_u32(blip)};
    if(!blip||!pg_world_call(instance,"mp:DoesBlipExist",b,1,&exists)||!exists){pg_world_finish(instance,2,PGWaypointNoWaypoint);goto done;}
    MugoatValue coordinate[]={mg_u64(pg_world_vectors),mg_u32(blip)};
    if(!pg_world_call(instance,"mp:GetBlipInfoIdCoord",coordinate,2,NULL)){pg_world_finish(instance,2,PGWaypointUnavailable);goto done;}
    float* v=pg_pointer(&env,pg_world_vectors,24);
    if(!pg_world_coords_valid(v[0],v[2],v[4])){pg_world_finish(instance,2,PGWaypointInvalidGround);goto done;}
    pg_waypoint_x=v[0];pg_waypoint_y=v[2];pg_waypoint_ped=ped;pg_waypoint_vehicle=vehicle;pg_waypoint_entity=entity;
    if(!pg_world_call(instance,"mp:IsNewLoadSceneActive",NULL,0,&active)){pg_world_finish(instance,2,PGWaypointUnavailable);goto done;}
    if(active){pg_world_finish(instance,2,PGWaypointStreamingBusy);goto done;}
    MugoatValue scene[]={mg_u64(pg_world_vectors),mg_f32(150),mg_u32(0)};uint32_t accepted=0;
    if(!pg_world_call(instance,"mp:NewLoadSceneStartSphere",scene,3,&accepted)||!accepted){pg_world_finish(instance,2,PGWaypointStreamingBusy);goto done;}
    pg_waypoint_scene=true;
  }else if(ped!=pg_waypoint_ped||vehicle!=pg_waypoint_vehicle||entity!=pg_waypoint_entity){pg_world_finish(instance,2,PGWaypointPlayerChanged);goto done;}
  // Probe collision at bounded heights without moving the player into the sky.
  static const float heights[]={0,100,250,500,800,1000};
  pg_world_vector(pg_world_vectors+32,pg_waypoint_x,pg_waypoint_y,heights[(pg_waypoint_frames-1)%6]);
  MugoatValue collision[]={mg_u64(pg_world_vectors+32)};uint32_t sceneLoaded=0;
  if(!pg_world_call(instance,"mp:RequestCollisionAtCoord",collision,1,NULL)||!pg_world_call(instance,"mp:IsNewLoadSceneLoaded",NULL,0,&sceneLoaded)){pg_world_finish(instance,2,PGWaypointUnavailable);goto done;}
  if(!sceneLoaded)goto done;
  pg_world_vector(pg_world_vectors+32,pg_waypoint_x,pg_waypoint_y,1000);*(float*)pg_pointer(&env,pg_world_vectors+124,4)=NAN;
  MugoatValue ground[]={mg_u64(pg_world_vectors+32),mg_u64(pg_world_vectors+124),mg_u32(0),mg_u32(0)};uint32_t found=0;
  if(!pg_world_call(instance,"mp:GetGroundZFor3dCoord",ground,4,&found)){pg_world_finish(instance,2,PGWaypointUnavailable);goto done;}
  if(!found)goto done;
  float z=*(float*)pg_pointer(&env,pg_world_vectors+124,4);
  if(!pg_world_coords_valid(pg_waypoint_x,pg_waypoint_y,z)||z>1000){pg_world_finish(instance,2,PGWaypointInvalidGround);goto done;}
  // All prerequisites are ready; recheck the local target immediately before mutation.
  failure=pg_waypoint_local_entity(instance,&ped,&vehicle,&entity);
  if(failure||ped!=pg_waypoint_ped||vehicle!=pg_waypoint_vehicle||entity!=pg_waypoint_entity){pg_world_finish(instance,2,failure?failure:PGWaypointPlayerChanged);goto done;}
  pg_world_vector(pg_world_vectors+64,pg_waypoint_x,pg_waypoint_y,z+(vehicle?1.5f:1.0f));pg_world_vector(pg_world_vectors+96,0,0,0);
  MugoatValue velocity[]={mg_u32(entity),mg_u64(pg_world_vectors+96)},target[]={mg_u32(entity),mg_u64(pg_world_vectors+64),mg_u32(0),mg_u32(0),mg_u32(0)};
  if(!pg_world_call(instance,"mp:SetEntityVelocity",velocity,2,NULL)||!pg_world_call(instance,"mp:SetEntityCoordsNoOffset",target,5,NULL)){pg_world_finish(instance,2,PGWaypointUnavailable);goto done;}
  pg_log("Waypoint teleport: local entity moved after destination ground/collision readiness.");pg_world_finish(instance,2,PGWaypointSuccess);
done:pg_test_leave_script(instance,previous);pthread_mutex_unlock(&pg_world_lock);
}

#include "VehicleAvailability.inc"
