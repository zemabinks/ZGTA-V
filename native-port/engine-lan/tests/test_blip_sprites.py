"""Exact minimap hook and bounded native/browser observation fixtures."""
import importlib.util
import json
from pathlib import Path
from public_test_inputs import game_file
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1];APP=ROOT.parent/'app';sys.path.insert(0,str(ROOT))
import blip_sprites as fix
ENGINE=game_file('b/8b0b5899ed/game.wasm')

def native():
    spec=importlib.util.spec_from_file_location('prepare_blip_sprites',APP/'Scripts/prepare_blip_sprites.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class BlipSprites(unittest.TestCase):
    def test_original_and_lan_name_abi_body_pins(self):
        self.assertEqual(fix.inspect(ENGINE.read_bytes()),fix.HOOK)
        with self.assertRaisesRegex(ValueError,'Unreviewed'):fix.inspect(b'not reviewed')
        with self.assertRaisesRegex(ValueError,'ABI changed'):fix.pin([],[],{},[],0)
        with self.assertRaisesRegex(ValueError,'body changed'):
            indices=[0]*(fix.HOOK['index']+1)
            fix.pin([(['i64'],['i64'])],indices,{fix.NAME:[fix.HOOK['index']]},[b'changed']*(fix.HOOK['index']+1),0)

    def test_browser_typed_original_first_and_bounded_diagnostics(self):
        with tempfile.TemporaryDirectory(prefix='zgta-blip-js-') as directory:
            spec=Path(directory)/'aux.json';spec.write_text(json.dumps(list(fix.b.auxiliary([fix.HOOK]))))
            result=subprocess.run(['node',str(ROOT/'tests/blip_sprites_fixture.cjs'),str(ROOT),str(spec)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('BLIP_TYPED_ORIGINAL_FIRST_BOUNDED_OBSERVATION_PASS',result.stdout)

    def test_feature_transform_preserves_indices_and_all_unrelated_bodies(self):
        import browser_features
        lan=APP/'Build/EngineLAN-OnlineBrowser-20261016/game.engine-lan.wasm'
        for source in [ENGINE,lan]:
            with self.subTest(engine=source.name):
                before=source.read_bytes();after,meta=browser_features.transform(before)
                oldtypes,oldindices,_=fix.b.gate.module_abi(before)
                newtypes,newindices,_=fix.b.gate.module_abi(after)
                self.assertEqual(newtypes,oldtypes);self.assertEqual(newindices[:len(oldindices)],oldindices)
                self.assertEqual(newindices[len(oldindices):],[oldindices[i] for i in [77480,21855,7226,35212,35144]])
                old=dict(fix.b.gate.sections(before));new=dict(fix.b.gate.sections(after))
                r=fix.b.gate.Reader(old[3]);imported=len(oldindices)-r.count()
                def bodies(raw):
                    r=fix.b.gate.Reader(raw);return [r.take(r.uint()) for _ in range(r.count())]
                a,b=bodies(old[10]),bodies(new[10])
                self.assertEqual(b[-5:],[a[i-imported] for i in [77480,21855,7226,35212,35144]])
                self.assertEqual([i+imported for i,(x,y) in enumerate(zip(a,b)) if x!=y],[1652,7226,10454,21855,35144,35212,77480])
                self.assertEqual(meta['blip_sprites']['slot'],meta['hook']['slot']+6)
                self.assertEqual(meta['gamer_tag']['slot'],meta['hook']['slot']+5)
                for kind in old.keys()-{3,4,7,8,10}:self.assertEqual(old[kind],new[kind])
                code="const fs=require('node:fs'),a=require('node:assert/strict');const bytes=fs.readFileSync(0);a(WebAssembly.validate(bytes));new WebAssembly.Module(bytes);console.log('BLIP_FEATURE_COMPILE_PASS');"
                result=subprocess.run(['node','--wasm-staging','-e',code],input=after,capture_output=True,timeout=45)
                self.assertEqual(result.returncode,0,result.stderr.decode());self.assertIn(b'BLIP_FEATURE_COMPILE_PASS',result.stdout)

    def test_native_exact_body_idempotence_and_header_composition(self):
        source=APP/'Build/Phone-CleanHome-20261020/AppRoot/Generated/game_19.c'
        if not source.exists():self.skipTest('Reviewed local generated source unavailable')
        patch=native();text=source.read_text();start=text.index(patch.SIGNATURE);end=text.index('\n}\n',start)+3;body=text[start:end]
        result=patch.patch(body);self.assertIn(patch.PATCHED_RETURN,result);self.assertEqual(patch.patch(result),result)
        with self.assertRaisesRegex(ValueError,'changed'):patch.patch(body.replace('16ull','32ull',1))
        with self.assertRaisesRegex(ValueError,'missing'):patch.patch('unreviewed generated function')
        with tempfile.TemporaryDirectory(prefix='zgta-blip-header-') as directory:
            p=Path(directory);(p/'game.h').write_text('#pragma once\n#include <stdint.h>\ntypedef uint64_t u64;typedef struct {int value;} w2c_game;\n')
            (p/'game-impl.h').write_text('#include "game.h"\nstatic inline int sample(void){return 7;}\n')
            (p/'game-blip-diagnostics-impl.h').write_text(patch.HEADER)
            (p/'test.c').write_text('#include "game-blip-diagnostics-impl.h"\n#include "game-impl.h"\nint main(void){return sample()!=7;}\n')
            subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(p),str(p/'test.c'),'-o',str(p/'test')],check=True,capture_output=True)
            subprocess.run([str(p/'test')],check=True)

    def test_native_bounds_original_priority_dedup_and_limit(self):
        source=r'''
#include "NativeBlipDiagnostics.h"
#include <assert.h>
static unsigned char memory[19521000];static unsigned reports;
static void report(void *ctx,int32_t sprite,uint16_t count){(void)ctx;(void)sprite;assert(count==445);reports++;}
static void set(uint64_t at,uint32_t value){for(unsigned i=0;i<4;i++)memory[at+i]=(unsigned char)(value>>(8*i));}
int main(void){PGBlipDiagnosticCache cache={0};set(PG_BLIP_TABLE_COUNT_ADDRESS,445);set(64,739);
 assert(pg_blip_diagnostic(&cache,memory,sizeof memory,64,777,report,0)==777);assert(!reports);
 assert(!pg_blip_diagnostic(&cache,memory,sizeof memory,64,0,report,0));assert(reports==1);
 assert(!pg_blip_diagnostic(&cache,memory,sizeof memory,64,0,report,0));assert(reports==1);
 assert(!pg_blip_diagnostic(&cache,memory,sizeof memory,0,0,report,0));
 assert(!pg_blip_diagnostic(&cache,memory,sizeof memory,UINT64_MAX,0,report,0));
 assert(!pg_blip_diagnostic(&cache,memory,sizeof memory,sizeof memory-3,0,report,0));
 assert(!pg_blip_diagnostic(&cache,memory,32,64,0,report,0));assert(reports==1);
 set(PG_BLIP_TABLE_COUNT_ADDRESS,0);set(64,740);assert(!pg_blip_diagnostic(&cache,memory,sizeof memory,64,0,report,0));assert(reports==1);
 set(PG_BLIP_TABLE_COUNT_ADDRESS,445);for(unsigned i=1000;i<1300;i++){set(64,i);assert(!pg_blip_diagnostic(&cache,memory,sizeof memory,64,0,report,0));}
 assert(reports==128&&cache.count==128);return 0;}
'''
        with tempfile.TemporaryDirectory(prefix='zgta-blip-native-') as directory:
            p=Path(directory);(p/'test.c').write_text(source)
            result=subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(APP/'Source'),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);subprocess.run([str(p/'test')],check=True)

if __name__=='__main__':unittest.main()
