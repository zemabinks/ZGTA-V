/* Standalone host-contract test; the original function bytes are a local input,
 * never embedded in source or uploaded as an artifact. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>
#include <time.h>
typedef struct {} w2c_game;
typedef struct {uint32_t type,reserved;uint64_t bits;} MugoatValue;
static struct {struct{uint8_t* data;uint64_t size;}memory;} env;
static double clock_ms;static int mode=2,created,killed;static bool bad_stack;
static int PGWorldToolsMode(void){return mode;}
static double timeMS(int clock){(void)clock;return clock_ms;}
static void* pg_pointer(void* ignored,uint64_t at,uint64_t size){(void)ignored;assert(at<=env.memory.size&&size<=env.memory.size-at);return env.memory.data+at;}
static void pg_log(const char* line){(void)line;}
static MugoatValue mg_u32(uint32_t n){return(MugoatValue){.type=1,.bits=n};}
static MugoatValue mg_u64(uint64_t n){return(MugoatValue){.type=2,.bits=n};}
static uint64_t active=999;
static uint64_t pg_world_enter_script(w2c_game* i){(void)i;uint64_t old=active;active=2200000;return old;}
static bool pg_world_script_active(w2c_game* i){(void)i;return active==2200000;}
static void pg_test_leave_script(w2c_game* i,uint64_t previous){(void)i;active=previous;}
static void put32(uint64_t at,uint32_t n){memcpy(pg_pointer(NULL,at,4),&n,4);}
static void put64(uint64_t at,uint64_t n){memcpy(pg_pointer(NULL,at,8),&n,8);}
static bool mugoat_command_call(void* i,const char* name,const MugoatValue* args,uint32_t count,MugoatValue* out){
 (void)i;(void)count;out->bits=0;
 if(!strcmp(name,"mp:SessionGetTask")){out->bits=2100000;return true;}
 if(!strcmp(name,"mp:SessionKillTask")){assert(args[0].bits==60);killed++;put32(2100032,2);return true;}
 assert(active==2200000);
 if(!strcmp(name,"mp:SessionRequestScript"))return true;
 if(!strcmp(name,"mp:SessionScriptLoaded")){out->bits=1;return true;}
 if(!strcmp(name,"mp:SessionGetProgram")){out->bits=1000000;return true;}
 if(!strcmp(name,"mp:SessionCreateTask")){
  assert(count==5&&args[0].bits==1392012650&&args[1].bits==0&&args[2].bits==0&&args[3].bits==4096);created++;
  memset(pg_pointer(NULL,2100000,648),0,648);put32(2100024,60);put32(2100028,1392012650);put32(2100104,4096);put32(2100208,bad_stack?1544:1540);put32(2100044,1545);put32(2100040,1544);put64(2100192,2000000);put32(2000000+1399*8,4);out->bits=60;return true;
 }
 assert(!"Unexpected engine command");return false;
}
#include "../../app/Source/NativeSessionRestart.inc"
int main(int argc,char** argv){
 assert(argc==2);env.memory.size=32*1024*1024;env.memory.data=calloc(1,env.memory.size);assert(env.memory.data);
 put32(1000088,1392012650);put32(1000028,889405);put32(1000036,1544);put32(1000032,4);put64(1000048,1100000);put64(1000016,1200000);put64(1000096,1000600);put32(1100000+1399*8,4);put64(1200000,1300000);put64(1200008,1316384);
 FILE* file=fopen(argv[1],"rb");assert(file);assert(!fseek(file,128+15844,SEEK_SET));assert(fread(pg_pointer(NULL,1300000+15844,21033-15844),1,21033-15844,file)==21033-15844);fclose(file);
 put64(15409704,2300000);uint16_t one=1;memcpy(pg_pointer(NULL,15409712,2),&one,2);put64(2300000,2200000);put32(2200024,5);memcpy(pg_pointer(NULL,2200428,9),"freemode",9);put64(29044456,2500000);put32(2500000+99916,5);
 w2c_game instance;assert(PGRequestSessionRestart());assert(!PGRequestSessionRestart());pg_process_session_restart(&instance);assert(PGSessionRestartStatus()==3);assert(created==1&&killed==0&&active==999);assert(pg_restart_u32(2100036)==15844);assert(pg_restart_u32(2000000+1400*8)==14);assert(pg_restart_u32(2000000+1401*8)==0);
 put32(2100032,2);pg_process_session_restart(&instance);assert(PGSessionRestartStatus()==3);put32(2200024,77);pg_process_session_restart(&instance);assert(PGSessionRestartStatus()==4);
 assert(PGRequestSessionRestart());bad_stack=true;pg_process_session_restart(&instance);assert(PGSessionRestartStatus()==-4&&killed==1&&active==999);
 bad_stack=false;env.memory.data[1300000+15844]^=1;assert(PGRequestSessionRestart());pg_process_session_restart(&instance);assert(PGSessionRestartStatus()==-4&&created==2);
 mode=1;assert(!PGRequestSessionRestart());free(env.memory.data);puts("PASS native direct-session contract with real local function SHA, argument/static split, task isolation, TLS restoration, completion, mismatch refusal and owned-task cleanup.");
}
