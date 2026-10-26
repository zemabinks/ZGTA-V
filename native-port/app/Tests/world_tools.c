/* Executes the production queued world-tool logic with typed synthetic engine commands. */
#include "EngineHost.h"
#include "MugoatOnline.h"
#include <assert.h>
#include <math.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <time.h>
typedef uint32_t u32;typedef uint64_t u64;typedef struct {int unused;} w2c_game;
static int env;
static unsigned char memory[4096];
static double clock_ms=1000;
static int mode=1,engine_tick;
static uint32_t loading; static bool cd_image=true,is_vehicle=true;
static uint32_t ped=41,vehicle,driver=41,created=200;
static bool ped_control=true,vehicle_control=true,model_loaded=true,scene_active,scene_loaded,ground_found;
static float wx=100,wy=200,wz=0,ground_z=20;
static unsigned creates,seats,moves,velocities,requests,releases,starts,stops,collisions,ownership_calls,actual_calls;
static unsigned network_flag,host_flag;
static uint64_t active_script=77,tls_base=64;
static bool no_script,network_script_ready=true,script_host=true;
static uint64_t* w2c_game_mugoat0x3Atls0x2Dbase(w2c_game* i){(void)i;return &tls_base;}
static const char* missing_command;
static const char* rejected_command;
int PGWorldToolsMode(void){return mode;}
static double timeMS(clockid_t unused){(void)unused;return clock_ms;}
static void* pg_pointer(void* unused,uint64_t p,uint64_t n){(void)unused;if(p==19473636)return &loading;if(p==15409704)p=3200;if(p==15409712)p=3208;assert(p<=sizeof memory&&n<=sizeof memory-p);return memory+p;}
static const char* pg_string(void* unused,uint64_t p){const char* s=pg_pointer(unused,p,32);assert(memchr(s,0,32));return s;}
static uint64_t w2c_game_f100(w2c_game* i,uint64_t n){(void)i;assert(engine_tick&&n==128);return 256;}
static uint64_t pg_enter_script(w2c_game* i,bool fallback){(void)i;assert(engine_tick&&fallback);uint64_t old=active_script;active_script=no_script?0:(mode==2?11:99);memcpy(memory+tls_base+3088,&active_script,8);return old;}
static void pg_test_leave_script(w2c_game* i,uint64_t previous){(void)i;uint64_t actual;memcpy(&actual,memory+tls_base+3088,8);assert(actual==0||actual==11||actual==99);active_script=previous;memcpy(memory+tls_base+3088,&active_script,8);}
static void pg_log(const char* s){assert(s&&engine_tick);}
static uint32_t pg_joaat(const char* s){uint32_t h=0;for(;*s;s++){h+=(unsigned char)*s;h+=h<<10;h^=h>>6;}h+=h<<3;h^=h>>11;h+=h<<15;return h;}
static MugoatValue mg_u32(uint32_t v){return (MugoatValue){1,0,v};}
static MugoatValue mg_u64(uint64_t v){return (MugoatValue){2,0,v};}
static MugoatValue mg_f32(float f){uint32_t b;memcpy(&b,&f,4);return (MugoatValue){3,0,b};}
static float mg_call_f32(w2c_game* i,const char* name,const MugoatValue* a,uint32_t n){MugoatValue v={0};assert(mugoat_command_call(i,name,a,n,&v));float f;uint32_t bits=(uint32_t)v.bits;memcpy(&f,&bits,4);return f;}
static const struct {const char* name;const char* params;unsigned result;} commands[]={
 {"NetworkGetThisScriptIsNetworkScript","",1},
 {"PlayerPedId","",1},{"DoesEntityExist","1",1},{"IsPedDeadOrDying","11",1},
 {"GetFirstBlipInfoId","1",1},{"DoesBlipExist","1",1},{"GetBlipInfoIdCoord","21",0},
 {"IsPedInAnyVehicle","11",1},{"GetVehiclePedIsIn","11",1},{"GetPedInVehicleSeat","111",1},
 {"NetworkGetEntityIsNetworked","1",1},{"NetworkHasControlOfEntity","1",1},
 {"IsNewLoadSceneActive","",1},{"NewLoadSceneStartSphere","231",1},{"IsNewLoadSceneLoaded","",1},{"NewLoadSceneStop","",0},
 {"RequestCollisionAtCoord","2",0},{"GetGroundZFor3dCoord","2211",1},{"SetEntityCoordsNoOffset","12111",0},{"SetEntityVelocity","12",0},
 {"IsModelInCdImage","1",1},{"IsModelAVehicle","1",1},{"RequestModel","1",0},{"HasModelLoaded","1",1},{"SetModelAsNoLongerNeeded","1",0},
 {"GetEntityCoords","211",0},{"GetEntityHeading","1",3},{"CreateVehicle","123111",1},
 {"TaskLeaveVehicle","111",0},{"ClearPedTasksImmediately","1",0},{"SetPedIntoVehicle","111",0},{"SetVehicleEngineOn","1111",0}
};
int mugoat_command_info(const char* name,uint32_t* params,uint32_t capacity,uint32_t* result){
 assert(engine_tick);if(missing_command&&!strcmp(name,missing_command))return -1;
 for(unsigned k=0;k<sizeof commands/sizeof *commands;k++)if(!strcmp(name+3,commands[k].name)){
  unsigned n=(unsigned)strlen(commands[k].params);assert(capacity>=n);for(unsigned j=0;j<n;j++)params[j]=(unsigned)(commands[k].params[j]-'0');*result=commands[k].result;return (int)n;
 }return -1;
}
bool mugoat_command_call(void* instance,const char* name,const MugoatValue* a,uint32_t n,MugoatValue* out){
 uint64_t actual;memcpy(&actual,memory+tls_base+3088,8);assert(instance&&engine_tick&&(actual==11||actual==99));uint32_t types[8],result;int count=mugoat_command_info(name,types,8,&result);assert(count==(int)n);
 for(unsigned i=0;i<n;i++)assert(a[i].type==types[i]);*out=(MugoatValue){result,0,0};actual_calls++;
 if(rejected_command&&!strcmp(name,rejected_command))return false;
 name+=3;
 if(!strcmp(name,"IsModelInCdImage"))out->bits=cd_image;
 else if(!strcmp(name,"IsModelAVehicle"))out->bits=is_vehicle;
 else if(!strcmp(name,"NetworkGetThisScriptIsNetworkScript"))out->bits=actual==99&&network_script_ready;
 else if(!strcmp(name,"PlayerPedId"))out->bits=ped;
 else if(!strcmp(name,"DoesEntityExist"))out->bits=a[0].bits!=0;
 else if(!strcmp(name,"IsPedDeadOrDying"))out->bits=0;
 else if(!strcmp(name,"GetFirstBlipInfoId")){assert(a[0].bits==8);out->bits=wx==999?0:7;}
 else if(!strcmp(name,"DoesBlipExist"))out->bits=a[0].bits==7;
 else if(!strcmp(name,"GetBlipInfoIdCoord")){assert(a[1].bits==7);float* v=pg_pointer(&env,a[0].bits,24);v[0]=wx;v[2]=wy;v[4]=wz;}
 else if(!strcmp(name,"IsPedInAnyVehicle")){assert(a[0].bits==ped);out->bits=vehicle!=0;}
 else if(!strcmp(name,"GetVehiclePedIsIn")){assert(a[0].bits==ped);out->bits=vehicle;}
 else if(!strcmp(name,"GetPedInVehicleSeat")){assert(a[0].bits==vehicle&&a[1].bits==UINT32_MAX);out->bits=driver;}
 else if(!strcmp(name,"NetworkGetEntityIsNetworked")){ownership_calls++;out->bits=1;}
 else if(!strcmp(name,"NetworkHasControlOfEntity")){ownership_calls++;out->bits=a[0].bits==ped?ped_control:vehicle_control;}
 else if(!strcmp(name,"IsNewLoadSceneActive"))out->bits=scene_active;
 else if(!strcmp(name,"NewLoadSceneStartSphere")){assert(!scene_active);starts++;scene_active=true;out->bits=1;}
 else if(!strcmp(name,"IsNewLoadSceneLoaded"))out->bits=scene_loaded;
 else if(!strcmp(name,"NewLoadSceneStop")){assert(scene_active);stops++;scene_active=false;}
 else if(!strcmp(name,"RequestCollisionAtCoord")){float* v=pg_pointer(&env,a[0].bits,24);assert(v[0]==wx&&v[2]==wy&&v[4]>=0&&v[4]<=1000);collisions++;}
 else if(!strcmp(name,"GetGroundZFor3dCoord")){assert(scene_loaded);out->bits=ground_found;*(float*)pg_pointer(&env,a[1].bits,4)=ground_z;}
 else if(!strcmp(name,"SetEntityCoordsNoOffset")){float* v=pg_pointer(&env,a[1].bits,24);assert(scene_loaded&&ground_found);assert(a[0].bits==(vehicle?vehicle:ped));assert(v[0]==wx&&v[2]==wy&&v[4]==ground_z+(vehicle?1.5f:1.0f));moves++;}
 else if(!strcmp(name,"SetEntityVelocity")){assert(a[0].bits==(vehicle?vehicle:ped));velocities++;}
 else if(!strcmp(name,"RequestModel"))requests++;
 else if(!strcmp(name,"HasModelLoaded"))out->bits=model_loaded;
 else if(!strcmp(name,"SetModelAsNoLongerNeeded"))releases++;
 else if(!strcmp(name,"GetEntityCoords")){assert(a[1].bits==ped);float* v=pg_pointer(&env,a[0].bits,24);v[0]=10;v[2]=20;v[4]=30;}
 else if(!strcmp(name,"GetEntityHeading")){*out=mg_f32(0);}
 else if(!strcmp(name,"CreateVehicle")){assert(a[3].bits==(unsigned)(mode==2)&&a[4].bits==0&&a[5].bits==0);network_flag=(unsigned)a[3].bits;host_flag=(unsigned)a[4].bits;creates++;out->bits=mode==2&&(actual!=99||(a[4].bits&&!script_host))?0:created;}
 else if(!strcmp(name,"SetPedIntoVehicle")){assert(a[0].bits==ped&&a[1].bits==created);seats++;}
 return true;
}
#include "NativeWorldTools.inc"
static void reset(void){assert(atomic_load(&pg_world_active)==0&&active_script==77);no_script=false;mode=1;ped=41;vehicle=0;driver=41;created=200;ped_control=vehicle_control=model_loaded=true;scene_active=scene_loaded=ground_found=false;wx=100;wy=200;wz=0;ground_z=20;creates=seats=moves=velocities=requests=releases=starts=stops=collisions=ownership_calls=actual_calls=0;network_flag=host_flag=0;missing_command=rejected_command=NULL;clock_ms=1000;}
static void tick(double ms){clock_ms+=ms;engine_tick=1;uint64_t threads=3300,main=11,freemode=99;uint16_t count=no_script?0:2;memcpy(memory+3200,&threads,8);memcpy(memory+3208,&count,2);memcpy(memory+3300,&main,8);memcpy(memory+3308,&freemode,8);strcpy((char*)memory+11+428,"main");strcpy((char*)memory+99+428,"freemode");memcpy(memory+tls_base+3088,&active_script,8);pg_process_vehicle_spawn(&(w2c_game){0});pg_process_waypoint_teleport(&(w2c_game){0});engine_tick=0;assert(active_script==77);}
static void teleport(void){assert(PGTeleportToWaypoint());assert(PGTeleportToWaypointStatus()==1);assert(actual_calls==0);}
int main(void){
 const char* invalid[]={NULL,"","   ","two words","9wrong","sultan/path","0x","0x0","0x100000000","0xzz","bad\nname","bad\xC3\xA9"};
 for(unsigned i=0;i<sizeof invalid/sizeof *invalid;i++){
  reset();int previous=PGSpawnVehicleStatus();assert(PGQueueSpawnVehicle(invalid[i])==PGVehicleSpawnInvalidModel);assert(PGSpawnVehicleStatus()==previous&&atomic_load(&pg_world_active)==0&&actual_calls==0);
 }
 char long_name[129];memset(long_name,'a',128);long_name[128]=0;
 for(unsigned n=64;n<=128;n++){long_name[n]=0;reset();assert(PGQueueSpawnVehicle(long_name)==PGVehicleSpawnInvalidModel&&actual_calls==0);long_name[n]='a';}
 long_name[63]=0;reset();assert(PGQueueSpawnVehicle(long_name)==1);assert(strlen(pg_spawn_model_name)==63&&pg_spawn_model_hash==pg_joaat(long_name));tick(1);assert(PGSpawnVehicleStatus()==2);
 reset();assert(PGQueueSpawnVehicle("  SuLtAn  ")==1&&pg_spawn_model_hash==pg_joaat("sultan"));tick(1);
 reset();assert(PGQueueSpawnVehicle("0XFFFFFFFF")==1&&pg_spawn_model_hash==UINT32_MAX);tick(1);
 reset();assert(PGQueueSpawnVehicle("mbs1k")==1&&!strcmp(pg_spawn_model_name,"mbslk"));tick(1);
 reset();assert(PGQueueSpawnVehicle("adder")==1);uint32_t original_hash=pg_spawn_model_hash;
 assert(PGQueueSpawnVehicle("invalid input")==PGVehicleSpawnInvalidModel&&PGSpawnVehicleStatus()==1&&pg_spawn_model_hash==original_hash);tick(1);assert(PGSpawnVehicleStatus()==2&&creates==1);
 // Latest valid choice wins before the first engine tick, with no old request.
 reset();model_loaded=false;assert(PGSpawnVehicle("doesnotexist"));assert(PGSpawnVehicle("adder"));assert(PGSpawnVehicle("sultan"));
 assert(actual_calls==0&&pg_spawn_model_hash==pg_joaat("doesnotexist"));model_loaded=true;tick(1);
 assert(PGSpawnVehicleStatus()==2&&pg_spawn_model_hash==pg_joaat("sultan")&&requests==1&&creates==1&&releases==1&&!pg_spawn_next);
 // A streaming model is released before its replacement is requested, without timeout.
 reset();model_loaded=false;assert(PGSpawnVehicle("doesnotexist"));tick(1);assert(requests==1&&releases==0);
 assert(PGSpawnVehicle("adder"));assert(PGSpawnVehicle("sultan"));assert(PGQueueSpawnVehicle("bad input")==PGVehicleSpawnInvalidModel);
 model_loaded=true;tick(1);assert(PGSpawnVehicleStatus()==2&&pg_spawn_model_hash==pg_joaat("sultan")&&creates==1&&requests==2&&releases==2);
 // Lost script context retains owned cleanup and the latest replacement safely.
 reset();model_loaded=false;assert(PGSpawnVehicle("doesnotexist"));tick(1);no_script=true;assert(PGSpawnVehicle("adder"));tick(1);
 assert(PGSpawnVehicleStatus()==1&&pg_world_pending_model&&pg_spawn_next&&creates==0&&releases==0);
 assert(PGSpawnVehicle("sultan"));assert(!PGTeleportToWaypoint());no_script=false;model_loaded=true;tick(1);
 assert(PGSpawnVehicleStatus()==2&&!pg_world_pending_model&&!pg_spawn_next&&pg_spawn_model_hash==pg_joaat("sultan")&&creates==1&&releases==2);
 // A rejected release cannot be bypassed, but new choices remain accepted.
 reset();model_loaded=false;assert(PGSpawnVehicle("doesnotexist"));tick(1);rejected_command="mp:SetModelAsNoLongerNeeded";
 assert(PGSpawnVehicle("adder"));tick(1);assert(PGSpawnVehicleStatus()==1&&creates==0&&pg_spawn_next);
 assert(PGSpawnVehicle("sultan"));rejected_command=NULL;model_loaded=true;tick(1);assert(PGSpawnVehicleStatus()==2&&creates==1&&pg_spawn_model_hash==pg_joaat("sultan"));
 reset();teleport();int previous_status=PGSpawnVehicleStatus();assert(PGQueueSpawnVehicle("sultan")==PGVehicleSpawnBusy&&PGSpawnVehicleStatus()==previous_status);tick(16000);
 reset();mode=0;assert(!PGSpawnVehicle("adder")&&!PGTeleportToWaypoint()&&PGTeleportToWaypointStatus()==PGWaypointUnavailable&&actual_calls==0);
 reset();assert(PGSpawnVehicle("adder"));assert(actual_calls==0);tick(1);assert(PGSpawnVehicleStatus()==2&&creates==1&&seats==1&&releases==1&&network_flag==0&&host_flag==0);
 reset();assert(PGSpawnVehicle("adder"));tick(31000);assert(PGSpawnVehicleStatus()==PGVehicleSpawnTimedOut&&actual_calls==0);
 reset();teleport();tick(16000);assert(PGTeleportToWaypointStatus()==PGWaypointTimedOut&&actual_calls==0);
 reset();no_script=true;assert(PGSpawnVehicle("adder"));tick(1);assert(PGSpawnVehicleStatus()==1&&actual_calls==0);tick(31000);assert(PGSpawnVehicleStatus()==PGVehicleSpawnTimedOut&&actual_calls==0&&atomic_load(&pg_world_active)==0);
 reset();no_script=true;teleport();tick(1);assert(PGTeleportToWaypointStatus()==1&&actual_calls==0);tick(16000);assert(PGTeleportToWaypointStatus()==PGWaypointTimedOut&&actual_calls==0&&atomic_load(&pg_world_active)==0);
 reset();model_loaded=false;assert(PGSpawnVehicle("adder"));tick(1);assert(requests==1);no_script=true;tick(31000);assert(PGSpawnVehicleStatus()==PGVehicleSpawnTimedOut&&releases==0&&pg_world_pending_model!=0);no_script=false;tick(1);assert(releases==1&&pg_world_pending_model==0);
 reset();mode=2;model_loaded=false;assert(PGSpawnVehicle("adder"));tick(1);assert(PGSpawnVehicleStatus()==1);assert(!PGTeleportToWaypoint()&&PGTeleportToWaypointStatus()==PGWaypointBusy);tick(31000);assert(PGSpawnVehicleStatus()==PGVehicleSpawnTimedOut&&releases==1&&creates==0);
 reset();mode=2;ped_control=false;assert(PGSpawnVehicle("adder"));tick(1);assert(PGSpawnVehicleStatus()==PGVehicleSpawnNoControl&&creates==0&&releases==1);
 reset();mode=2;vehicle_control=false;assert(PGSpawnVehicle("adder"));tick(1);assert(PGSpawnVehicleStatus()==PGVehicleSpawnNoControl&&creates==1&&seats==0&&releases==1);
 reset();mode=2;assert(PGSpawnVehicle("adder"));tick(1);assert(PGSpawnVehicleStatus()==2&&network_flag==1&&host_flag==0&&ownership_calls>=4&&releases==1);
 reset();mode=2;network_script_ready=false;assert(PGSpawnVehicle("sultan"));tick(1);assert(PGSpawnVehicleStatus()==1&&requests==0&&creates==0);network_script_ready=true;tick(1);assert(PGSpawnVehicleStatus()==2&&creates==1);
 reset();mode=2;network_script_ready=false;teleport();tick(1);assert(PGTeleportToWaypointStatus()==1&&starts==0&&creates==0);network_script_ready=true;scene_loaded=ground_found=true;tick(1);assert(PGTeleportToWaypointStatus()==2&&moves==1&&creates==0);
 reset();mode=2;script_host=false;assert(PGSpawnVehicle("sultan"));tick(1);assert(PGSpawnVehicleStatus()==2&&network_flag==1&&host_flag==0);script_host=true;
 reset();ped=0;assert(PGSpawnVehicle("adder"));tick(1);assert(PGSpawnVehicleStatus()==PGVehicleSpawnNoPlayer&&creates==0&&releases==1);
 reset();created=0;assert(PGSpawnVehicle("adder"));tick(1);assert(PGSpawnVehicleStatus()==PGVehicleSpawnCreateFailed&&creates==2&&releases==1);
 reset();missing_command="mp:RequestModel";assert(PGSpawnVehicle("adder"));tick(1);assert(PGSpawnVehicleStatus()==PGVehicleSpawnUnavailable&&actual_calls==0);
 reset();wx=999;teleport();tick(1);assert(PGTeleportToWaypointStatus()==PGWaypointNoWaypoint&&starts==0&&moves==0);
 reset();missing_command="mp:GetGroundZFor3dCoord";teleport();tick(1);assert(PGTeleportToWaypointStatus()==PGWaypointUnavailable&&starts==0&&actual_calls==0);
 reset();wx=NAN;teleport();tick(1);assert(PGTeleportToWaypointStatus()==PGWaypointInvalidGround&&starts==0);
 reset();ped=0;teleport();tick(1);assert(PGTeleportToWaypointStatus()==PGWaypointNoLocalPlayer&&starts==0);
 reset();scene_active=true;teleport();tick(1);assert(PGTeleportToWaypointStatus()==PGWaypointStreamingBusy&&stops==0&&scene_active);
 reset();teleport();tick(1);assert(PGTeleportToWaypointStatus()==1&&starts==1&&collisions==1&&moves==0);assert(!PGTeleportToWaypoint()&&PGTeleportToWaypointStatus()==1);assert(!PGSpawnVehicle("adder"));tick(5000);assert(PGTeleportToWaypointStatus()==1&&moves==0);tick(15001);assert(PGTeleportToWaypointStatus()==PGWaypointTimedOut&&stops==1&&moves==0);
 reset();scene_loaded=ground_found=true;ground_z=NAN;teleport();tick(1);assert(PGTeleportToWaypointStatus()==PGWaypointInvalidGround&&stops==1&&moves==0);
 reset();mode=2;teleport();tick(1);ped=42;tick(1);assert(PGTeleportToWaypointStatus()==PGWaypointPlayerChanged&&stops==1&&moves==0);
 reset();mode=2;vehicle=80;driver=999;teleport();tick(1);assert(PGTeleportToWaypointStatus()==PGWaypointNoControl&&starts==0&&moves==0);
 reset();mode=2;vehicle=80;vehicle_control=false;teleport();tick(1);assert(PGTeleportToWaypointStatus()==PGWaypointNoControl&&starts==0&&moves==0);
 reset();mode=2;vehicle=80;scene_loaded=ground_found=true;teleport();tick(1);assert(PGTeleportToWaypointStatus()==2&&moves==1&&velocities==1&&stops==1&&creates==0);
 reset();scene_loaded=ground_found=true;teleport();tick(1);assert(PGTeleportToWaypointStatus()==2&&moves==1&&ownership_calls==0&&stops==1);
 reset();scene_loaded=ground_found=true;ground_z=50000;teleport();tick(1);assert(PGTeleportToWaypointStatus()==PGWaypointInvalidGround&&moves==0&&stops==1);
 reset();teleport();tick(1);assert(scene_active&&starts==1);no_script=true;tick(16000);assert(PGTeleportToWaypointStatus()==PGWaypointTimedOut&&stops==0&&pg_world_pending_scene);no_script=false;tick(1);assert(stops==1&&!pg_world_pending_scene);
 reset();rejected_command="mp:RequestCollisionAtCoord";teleport();tick(1);assert(PGTeleportToWaypointStatus()==PGWaypointUnavailable&&moves==0&&stops==1);
 // Availability never calls the engine on UIKit; unknown while loading/no script.
 reset();memset(pg_model_probes,0,sizeof pg_model_probes);atomic_store(&pg_model_probe_ready,false);loading=1;
 assert(PGVehicleModelAvailability("sultan")==-1&&actual_calls==0);
 engine_tick=1;pg_process_vehicle_availability((w2c_game*)1);engine_tick=0;
 assert(PGVehicleModelAvailability("sultan")==-1&&actual_calls==0);
 loading=0;engine_tick=1;pg_process_vehicle_availability((w2c_game*)1);engine_tick=0;
 unsigned before=actual_calls;assert(PGVehicleModelAvailability("sultan")==2&&actual_calls==before);
 engine_tick=1;pg_process_vehicle_availability((w2c_game*)1);engine_tick=0;
 assert(PGVehicleModelAvailability("sultan")==1&&requests==0&&creates==0);
 cd_image=false;assert(PGVehicleModelAvailability("oppressor2")==2);
 engine_tick=1;pg_process_vehicle_availability((w2c_game*)1);engine_tick=0;
 assert(PGVehicleModelAvailability("oppressor2")==0&&requests==0&&creates==0);
 loading=1;engine_tick=1;pg_process_vehicle_availability((w2c_game*)1);engine_tick=0;
 assert(PGVehicleModelAvailability("oppressor2")==-1);loading=0;cd_image=true;
 // Even a full visible catalog is bounded to eight pure probes per control update.
 for(unsigned k=0;k<18;k++){char name[32];snprintf(name,sizeof name,"probe_%u",k);atomic_store(&pg_model_probe_ready,true);assert(PGVehicleModelAvailability(name)==2);}
 unsigned completed=0;for(unsigned k=0;k<PG_MODEL_SLOTS;k++)if(pg_model_probes[k].state>=2)completed++;
 engine_tick=1;pg_process_vehicle_availability((w2c_game*)1);engine_tick=0;
 unsigned after=0;for(unsigned k=0;k<PG_MODEL_SLOTS;k++)if(pg_model_probes[k].state>=2)after++;
 assert(after-completed==8&&requests==0&&creates==0);
 missing_command="mp:IsModelInCdImage";engine_tick=1;pg_process_vehicle_availability((w2c_game*)1);engine_tick=0;assert(PGVehicleModelAvailability("sultan")==-1);missing_command=NULL;
 reset();atomic_store(&pg_model_probe_ready,true);cd_image=false;assert(PGSpawnVehicle("oppressor2"));tick(1);assert(PGSpawnVehicleStatus()==PGVehicleSpawnModelMissing&&requests==0&&creates==0);cd_image=true;
 puts("QUEUED_WORLD_TOOLS_LOCAL_OWNERSHIP_GROUND_TIMEOUT_CLEANUP_PASS");return 0;
}
