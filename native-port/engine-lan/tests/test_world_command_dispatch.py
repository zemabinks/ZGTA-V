"""Real pinned native names/ABI plus execution of the added typed C dispatch."""
from pathlib import Path
from public_test_inputs import game_file
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import world_commands as world
ENGINE = game_file('b/8b0b5899ed/game.wasm')
GENERATED = ROOT.parent/'app/Build/EngineLAN-NativeRepair-20261017/AppRoot/Generated'

class WorldDispatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ENGINE.read_bytes()
        cls.original = (GENERATED/'MugoatCommands.c').read_text()
        cls.extra = world.additions(cls.data, GENERATED)

    def test_only_new_command_dispatch_added_and_repatch_refused(self):
        modified = world.patch(self.original, self.data, GENERATED)
        decl, info, calls = self.extra
        restored = modified.replace(decl+'\n'+world.INFO+'\n'+info,world.INFO).replace(world.CALL+'\n'+calls,world.CALL)
        self.assertEqual(restored,self.original)
        with self.assertRaisesRegex(ValueError,'already present'):
            world.patch(modified,self.data,GENERATED)
        with self.assertRaisesRegex(ValueError,'Unreviewed'):
            world.patch(self.original,b'wrong engine',GENERATED)
        types, indices, names = world.gate.module_abi(self.data)
        names[world.COMMANDS[0][1]] = [1]
        with patch.object(world.gate,'module_abi',return_value=(types,indices,names)):
            with self.assertRaisesRegex(ValueError,'name/index/ABI'):
                world.additions(self.data,GENERATED)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'generated definition'):
                world.additions(self.data,Path(tmp))

    def test_actual_c_dispatch_enforces_count_type_and_value_bits(self):
        decl, info, calls = self.extra
        prelude='''#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <assert.h>
typedef uint32_t u32;typedef uint64_t u64;typedef float f32;
typedef struct {int unused;} w2c_game;
typedef struct {uint32_t type;uint64_t bits;} MugoatValue;
static int hits;
static float online_f32(uint64_t b){float f;uint32_t v=(uint32_t)b;memcpy(&f,&v,4);return f;}
'''
        mocks=[];checks=[]
        for alias,_,index,params,results in world.COMMANDS:
            result=world.C_TYPES[results[0]] if results else 'void'
            parameters=','.join(world.C_TYPES[t]+' v'+str(i) for i,t in enumerate(params))
            tests=''.join('assert(v'+str(i)+('==1.5f);' if t=='f32' else '=='+str(41+i)+');') for i,t in enumerate(params))
            mocks.append(f'{result} w2c_game_f{index}(w2c_game* instance'+(','+parameters if params else '')+') {(void)instance;'+tests+'hits++;'+('return 27;' if results else '')+'}')
            values=','.join('{'+str(world.TAGS[t])+','+('1069547520' if t=='f32' else str(41+i))+'}' for i,t in enumerate(params)) or '{0,0}'
            checks.append('{MugoatValue a[]={'+values+'},out={0};uint32_t p[8]={0},r=99;'
                f'assert(mugoat_command_info("mp:{alias}",p,8,&r)=={len(params)});'
                + ''.join(f'assert(p[{i}]=={world.TAGS[t]});' for i,t in enumerate(params))
                +f'assert(r=={world.TAGS[results[0]] if results else 0});int before=hits;'
                +f'assert(!mugoat_command_call(0,"mp:{alias}",a,{len(params)+1},&out));assert(hits==before);'
                + (f'uint32_t saved=a[0].type;a[0].type=99;assert(!mugoat_command_call(0,"mp:{alias}",a,{len(params)},&out));a[0].type=saved;assert(hits==before);' if params else '')
                +f'assert(mugoat_command_call(0,"mp:{alias}",a,{len(params)},&out));assert(hits==before+1);assert(out.type==r);assert(out.bits=={27 if results else 0});'+'}')
        source=prelude+decl+'\n'+'\n'.join(mocks)+'\n'+world.INFO+'\n'+info+'\nreturn -1;}\n'+world.CALL+'\n'+calls+'\nreturn false;}\nint main(void){'+'\n'.join(checks)+'return 0;}'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'fixture.c').write_text(source)
            result=subprocess.run(['/usr/bin/clang','-std=c11','-Wall','-Werror',str(p/'fixture.c'),'-o',str(p/'fixture')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            subprocess.run([str(p/'fixture')],check=True)

if __name__=='__main__':unittest.main()
