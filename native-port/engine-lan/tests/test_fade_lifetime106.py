"""Run actual original DrawInternal/DrawSkinnedPortion C with controlled materials.

Only geometry/pass and unavailable host services are mocked. Original branch,
loop and inline cleanup bodies are authenticated; no game/asset/network starts.
"""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import render_hooks as h

SOURCE=ROOT.parents[2]/'gta-intel-multiplayer-build-20261016/native-port/app/Generated'
PRE=r'''#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
typedef uint32_t u32;typedef uint64_t u64;typedef int32_t s32;typedef int64_t s64;
typedef struct{unsigned char*data;}Memory;
typedef struct{void*module_instance;}Entry;typedef struct{Entry data[16];}Table;
typedef struct{Memory*w2c_env_memory;u64 w2c_mugoat0x3Atls0x2Dbase,w2c_g27,w2c_g34;Table w2c_0x5F_indirect_function_table;}w2c_game;
#define FUNC_PROLOGUE
#define FUNC_EPILOGUE
#define UNREACHABLE abort()
#define checked_add_u64(a,b) ((a)+(b))
#define w2c_game_t1 1
#define w2c_game_t3 3
#define w2c_game_t21 21
#define w2c_game_t24 24
static u32 renderer,events[64],eventCount,draws[64],drawCount,passCount,beginCount,firstAvailable;
static unsigned char bytes[26000000];
static u32 i32_load_shared(void*a,u64 b,Memory*m,u64 p){u32 v;memcpy(&v,m->data+p,4);return v;}
static u32 i32_load8_u_shared(void*a,u64 b,Memory*m,u64 p){return m->data[p];}
static u32 i32_load16_u_shared(void*a,u64 b,Memory*m,u64 p){uint16_t v;memcpy(&v,m->data+p,2);return v;}
static u64 i64_load16_u_shared(void*a,u64 b,Memory*m,u64 p){return i32_load16_u_shared(a,b,m,p);}
static u64 i64_load_shared(void*a,u64 b,Memory*m,u64 p){u64 v;memcpy(&v,m->data+p,8);return v;}
static void i32_store_shared(void*a,u64 b,Memory*m,u64 p,u32 v){memcpy(m->data+p,&v,4);}
static void i32_store16_shared(void*a,u64 b,Memory*m,u64 p,u32 v){uint16_t x=v;memcpy(m->data+p,&x,2);}
static void i64_store_shared(void*a,u64 b,Memory*m,u64 p,u64 v){memcpy(m->data+p,&v,8);}
static u64 stack=4096;
u64 w2c_game_emscripten_stack_get_current(w2c_game*i){return stack;}
u64 w2c_game_0x5Femscripten_stack_alloc(w2c_game*i,u64 n){return stack-=n;}
void w2c_game_0x5Femscripten_stack_restore(w2c_game*i,u64 p){stack=p;}
void w2c_game_f550(w2c_game*i,u32 op,u64 p,u32 n){if(op!=65||n!=1)abort();renderer=i32_load_shared(0,0,i->w2c_env_memory,p);events[eventCount++]=renderer;}
void w2c_game_f244(w2c_game*i,u64 p,u32 a,u32 b){}
static void pg98_original_44583(w2c_game*i){}
static void pg98_original_9952(w2c_game*i,u64 p){}
static void pg98_original_64694(w2c_game*i,u32 a,u32 b){}
static void pg98_original_43886(w2c_game*i){}
static void pg98_original_9295(w2c_game*i){}
static u32 pg98_original_9291(w2c_game*i,u64 p,u32 a,u32 b,u32 c){
 ++beginCount;u32 result=(pg98_load32(i,6634168)==11||firstAvailable)?passCount:0;
 if(result){i64_store_shared(0,0,i->w2c_env_memory,12432408,999);pg98_store32(i,12432416,result);}
 return result;
}
static void w2c_game_f9543(w2c_game*i,u64 e,u32 pass,u64 s){}
static void w2c_game_f9549(w2c_game*i){}
static u32 mock_indirect(int type,void*i,...){if(type==1||type==3)draws[drawCount++]=renderer;return 1;}
#define CALL_INDIRECT(table,t,ft,x,...) mock_indirect(ft,__VA_ARGS__)
'''
POST=r'''
static void put64(u64 at,u64 v){memcpy(bytes+at,&v,8);}static void put32(u64 at,u32 v){memcpy(bytes+at,&v,4);}static void put16(u64 at,u32 v){uint16_t n=v;memcpy(bytes+at,&n,2);}
static void setup(w2c_game*i){memset(bytes,0,sizeof(bytes));renderer=eventCount=drawCount=beginCount=firstAvailable=0;passCount=2;pg98_stippling=0;stack=4096;
 put32(6634168,20);put32(21490232,11);put32(7248300,20);put32(7248304,21);put32(7248320,22);put32(23984584,0xf00f);
 /* Shader1000, model2000 and geometry4000. Actual original DrawInternal. */
 put64(1008,1500);put16(2016,1);put64(2008,3000);put64(3000,4000);put64(4000,5000);put64(5024,1);
 /* Actual two-material skinned model6000, drawable9000. No TLS overrides. */
 bytes[6044]=1;put16(6046,2);put16(6016,2);put64(6032,7000);put16(7000,0);put16(7002,1);
 put64(6008,8000);put64(8000,4000);put64(8008,4100);put64(4100,5100);put64(5056,1);put64(5156,1);
 put16(9024,2);put64(9016,10000);put64(10000,11000);put64(10008,12000);
 put32(11032,0x101);put32(12032,0x101);put64(11008,13000);put64(12008,14000);put32(13712,1);put32(14712,2);
}
static int mode=0;
static int check(int condition,const char*message){if(condition)return 0;fprintf(stderr,"%s\n",message);return 1;}
int main(int argc,char**argv){Memory memory={bytes};w2c_game i={.w2c_env_memory=&memory,.w2c_mugoat0x3Atls0x2Dbase=15000,.w2c_g27=16000,.w2c_g34=16008};
 mode=argc>1?atoi(argv[1]):0;setup(&i);
 if(mode==0){
  w2c_game_f9299(&i,1000,0,2000,0);
  if(check(drawCount==2&&draws[0]==25&&draws[1]==25,"mask must cover both passes"))return 2;
  if(check(renderer==0&&!pg98_stippling,"inline DrawInternal cleanup left partial mask"))return 3;
  firstAvailable=1;w2c_game_f9299(&i,1000,0,2000,0);
  if(check(drawCount==4&&draws[2]==0&&draws[3]==0,"ordinary DrawInternal inherited mask"))return 4;
 }else if(mode==1){
  /* Force a prior partial state with no EndDraw call: all Begin early exits
     must establish their own mask; no nested draw lifetime is assumed. */
  pg98_stippling=1;renderer=25;firstAvailable=1;
  w2c_game_f9291(&i,1000,0,0,0);
  if(check(renderer==0&&!pg98_stippling,"available BeginDraw inherited mask"))return 5;
  pg98_stippling=1;renderer=22;firstAvailable=0;put32(23984584,0);w2c_game_f9291(&i,1000,0,0,0);
  if(check(renderer==0&&!pg98_stippling,"empty BeginDraw inherited mask"))return 6;
  pg98_stippling=1;renderer=22;put32(23984584,65535);w2c_game_f9291(&i,1000,0,0,0);
  if(check(renderer==0&&!pg98_stippling,"full fallback inherited mask"))return 7;
 }else if(mode==2){
  w2c_game_f9302(&i,6000,0,0,2,9000,0,0x101,0);
  if(check(drawCount==4,"skinned two-material fixture missed draws"))return 8;
  if(check(draws[0]==25&&draws[1]==25&&draws[2]==25&&draws[3]==25,"skinned coverage changed before material completed"))return 9;
  if(check(renderer==0&&!pg98_stippling,"inline skinned cleanup left partial mask"))return 10;
  firstAvailable=1;w2c_game_f9302(&i,6000,0,0,2,9000,0,0x101,0);
  if(check(drawCount==8&&draws[4]==0&&draws[5]==0&&draws[6]==0&&draws[7]==0,"solid skinned material inherited mask"))return 11;
 }else if(mode==3){
  firstAvailable=1;w2c_game_f9299(&i,1000,0,2000,0);w2c_game_f9302(&i,6000,0,0,2,9000,0,0x101,0);
  if(check(eventCount==0&&renderer==0,"ordinary rendering emitted extra packets"))return 12;
 }
 if(check(stack==4096,"private emitter stack changed"))return 13;
 return 0;
}
'''

class FadeLifetime106(unittest.TestCase):
 def test_original_draw_paths_and_retained105_failure(self):
  text=(SOURCE/'game_63.c').read_text()
  for row in h.LIFETIME_PINS:
   if row['index'] in (9299,9302):
    self.assertEqual(hashlib.sha256(h.native_function(text,row['index'])[0].encode()).hexdigest(),row['native_sha256'])
  for old in (True,False):
   value=text if old else h._inline_native(text,'game_63.c')
   header=h.BUILD104_HEADER if old else h.NATIVE_HEADER
   bodies=h.BUILD104_BODIES if old else h.NATIVE_BODIES
   # Header must precede controlled original BeginDraw, which uses its helpers.
   split=PRE.index('static u32 pg98_original_9291')
   code=PRE[:split]+header+PRE[split:]+h.NATIVE_STATE+'\n'.join(bodies.values())+'\n'+ '\n'.join(h.native_function(value,n)[0] for n in (9299,9302))+POST
   with tempfile.TemporaryDirectory(prefix='zgta-lifetime106-') as folder:
    source=Path(folder)/'draw.c';exe=source.with_suffix('');source.write_text(code)
    r=subprocess.run(['clang','-std=c11','-O1','-fsanitize=address,undefined',str(source),'-o',str(exe)],text=True,capture_output=True)
    self.assertEqual(r.returncode,0,r.stderr)
    for mode in range(4):
     r=subprocess.run([str(exe),str(mode)],text=True,capture_output=True)
     self.assertEqual(r.returncode==0,not old or mode==3, f'old={old}, mode={mode}: {r.stderr}')
     if old and mode!=3:self.assertIn('left partial mask' if mode in (0,2) else 'inherited mask',r.stderr)

if __name__=='__main__':unittest.main()
