"""Native script-bank C staging and typed thread-local scope regressions."""
from pathlib import Path
from public_test_inputs import game_file
import hashlib
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import native_script_bank as native

ENGINE=game_file('b/8b0b5899ed/game.wasm')
GENERATED=ROOT.parent/'app/Build/EngineLAN-Experimental-20261016/AppRoot/Generated'

class NativeScriptBank(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patches,cls.helpers,cls.receipt=native.transform_generated(ENGINE.read_bytes(),GENERATED)

    def test_actual_pinned_wasm_and_generated_definitions_preserve_calls(self):
        self.assertEqual(set(self.patches),{'game_9.c','game_48.c'})
        for hook in native.script_bank.HOOKS:
            pin=native.C_PINS[hook['index']]
            original=(GENERATED/pin['part']).read_bytes()
            symbol=('w2c_game_f'+str(hook['index'])).encode()
            signature=pin['signature'].encode()
            expected=original.replace(signature,signature.replace(symbol,symbol+b'_zema_script_bank_original'),1)
            self.assertEqual(self.patches[pin['part']],expected)
        self.assertFalse(self.receipt['runtime_verified'])
        self.assertFalse(self.receipt['inputs_modified'])
        self.assertEqual(self.receipt['engine_sha256'],native.script_bank.ENGINE_SHA256)

    def test_changed_bodies_abi_engine_duplicates_and_second_patch_refused(self):
        with self.assertRaisesRegex(ValueError,'Unreviewed engine'):
            native.transform_generated(b'wrong engine',GENERATED)
        for hook in native.script_bank.HOOKS:
            pin=native.C_PINS[hook['index']]
            original=(GENERATED/pin['part']).read_bytes()
            signature=pin['signature'].encode()
            changed=original.replace(signature,signature.replace(b'u32 var_p1',b'u64 var_p1'),1)
            with self.assertRaisesRegex(ValueError,'bytes/ABI changed'):
                native.patch_part(changed,[hook])
            changed=original.replace(signature+b' {\n',signature+b' {\n  /* changed body */\n',1)
            with self.assertRaisesRegex(ValueError,'bytes/ABI changed'):
                native.patch_part(changed,[hook])
            with self.assertRaisesRegex(ValueError,'already patched'):
                native.patch_part(self.patches[pin['part']],[hook])
            with self.assertRaisesRegex(ValueError,'Repeated'):
                native.patch_part(original,[hook,hook])
            symbol='w2c_game_f'+str(hook['index'])
            duplicate=native.re.search(rb'(?ms)^u32 '+symbol.encode()+rb'\([^\n]*\) \{\n.*?^\}',original)[0]
            with self.assertRaisesRegex(ValueError,'duplicate'):
                native.patch_part(original+b'\n'+duplicate,[hook])

    def test_new_output_only_and_inputs_unchanged(self):
        baseline={name:hashlib.sha256((GENERATED/name).read_bytes()).hexdigest() for name in self.patches}
        with tempfile.TemporaryDirectory(prefix='zema-native-bank-plan-') as folder:
            parent=Path(folder).resolve()
            native.write_plan(parent/'new',self.patches,self.helpers,self.receipt)
            self.assertEqual((parent/'new').stat().st_mode&0o777,0o700)
            for name in [*self.patches,*self.helpers,'native-script-bank-plan.json']:
                self.assertEqual((parent/'new'/name).stat().st_mode&0o777,0o600)
            with self.assertRaisesRegex(ValueError,'New non-symlink'):
                native.write_plan(parent/'new',self.patches,self.helpers,self.receipt)
            (parent/'link').symlink_to(parent/'new',target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'New non-symlink'):
                native.write_plan(parent/'link'/'nested',self.patches,self.helpers,self.receipt)
        self.assertEqual(baseline,{name:hashlib.sha256((GENERATED/name).read_bytes()).hexdigest() for name in self.patches})

    def test_existing_patched_stage_verifies_without_original_folder(self):
        with tempfile.TemporaryDirectory(prefix='zema-native-bank-verify-') as folder:
            output=Path(folder).resolve()/'Generated'
            native.write_plan(output,self.patches,self.helpers,self.receipt)
            # No original folder is consulted: remaining translation units can be empty
            # because the receipt/pins cover the two transformed parts independently.
            for i in range(64):
                file=output/('game_'+str(i)+'.c')
                if not file.exists():file.write_bytes(b'/* unrelated translation unit */\n')
            self.assertEqual(native.verify_generated(ENGINE.read_bytes(),output),self.receipt)
            helper=output/'ZemaNativeScriptBank.c'
            helper.write_bytes(helper.read_bytes()+b'\n/* changed */\n')
            with self.assertRaisesRegex(ValueError,'helper bytes changed'):
                native.verify_generated(ENGINE.read_bytes(),output)
            helper.write_bytes(self.helpers[helper.name])
            part=output/'game_9.c';part.write_bytes(part.read_bytes()+b'\n/* changed */\n')
            with self.assertRaisesRegex(ValueError,'part bytes changed'):
                native.verify_generated(ENGINE.read_bytes(),output)
            part.write_bytes(self.patches[part.name])
            (output/'game_0.c').write_bytes(b'u32 w2c_game_f21855(w2c_game* i,u32 a,u32 b,u32 c) { return 0; }\n')
            with self.assertRaisesRegex(ValueError,'moved or unpatched'):
                native.verify_generated(ENGINE.read_bytes(),output)

    def test_helper_compiles_against_actual_generated_game_abi(self):
        with tempfile.TemporaryDirectory(prefix='zema-native-bank-abi-') as folder:
            directory=Path(folder)
            for name,data in self.helpers.items():(directory/name).write_bytes(data)
            result=subprocess.run(['/usr/bin/clang','-fsyntax-only','-std=c11','-Wall','-Wextra','-Werror','-I',str(directory),'-I',str(GENERATED),'-I',str(GENERATED.parent/'Tools/wabt-1.0.42/share/wabt/wasm2c'),str(directory/'ZemaNativeScriptBank.c')],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_compiled_typed_scope_nested_requests_and_other_threads(self):
        with tempfile.TemporaryDirectory(prefix='zema-native-bank-scope-') as folder:
            directory=Path(folder)
            (directory/'game.h').write_text('''#include <stdint.h>
typedef uint32_t u32; typedef uint64_t u64; typedef struct w2c_game { int fixture; } w2c_game;
u32 w2c_game_f21855(w2c_game*,u32,u32,u32);
u32 w2c_game_f7226(w2c_game*,u64,u32);
''')
            for name,data in self.helpers.items():(directory/name).write_bytes(data)
            binary=directory/'fixture'
            result=subprocess.run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-I',str(directory),str(directory/'ZemaNativeScriptBank.c'),str(ROOT/'tests/native_script_bank_fixture.c'),'-o',str(binary)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('NATIVE_SCRIPT_BANK_TYPED_TLS_NESTED_ORIGINAL_STATUS_PASS',result.stdout)

if __name__=='__main__':unittest.main()
