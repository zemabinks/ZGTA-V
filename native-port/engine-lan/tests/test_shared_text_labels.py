"""Shared catalog parity, native cache safety and exact generated hook refusal."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'app'
SCRIPTS=APP/'Scripts'

def load(name):
    spec=importlib.util.spec_from_file_location(name,SCRIPTS/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class SharedLabels(unittest.TestCase):
    def test_generated_tables_match_catalog(self):
        for path,text in load('generate_text_labels').outputs().items():
            self.assertEqual(path.read_text(),text,path.name)

    def test_native_cache_original_priority_bounds_and_retry(self):
        source=r'''
#include "NativeTextFallback.h"
#include <assert.h>
static unsigned allocations,copies;
static int fail;
static unsigned char memory[8192];
static uint64_t allocate(void *ctx,size_t size) {
  (void)ctx;(void)size;allocations++;return fail==1?0:fail==2?8191:64;
}
static int copy(void *ctx,uint64_t at,const char *text,size_t size) {
  (void)ctx;if(at>sizeof memory||size>sizeof memory-at)return 0;
  memcpy(memory+at,text,size);copies++;return 1;
}
int main(void) {
  PGTextFallbackCache cache={0};uint32_t hash=0;
  for(unsigned i=0;i<PG_TEXT_LABEL_COUNT;i++) {
    assert(pg_text_label_index(pg_text_labels[i].hash)==(int)i);
    if(!strcmp(pg_text_labels[i].text,"Public Session"))hash=pg_text_labels[i].hash;
  }
  assert(hash);
  assert(pg_text_fallback(&cache,hash,777,allocate,copy,0)==777);
  assert(!allocations);
  assert(!pg_text_fallback(&cache,0x12345678,0,allocate,copy,0));assert(!allocations);
  fail=1;assert(!pg_text_fallback(&cache,hash,0,allocate,copy,0));
  fail=2;assert(!pg_text_fallback(&cache,hash,0,allocate,copy,0));assert(!copies);
  fail=0;assert(pg_text_fallback(&cache,hash,0,allocate,copy,0)==64);
  assert(!strcmp((const char*)memory+64,"Public Session"));assert(copies==1);
  assert(pg_text_fallback(&cache,hash,0,allocate,copy,0)==64);assert(allocations==3);
  assert(pg_text_fallback(&cache,hash,888,allocate,copy,0)==888);assert(allocations==3);
}
'''
        with tempfile.TemporaryDirectory(prefix='zgta-native-label-') as directory:
            p=Path(directory);(p/'fixture.c').write_text(source)
            subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(APP/'Source'),str(p/'fixture.c'),'-o',str(p/'fixture')],check=True,capture_output=True)
            subprocess.run([str(p/'fixture')],check=True)

    def test_generated_part_does_not_include_unguarded_implementation_twice(self):
        header=load('prepare_text_fallback').HEADER
        with tempfile.TemporaryDirectory(prefix='zgta-text-header-') as directory:
            p=Path(directory)
            (p/'game.h').write_text('#pragma once\n#include <stdint.h>\ntypedef uint32_t u32;typedef uint64_t u64;typedef struct {int value;} w2c_game;\n')
            (p/'game-impl.h').write_text('#include "game.h"\nstatic inline int sample(void){return 7;}\n')
            (p/'game-text-fallback-impl.h').write_text(header)
            (p/'part.c').write_text('#include "game-text-fallback-impl.h"\n#include "game-impl.h"\nint main(void){return sample()==7?0:1;}\n')
            result=subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(p),str(p/'part.c'),'-o',str(p/'test')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            subprocess.run([str(p/'test')],check=True)

    def test_exact_native_body_and_idempotent_hook(self):
        generated=APP/'Build/Phone-CleanHome-20261020/AppRoot/Generated/game_52.c'
        if not generated.exists():self.skipTest('Local generated native reference unavailable')
        patch=load('prepare_text_fallback')
        source=generated.read_text();start=source.index(patch.SIGNATURE);end=source.index('\n}\n',start)+3
        function=source[start:end]
        patched=patch.patch(function)
        self.assertIn(patch.PATCHED_RETURN,patched)
        self.assertEqual(patch.patch(patched),patched)
        with self.assertRaisesRegex(ValueError,'changed'):patch.patch(function.replace('32ull','64ull',1))
        with self.assertRaisesRegex(ValueError,'missing'):patch.patch('unreviewed generated source')

if __name__=='__main__':unittest.main()
