"""Typed-table and shared-save regressions; no real game or devices run."""
import hashlib
import base64
import json
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import social_tables as social
import online_wasm
import prepare_experimental

TYPES=[(['i64'],['i32']),(['i64','i64'],['i64']),(['i64','i64','i64'],['i32']),(['f32'],['f32']),(['i64'],[])]

def run(args,**kw):
    p=subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=90,**kw)
    if p.returncode:raise AssertionError(p.stdout[-2000:]+'\n'+p.stderr[-4000:])
    return p.stdout

class Experimental(unittest.TestCase):
    def test_native_reserved_roles_keep_actual_indirect_type_checks(self):
        cached=ROOT.parent/'app/Build/EngineLAN-Experimental-20261016/AppRoot'
        h,c,plan=social.native(TYPES)
        with tempfile.TemporaryDirectory(prefix='zema-social-native-') as d:
            p=Path(d).resolve();(p/'ZemaSocial.h').write_text(h);(p/'ZemaSocial.c').write_text(c)
            registry=[]
            for i,(params,results) in enumerate(TYPES):
                enums=['WASM_RT_'+x.upper() for x in params+results]
                registry.append('if(pc=='+str(len(params))+'&&rc=='+str(len(results))+''.join('&&v['+str(n)+']=='+x for n,x in enumerate(enums))+')return signatures['+str(i)+'];')
            fixture='''#include "game-impl.h"
#include "ZemaProfile.h"
#include <setjmp.h>
#include <stdarg.h>
#include <stdlib.h>
#include <assert.h>
static char signatures[5][32]={{1},{2},{3},{4},{5}};
static jmp_buf trap;static uint8_t memory[33554432];
void wasm_rt_trap(wasm_rt_trap_t t){(void)t;longjmp(trap,1);}
void pg_note_call_indirect(const char* f,uint32_t i,uint32_t n){(void)f;(void)i;(void)n;}
uint8_t* mugoat_memory_data(void* i,uint64_t* n){(void)i;*n=sizeof memory;return memory;}
u64 w2c_game_f91000(w2c_game* i,u64 n){(void)i;(void)n;return 20000;}
void w2c_game_f91002(w2c_game* i,u64 p){(void)i;(void)p;}
wasm_rt_funcref_table_t* w2c_game_0x5F_indirect_function_table(w2c_game* i){return &i->w2c_0x5F_indirect_function_table;}
uint32_t wasm_rt_grow_funcref_table(wasm_rt_funcref_table_t* t,uint32_t n,wasm_rt_funcref_t init){uint32_t old=t->size;if(n>t->max_size-old)return UINT32_MAX;t->data=realloc(t->data,(old+n)*sizeof(*t->data));for(uint32_t i=old;i<old+n;i++)t->data[i]=init;t->size+=n;return old;}
wasm_rt_func_type_t wasm2c_game_get_func_type(uint32_t pc,uint32_t rc,...){int v[16];va_list a;va_start(a,rc);for(uint32_t i=0;i<pc+rc;i++)v[i]=va_arg(a,int);va_end(a);
'''+''.join(registry)+'''return NULL;}
int main(void){
  w2c_game* i=calloc(1,sizeof(*i));wasm_rt_funcref_table_t* t=&i->w2c_0x5F_indirect_function_table;t->size=89368;t->max_size=100000;t->data=calloc(t->size,sizeof(*t->data));
  assert(ZemaProfileConfigure(123456,(uint8_t*)"zema",4));assert(ZemaSocialInstall(i));assert(ZemaSocialPrepare(i));
  u64 role=89370;assert(CALL_INDIRECT((*t),u32(*)(void*,u64),signatures[0],role,t->data[role].module_instance,20000)==1);
  role=89371;assert(CALL_INDIRECT((*t),u64(*)(void*,u64,u64),signatures[1],role,t->data[role].module_instance,20000,10000)==0);u64 id;memcpy(&id,memory+10008,8);assert(id==123456);
  role=89369;assert(CALL_INDIRECT((*t),f32(*)(void*,f32),signatures[3],role,t->data[role].module_instance,1.25f)==0.0f);
  /* Unsupported signed-in ABI stays null and traps; ordinary indices retain checks. */
  if(!setjmp(trap)){role=89370;CALL_INDIRECT((*t),f32(*)(void*,f32),signatures[3],role,t->data[role].module_instance,1.0f);abort();}
  if(!setjmp(trap)){role=0;CALL_INDIRECT((*t),u32(*)(void*,u64),signatures[0],role,t->data[role].module_instance,0);abort();}
  if(!setjmp(trap)){role=UINT64_MAX;CALL_INDIRECT((*t),u32(*)(void*,u64),signatures[0],role,t->data[0].module_instance,0);abort();}
  puts("NATIVE_TYPED_SOCIAL_AND_ORDINARY_TRAPS_PASS");return 0;
}
'''
            (p/'fixture.c').write_text(fixture)
            library=Path(os.environ.get('ZEMA_TEST_LAN_LIBRARY',str(ROOT.parent/'app/Build/EngineLAN/RustHost/debug/libzema_engine_lan.a')))
            run(['/usr/bin/clang','-std=c11','-w','-I',p,'-I',ROOT,'-I',cached/'Generated','-I',cached/'Tools/wabt-1.0.42/share/wabt/wasm2c','-I',cached/'Tools/simde',p/'fixture.c',p/'ZemaSocial.c',library,'-o',p/'test'])
            self.assertIn('NATIVE_TYPED_SOCIAL_AND_ORDINARY_TRAPS_PASS',run([p/'test']))

    def test_explicit_browser_entry_waits_for_shared_save_and_lan(self):
        self.assertIn("EXPLICIT_SHARED_PROFILE_AND_LAN_GAME_LAUNCH_PASS",run(["node",ROOT/"tests/entry_fixture.cjs",ROOT/"entry.js"]))

    def test_failed_resume_is_identified_without_changing_engine_context(self):
        self.assertIn('NETWORK_RECOVERY_OPERATION_AND_ENGINE_CONTEXT_GUARD_PASS',run(['node',ROOT/'tests/network_recovery.cjs',ROOT]))

    def test_shared_profile_multiple_workers_and_restart(self):
        with tempfile.TemporaryDirectory(prefix='zema-shared-profile-') as d:
            self.assertIn('SHARED_PROFILE_4_WRITERS_DISK_RESUME_EXTERNAL_GUARD_PASS',run(['node',ROOT/'tests/profile_rpc.cjs',str(Path(d).resolve())]))

    def test_browser_social_dispatch_preserves_wasm_checks(self):
        b=online_wasm.b;types=[(['i64'],['i32']),(['i64'],['i64']),(['i64'],[]),(['i64','i64'],['i32']),(['i64','i64'],['i64']),(['i64','i64','i64'],['i64']),(['f32'],['f32']),(['f32','i64'],['f32'])]
        inverse={'i32':0x7f,'i64':0x7e,'f32':0x7d}
        typed=[b'\x60'+b.leb(len(p))+bytes(inverse[x] for x in p)+b.leb(len(r))+bytes(inverse[x] for x in r) for p,r in types]
        names=['Fixture::local_ip','emscripten_builtin_malloc','emscripten_builtin_free','Fixture::sign','Fixture::info','Fixture::float']
        bodies=[b'\0\x41\0\x0b',b'\0\x42'+b.sleb(20000)+b'\x0b',b'\0\x0b',b'\0\x20\0\x20\x01\x11\0\0\x0b',b'\0\x20\0\x20\x01\x20\x02\x11\x04\0\x0b',b'\0\x20\0\x20\x01\x11\x06\0\x0b']
        exports=[b.string('__indirect_function_table')+b'\x01\0']+[b.string('test:'+n)+b'\0'+b.leb(i) for i,n in [(3,'sign'),(4,'info'),(5,'float')]]
        names_blob=b.leb(6)+b''.join(b.leb(i)+b.string(n) for i,n in enumerate(names))
        data=(b'\0asm\x01\0\0\0'+b.section(1,b.leb(len(typed))+b''.join(typed))+b.section(2,b'\x01'+b.string('env')+b.string('memory')+b'\x02\x03'+b.leb(256)+b.leb(256))+b.section(3,b'\x06\0\x01\x02\x03\x05\x07')+b.section(4,b'\x01\x70\x05\x08\x08')+b.section(7,b.leb(len(exports))+b''.join(exports))+b.section(10,b'\x06'+b''.join(b.leb(len(x))+x for x in bodies))+b.section(0,b.string('name')+b.section(1,names_blob)))
        contract={'engine_sha256':hashlib.sha256(data).hexdigest(),'upstream_revision':'SYNTHETIC','hooks':[{'field':'local_ip_address','group':'vnet','name':names[0],'index':0,'params':['i64'],'results':['i32']}]}
        changed,metadata=online_wasm.transform(data,contract)
        with tempfile.TemporaryDirectory(prefix='zema-social-wasm-') as d:
            p=Path(d).resolve();f=p/'fixture.json';f.write_text(json.dumps({'wasm':base64.b64encode(changed).decode(),'metadata':metadata}))
            self.assertIn('BROWSER_TYPED_SOCIAL_INFO_FLOAT_AND_ORDINARY_TRAPS_PASS',run(['node',ROOT/'tests/social_wasm.cjs',f,p/'profile.zemapf']))

    def test_decoder_does_not_patch_opcodes_inside_immediates(self):
        # i64.const with an immediate containing 0x11 is not call_indirect.
        body=b'\0\x42\x91\0\x1a\x0b';self.assertEqual(online_wasm.rewrite(body,{0:99}),(body,0))
        body=b'\0\x20\0\x11\0\0\x0b';patched,count=online_wasm.rewrite(body,{0:99});self.assertEqual(count,1);self.assertEqual(patched,b'\0\x20\0\x10\x63\x11\0\0\x0b')
        with self.assertRaises(ValueError):online_wasm.rewrite(b'\0\xfb\x00\x0b',{})

    def test_compiled_ui_is_explicit_and_changed_cache_refused(self):
        spec={'targets':{'PlayGTA5Native':{'sources':[],'info':{'properties':{}}}}}
        prepare_experimental.add_ui(spec)
        target=spec['targets']['PlayGTA5Native'];self.assertIn({'path':'GeneratedUIAssets','buildPhase':'resources'},target['sources'])
        self.assertEqual(target['info']['properties']['CFBundleIcons']['CFBundlePrimaryIcon']['CFBundleIconName'],'AppIcon')
        with tempfile.TemporaryDirectory(prefix='zema-bad-ui-') as folder:
            with self.assertRaises(ValueError):prepare_experimental.verify_ui(Path(folder))

    def test_stage_refuses_changed_source_anchors(self):
        with self.assertRaises(ValueError):prepare_experimental.engine_patch('changed')
        with self.assertRaises(ValueError):prepare_experimental.controller_patch('changed')

    def test_broadcast_overlay_is_exact_length_and_transactional(self):
        source=r'''#include <assert.h>
#include <string.h>
#include <stdint.h>
extern int ZemaBroadcastPatch(uint8_t*,size_t);
int main(){char b[]="<HostBroadcastData><Item><SizeOfData value=\"7500\"/><NumInstances value=\"2\"/></Item><Item><SizeOfData value=\"4000\"/><NumInstances value=\"4\"/></Item></HostBroadcastData><PlayerBroadcastData>\n<Item><SizeOfData value=\"3600\"/>\n\t\t<NumInstances value=\"1\"/></Item>\n<Item><SizeOfData value=\"2500\"/>\n\t\t<NumInstances value=\"2\"/></Item>\n<Item><SizeOfData value=\"150\"/>\n\t\t<NumInstances value=\"4\"/></Item>\n<Item><SizeOfData value=\"80\"/>\n\t\t<NumInstances value=\"4\"/></Item>\n<Item><SizeOfData value=\"40\"/>\n\t\t<NumInstances value=\"8\"/></Item>\n</PlayerBroadcastData>";size_t n=strlen(b);assert(ZemaBroadcastPatch((uint8_t*)b,n));assert(strlen(b)==n);assert(strstr(b,"value=\"16\""));assert(ZemaBroadcastPatch((uint8_t*)b,n));char bad[]="<PlayerBroadcastData>bad</PlayerBroadcastData>",old[sizeof bad];memcpy(old,bad,sizeof bad);assert(!ZemaBroadcastPatch((uint8_t*)bad,strlen(bad)));assert(!memcmp(old,bad,sizeof bad));return 0;}'''
        with tempfile.TemporaryDirectory(prefix='zema-broadcast-') as d:
            p=Path(d);(p/'test.c').write_text(source);run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror',p/'test.c',ROOT/'BroadcastOverlay.c','-o',p/'test']);run([p/'test'])

if __name__=='__main__':unittest.main()
