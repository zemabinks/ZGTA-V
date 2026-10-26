"""Approved built-in icon equivalence, real native getter mutation and bounds."""
import importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];APP=ROOT.parent/'app'
sys.path.insert(0,str(APP/'Scripts'))
import generate_blip_fallbacks,prepare_blip_sprites

class BlipFallbacks(unittest.TestCase):
    def test_shared_outputs_current_and_sensible_contact_routes(self):
        for path,text in generate_blip_fallbacks.outputs().items():self.assertEqual(path.read_text(),text)
        rows={a:(b,n) for a,b,n,_ in json.loads(generate_blip_fallbacks.CATALOG.read_text())}
        self.assertEqual(rows[445],(77,'radar_lester_family'))
        self.assertEqual(rows[739],(280,'radar_friend'))
        self.assertEqual(rows[798],(59,'radar_heist'))
        self.assertEqual(rows[892],(303,'radar_bounty_hit'))
        self.assertEqual(rows[788],(374,'radar_business'))
        self.assertEqual(rows[829],(377,'radar_parachute'))
        self.assertNotIn(1,rows)

    def test_browser_actual_table_layout_no_writes_priority_and_corruption(self):
        r=subprocess.run(['node',str(ROOT/'tests/blip_fallbacks_fixture.cjs'),str(ROOT/'blip_sprites.js')],capture_output=True,text=True,timeout=30)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertIn('BOUNDS_PASS',r.stdout)

    def test_native_real_getter_keeps_original_reference_when_parameter_reassigned(self):
        part=APP/'Build/Phone-CleanHome-20261020/AppRoot/Generated/game_19.c'
        if not part.exists():self.skipTest('Reviewed native source absent')
        s=part.read_text();start=s.index(prepare_blip_sprites.SIGNATURE);end=s.index('\n}\n',start)+3
        original=s[start:end];patched=prepare_blip_sprites.patch(original)
        self.assertIn('var_p0 = var_j0;',original)
        self.assertIn('const u64 pg_blip_reference = var_p0;',patched)
        declarations=r'''
#include <stdint.h>
typedef uint32_t u32;typedef uint64_t u64;typedef int32_t s32;
typedef struct { unsigned char *data;u64 size; } test_memory;
typedef struct {u64 w2c_g0;test_memory *w2c_env_memory;} w2c_game;
'''
        harness=r'''
#include "game.h"
#include "NativeBlipDiagnostics.h"
#include <assert.h>
#define FUNC_PROLOGUE
#define FUNC_EPILOGUE
#define checked_add_u64(a,b) ((a)+(b))
#define i32_load_shared(a,b,m,p) pg_blip_read32((m)->data+(p))
#define i64_load_shared(a,b,m,p) pg_blip_read64((m)->data+(p))
#define i64_load16_u_shared(a,b,m,p) ((u64)((m)->data[p]|((u32)(m)->data[(p)+1]<<8)))
#define i32_store_shared(a,b,m,p,v) put32((m)->data+(p),(v))
#define i64_store_shared(a,b,m,p,v) put64((m)->data+(p),(v))
static void put32(unsigned char *p,u32 v){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(v>>(i*8));}
static void put64(unsigned char *p,u64 v){for(unsigned i=0;i<8;i++)p[i]=(unsigned char)(v>>(i*8));}
static u64 w2c_game_f2721(w2c_game *instance,u64 p){(void)instance;(void)p;return 0;}
static u64 captured;
u64 pg_blip_name_diagnostic(w2c_game *instance,u64 reference,u64 value){captured=reference;return pg_blip_fallback(instance->w2c_env_memory->data,instance->w2c_env_memory->size,reference,value,0);}
'''
        main=r'''
static unsigned char bytes[19660800];
int main(void){test_memory m={bytes,sizeof bytes};w2c_game engine={32768,&m};
 put64(bytes+PG_BLIP_TABLE_ADDRESS,4096);bytes[PG_BLIP_TABLE_COUNT_ADDRESS]=170;bytes[PG_BLIP_TABLE_COUNT_ADDRESS+1]=1;
 for(unsigned id=0;id<426;id++)put32(bytes+4096+id*16,id);
 put64(bytes+4096+280*16+8,65536);memcpy(bytes+65536,"radar_friend",13);
 put32(bytes+64,739);assert(w2c_game_f35144(&engine,64)==65536);assert(captured==64);assert(pg_blip_read32(bytes+64)==739);assert(engine.w2c_g0==32768);
 put32(bytes+64,950);assert(w2c_game_f35144(&engine,64)==0);assert(captured==64);
 put32(bytes+64,280);assert(w2c_game_f35144(&engine,64)==65536);
 int32_t target=0;assert(pg_blip_fallback(0,0,UINT64_MAX,999,&target)==999);assert(target==-1);
 assert(!pg_blip_fallback(bytes,32,64,0,&target));assert(!pg_blip_fallback(bytes,sizeof bytes,UINT64_MAX,0,&target));
 put32(bytes+64,739);put64(bytes+PG_BLIP_TABLE_ADDRESS,UINT64_MAX);assert(!pg_blip_fallback(bytes,sizeof bytes,64,0,&target));
 put64(bytes+PG_BLIP_TABLE_ADDRESS,4096);put64(bytes+4096+280*16+8,sizeof bytes-1);assert(!pg_blip_fallback(bytes,sizeof bytes,64,0,&target));
 put64(bytes+4096+280*16+8,65536);bytes[65536]='X';assert(!pg_blip_fallback(bytes,sizeof bytes,64,0,&target));
 return 0;}
'''
        with tempfile.TemporaryDirectory(prefix='zgta-real-blip-getter-') as d:
            p=Path(d);(p/'game.h').write_text('#pragma once\n'+declarations);(p/'game-blip-diagnostics-impl.h').write_text(prepare_blip_sprites.HEADER)
            (p/'test.c').write_text(harness+'\n'+patched+'\n'+main)
            r=subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(p),'-I',str(APP/'Source'),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            subprocess.run([str(p/'test')],check=True,capture_output=True)

if __name__=='__main__':unittest.main()
