/* Only the newly allocated task's entry and route statics are changed. GTA owns
 * cleanup, save handling and the complete Public Session leave/join sequence. */
#include <CommonCrypto/CommonDigest.h>
static _Atomic int pg_restart_status;
static unsigned pg_restart_phase,pg_restart_id,pg_restart_old_freemode;
static double pg_restart_started;
static bool pg_restart_range(uint64_t at,uint64_t size){return at && at<=env.memory.size && size<=env.memory.size-at;}
static uint32_t pg_restart_u32(uint64_t at){uint32_t n;memcpy(&n,pg_pointer(&env,at,4),4);return n;}
static uint64_t pg_restart_u64(uint64_t at){uint64_t n;memcpy(&n,pg_pointer(&env,at,8),8);return n;}
static void pg_restart_set32(uint64_t at,uint32_t n){memcpy(pg_pointer(&env,at,4),&n,4);}
static bool pg_restart_call(w2c_game* instance,const char* name,const MugoatValue* args,unsigned count,uint64_t* value){
  MugoatValue result={0};if(!mugoat_command_call(instance,name,args,count,&result))return false;if(value)*value=result.bits;return true;
}
bool PGRequestSessionRestart(void){
  if(PGWorldToolsMode()!=2)return false;
  int old=atomic_load(&pg_restart_status);
  do{if(old>=1&&old<=3)return false;}while(!atomic_compare_exchange_weak(&pg_restart_status,&old,1));return true;
}
int PGSessionRestartStatus(void){return atomic_load(&pg_restart_status);}
static void pg_restart_finish(int status,const char* message){pg_restart_phase=0;pg_restart_id=0;atomic_store(&pg_restart_status,status);pg_log(message);}
static bool pg_restart_valid_program(uint64_t program){
  if(!pg_restart_range(program,128)||pg_restart_u32(program+88)!=1392012650||pg_restart_u32(program+28)!=889405||pg_restart_u32(program+36)!=1544||pg_restart_u32(program+32)!=4)return false;
  uint64_t pages=pg_restart_u64(program+16),initial=pg_restart_u64(program+48);if(!pg_restart_range(pages,55*8)||!pg_restart_range(initial,1544*8)||pg_restart_u32(initial+1399*8)!=4)return false;
  CC_SHA256_CTX ctx;CC_SHA256_Init(&ctx);
  for(unsigned off=15844;off<21033;){unsigned count=16384-off%16384;if(count>21033-off)count=21033-off;uint64_t base=pg_restart_u64(pages+(off/16384)*8)+off%16384;if(!pg_restart_range(base,count))return false;CC_SHA256_Update(&ctx,pg_pointer(&env,base,count),count);off+=count;}
  unsigned char hash[32];CC_SHA256_Final(hash,&ctx);
  static const unsigned char expected[]={0x5c,0x6b,0xe1,0x36,0x9a,0x9f,0xf4,0x1d,0x9c,0xcf,0xa3,0xf0,0xbe,0xea,0x3e,0x0a,0x68,0xc3,0x74,0xa5,0xcc,0xb1,0x7e,0xa2,0x00,0x51,0x5c,0x01,0x21,0xfc,0xbd,0x64};
  return !memcmp(hash,expected,32);
}
static unsigned pg_restart_freemode_id(void){
  uint16_t count=0;memcpy(&count,pg_pointer(&env,15409712,2),2);if(count>1024)return 0;uint64_t list=pg_restart_u64(15409704);if(!pg_restart_range(list,count*8))return 0;
  for(unsigned i=0;i<count;i++){uint64_t t=pg_restart_u64(list+i*8);if(pg_restart_range(t,648)&&pg_restart_u32(t+32)<=1&&!memcmp(pg_pointer(&env,t+428,9),"freemode",9))return pg_restart_u32(t+24);}return 0;
}
static void pg_process_session_restart(w2c_game* instance){
  int status=atomic_load(&pg_restart_status);if(status<1||status>3)return;
  if(PGWorldToolsMode()!=2){pg_restart_finish(-1,"Session restart needs multiplayer.");return;}
  if(!pg_restart_phase){pg_restart_started=timeMS(CLOCK_MONOTONIC);pg_restart_phase=1;pg_restart_old_freemode=pg_restart_freemode_id();}
  if(timeMS(CLOCK_MONOTONIC)-pg_restart_started>(pg_restart_phase>=3?120000:30000)){pg_restart_finish(-2,"Session restart timed out; Find New Session remains available.");return;}
  MugoatValue hash[]={mg_u32(1392012650)};uint64_t result=0;
  if(pg_restart_phase==4){unsigned current=pg_restart_freemode_id();uint64_t session=pg_restart_u64(29044456);if(current&&current!=pg_restart_old_freemode&&pg_restart_range(session+99916,4)&&pg_restart_u32(session+99916)==5)pg_restart_finish(4,"GTA returned to the multiplayer session.");return;}
  if(pg_restart_phase==3){
    MugoatValue id[]={mg_u32(pg_restart_id)};if(!pg_restart_call(instance,"mp:SessionGetTask",id,1,&result)){pg_restart_finish(-3,"Session task lookup failed.");return;}
    if(!result||pg_restart_u32(result+32)==2)pg_restart_phase=4;else if(pg_restart_u32(result+32)>2)pg_restart_finish(-3,"GTA rejected the session task.");return;
  }
  uint64_t previous=pg_world_enter_script(instance);
  if(!pg_world_script_active(instance)){pg_test_leave_script(instance,previous);return;}
  if(pg_restart_phase==1){pg_restart_old_freemode=pg_restart_freemode_id();if(!pg_restart_old_freemode){pg_test_leave_script(instance,previous);return;}}
  unsigned owned=0;bool ok=true;
  if(pg_restart_phase==1){ok=pg_restart_call(instance,"mp:SessionRequestScript",hash,1,NULL);if(ok){pg_restart_phase=2;atomic_store(&pg_restart_status,2);}}
  if(ok&&pg_restart_phase==2){
    ok=pg_restart_call(instance,"mp:SessionScriptLoaded",hash,1,&result);
    if(ok&&result){
      uint64_t program=0;ok=pg_restart_call(instance,"mp:SessionGetProgram",hash,1,&program)&&pg_restart_valid_program(program);
      if(ok){MugoatValue args[]={mg_u32(1392012650),mg_u64(0),mg_u32(0),mg_u32(4096),mg_u64(pg_restart_u64(program+96))};result=0;ok=pg_restart_call(instance,"mp:SessionCreateTask",args,5,&result)&&result;owned=ok?(unsigned)result:0;}
      if(ok){MugoatValue id[]={mg_u32(owned)};ok=pg_restart_call(instance,"mp:SessionGetTask",id,1,&result)&&pg_restart_range(result,648);}
      if(ok){uint64_t task=result,stack=pg_restart_u64(task+192);ok=pg_restart_u32(task+28)==1392012650&&pg_restart_u32(task+32)==0&&pg_restart_u32(task+36)==0&&pg_restart_u32(task+104)==4096&&pg_restart_u32(task+208)==1540&&pg_restart_u32(task+44)==1545&&pg_restart_u32(task+40)==1544&&pg_restart_range(stack,4096*8)&&pg_restart_u32(stack+1399*8)==4;
        if(ok){pg_restart_set32(stack+1400*8,14);pg_restart_set32(stack+1401*8,0);pg_restart_set32(task+36,15844);pg_restart_id=owned;owned=0;pg_restart_phase=3;pg_restart_started=timeMS(CLOCK_MONOTONIC);atomic_store(&pg_restart_status,3);pg_log("Direct Public Session restart scheduled.");}
      }
    }
  }
  if(owned){MugoatValue id[]={mg_u32(owned)};pg_restart_call(instance,"mp:SessionKillTask",id,1,NULL);}
  pg_test_leave_script(instance,previous);
  if(!ok)pg_restart_finish(-4,"Session restart refused: engine resource or task did not match the verified contract.");
}
