"""Offline ABI/corruption regressions; fixtures contain no game code."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('engine_lan', ROOT / 'Scripts/inspect_engine_lan.py')
lan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lan)
sys.path.insert(0, str(ROOT / 'Scripts'))
import prepare_engine_lan_adapter as adapter


def leb(value):
    out = bytearray()
    while True:
        byte = value & 127
        value >>= 7
        out.append(byte | (128 if value else 0))
        if not value:
            return bytes(out)


def string(value):
    data = value.encode()
    return leb(len(data)) + data


def section(kind, body):
    return bytes([kind]) + leb(len(body)) + body


def fixture(names=None, code_count=1, imports=False):
    if names is None:
        names = [(0, 'Engine::Send()')]
    header = b'\0asm\x01\0\0\0'
    # (i64, i32) -> i32; the body returns its second argument.
    types = section(1, b'\x01\x60\x02\x7e\x7f\x01\x7f')
    imported = b''
    if imports:
        # Shared memory64 and an imported function: only the function shifts
        # the definition's index; the memory does not.
        imported = section(2, b'\x02' + string('env') + string('memory') +
                           b'\x02\x07\x01\x02' + string('env') + string('call') + b'\x00\x00')
    functions = section(3, b'\x01\x00')
    body = b'\x00\x20\x01\x0b'
    code = section(10, leb(code_count) + (leb(len(body)) + body) * code_count)
    named = leb(len(names)) + b''.join(leb(i) + string(name) for i, name in names)
    return header + types + imported + functions + code + section(0, string('name') + section(1, named))


def contract(data, index=0):
    return {'engine_sha256': hashlib.sha256(data).hexdigest(), 'upstream_revision': 'fixture',
            'hooks': [{'field': 'send', 'group': 'vnet', 'name': 'Engine::Send()',
                       'index': index, 'params': ['i64', 'i32'], 'results': ['i32']}]}


class EngineLanTests(unittest.TestCase):
    def test_exact_abi_is_inspection_only_and_does_not_modify_input(self):
        data = fixture(); original = bytes(data)
        result = lan.inspect(data, contract(data))
        self.assertEqual(data, original)
        self.assertEqual(result['hooks_resolved'], 1)
        self.assertEqual(result['hooks'][0]['c_symbol'], 'w2c_game_f0')
        self.assertFalse(result['runtime_enabled'])
        self.assertFalse(result['runtime_verified'])
        self.assertEqual(result['browser_integration'], 'NOT_IMPLEMENTED')

    def test_wrong_engine_rejected_before_any_address_resolution(self):
        data = fixture()
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            lan.inspect(data + b'changed', contract(data))

    def test_missing_or_moved_hook_refused(self):
        for names in [[], [(0, 'Different::Send()')]]:
            data = fixture(names)
            with self.assertRaisesRegex(ValueError, 'Missing, ambiguous or moved'):
                lan.inspect(data, contract(data))
        data = fixture(); record = contract(data); record['hooks'][0]['index'] = 1
        with self.assertRaisesRegex(ValueError, 'moved'):
            lan.inspect(data, record)

    def test_ambiguous_hook_refused(self):
        data = fixture([(0, 'Engine::Send()'), (1, 'Engine::Send()')], imports=True)
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            lan.inspect(data, contract(data))

    def test_parameter_and_return_abi_changes_refused(self):
        data = fixture()
        for field, value in [('params', ['i32', 'i32']), ('results', ['i64']), ('results', [])]:
            record = contract(data); record['hooks'][0][field] = value
            with self.assertRaisesRegex(ValueError, 'signature mismatch'):
                lan.inspect(data, record)

    def test_imported_functions_shift_indices_but_shared_memory64_does_not(self):
        data = fixture([(1, 'Engine::Send()')], imports=True)
        result = lan.inspect(data, contract(data, 1))
        self.assertEqual(result['hooks'][0]['c_symbol'], 'w2c_game_f1')

    def test_duplicate_contract_fields_refused(self):
        data = fixture(); record = contract(data)
        record['hooks'].append(copy.deepcopy(record['hooks'][0]))
        with self.assertRaisesRegex(ValueError, 'repeated hook'):
            lan.inspect(data, record)

    def test_truncation_overflow_and_duplicate_sections_refused(self):
        valid = fixture()
        corrupt = [valid[:7], valid[:-1], valid[:8] + b'\x01' + b'\x80' * 11,
                   valid + section(3, b'\x00')]
        for data in corrupt:
            with self.subTest(data=data[:12]), self.assertRaises(ValueError):
                lan.inspect(data, contract(data))

    def test_code_count_and_function_name_bounds_refused(self):
        for data in [fixture(code_count=0), fixture([(2, 'Engine::Send()')]),
                     fixture([(0, 'Engine::Send()'), (0, 'SameIndex()')])]:
            with self.assertRaises(ValueError):
                lan.inspect(data, contract(data))

    def test_type_index_and_oversized_vectors_refused(self):
        data = fixture().replace(section(3, b'\x01\x00'), section(3, b'\x01\x01'))
        with self.assertRaisesRegex(ValueError, 'function/type'):
            lan.inspect(data, contract(data))
        data = fixture()[:8] + section(1, leb(1_000_001))
        with self.assertRaisesRegex(ValueError, 'Oversized'):
            lan.inspect(data, contract(data))

    def test_changed_or_symlinked_reference_refused_without_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / 'hooks.rs'
            original = b'not executable source data'
            source.write_bytes(original)
            record = {'upstream_files': {'hooks.rs': hashlib.sha256(original).hexdigest()}}
            lan.verify_reference(root, record)
            source.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'changed'):
                lan.verify_reference(root, record)
            source.unlink(); source.symlink_to(root / 'other.rs')
            with self.assertRaisesRegex(ValueError, 'symlinks'):
                lan.verify_reference(root, record)

    def test_reference_traversal_refused(self):
        for name in ['../outside', '/absolute']:
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                lan.verify_reference(Path('/unused'), {'upstream_files': {name: 'fixture'}})

    def test_generated_c_mapping_and_signature_drift(self):
        data = fixture(); hooks = contract(data)['hooks']
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            for i in range(64):
                (root / f'game_{i}.c').write_text('')
            path = root / 'game_7.c'
            definition = 'u32 w2c_game_f0(w2c_game* instance, u64 arg0, u32 arg1) {\n}\n'
            path.write_text(definition)
            result = lan.inspect_generated(root, hooks)
            self.assertEqual(result['parts_containing_hooks'], 1)
            self.assertEqual(result['definitions'][0]['part'], 'game_7.c')
            self.assertFalse(result['runtime_enabled'])
            path.write_text(definition.replace('u64 arg0', 'u32 arg0'))
            with self.assertRaisesRegex(ValueError, 'signature mismatch'):
                lan.inspect_generated(root, hooks)

    def test_missing_duplicate_and_symlinked_generated_definitions_refused(self):
        data = fixture(); hooks = contract(data)['hooks']
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with self.assertRaisesRegex(ValueError, '64-part'):
                lan.inspect_generated(root, hooks)
            for i in range(64):
                (root / f'game_{i}.c').write_text('')
            with self.assertRaisesRegex(ValueError, 'Missing or duplicate'):
                lan.inspect_generated(root, hooks)
            definition = 'u32 w2c_game_f0(w2c_game* instance, u64 a, u32 b) {\n}\n'
            (root / 'game_0.c').write_text(definition * 2)
            with self.assertRaisesRegex(ValueError, 'Missing or duplicate'):
                lan.inspect_generated(root, hooks)
            path = root / 'game_1.c'; path.unlink(); path.symlink_to(root / 'game_0.c')
            with self.assertRaisesRegex(ValueError, 'symlinks'):
                lan.inspect_generated(root, hooks)

    def test_patch_plan_changes_definitions_only_and_rejects_wrong_bytes(self):
        hook = contract(fixture())['hooks'][0]
        original = b'u32 w2c_game_f0(w2c_game* instance, u64 a, u32 b) {\n  return w2c_game_f0(instance, a, b);\n}\n'
        digest = hashlib.sha256(original).hexdigest()
        changed = adapter.patch_part(original, [hook], digest)
        self.assertEqual(changed, original.replace(b'u32 w2c_game_f0(', b'u32 w2c_game_f0_zema_lan_original(', 1))
        self.assertIn(b'return w2c_game_f0(instance, a, b)', changed)
        with self.assertRaisesRegex(ValueError, 'bytes changed'):
            adapter.patch_part(original + b'changed', [hook], digest)
        with self.assertRaisesRegex(ValueError, 'already contains'):
            adapter.patch_part(changed, [hook], hashlib.sha256(changed).hexdigest())

    def test_adapter_output_cannot_overwrite_or_escape_build_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); output = root / 'Build/Isolated'
            adapter.write_adapter(output, 'header', 'source', {'applied': False}, root)
            with self.assertRaises(ValueError):
                adapter.write_adapter(output, 'changed', 'changed', {}, root)
            self.assertEqual((output / 'ZemaEngineLAN.c').read_text(), 'source')
            for unsafe in [root / 'Original', root / 'Build/../Original']:
                with self.assertRaises(ValueError):
                    adapter.write_adapter(unsafe, '', '', {}, root)
            self.assertFalse((root / 'Original').exists())

    def test_adapter_rejects_unsafe_c_identifiers_and_unsupported_signatures(self):
        for field, value in [('field', 'x;inject'), ('params', ['externref']), ('results', ['i32', 'i32'])]:
            hook = contract(fixture())['hooks'][0]; hook[field] = value
            with self.assertRaises(ValueError):
                adapter.render([hook])

    def test_compiled_c_adapter_fallback_delegation_and_immutable_installation(self):
        hooks = [
            {'field': 'send', 'index': 1, 'params': ['i64', 'i32'], 'results': ['i64']},
            {'field': 'sample', 'index': 2, 'params': ['f64'], 'results': ['f64']},
            {'field': 'tick', 'index': 3, 'params': [], 'results': []},
        ]
        header, source = adapter.render(hooks)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / 'ZemaEngineLAN.h').write_text(header)
            (root / 'ZemaEngineLAN.c').write_text(source)
            (root / 'game.h').write_text('''#pragma once
#include <stdint.h>
typedef uint32_t u32; typedef uint64_t u64; typedef float f32; typedef double f64;
typedef struct { u64 cookie; } w2c_game;
u64 w2c_game_f1(w2c_game*, u64, u32);
f64 w2c_game_f2(w2c_game*, f64);
void w2c_game_f3(w2c_game*);
''')
            (root / 'main.c').write_text('''#include "ZemaEngineLAN.h"
#include <assert.h>
static int ticks;
u64 w2c_game_f1_zema_lan_original(w2c_game* g, u64 a, u32 b) { return a + b + g->cookie; }
f64 w2c_game_f2_zema_lan_original(w2c_game* g, f64 a) { return a * 2 + g->cookie; }
void w2c_game_f3_zema_lan_original(w2c_game* g) { ticks += (int)g->cookie; }
static u64 intercept(w2c_game* g, u64 a, u32 b) { return w2c_game_f1_zema_lan_original(g, a, b) + 10; }
static void tick(w2c_game* g) { w2c_game_f3_zema_lan_original(g); ticks += 100; }
int main(void) {
  w2c_game g = { .cookie = 3 };
  const u64 large = 0x1ffffffffULL;
  assert(w2c_game_f1(&g, large, 4) == large + 7);
  assert(w2c_game_f2(&g, 1.25) == 5.5);
  w2c_game_f3(&g); assert(ticks == 3);
  assert(!ZemaEngineLANInstall(0));
  ZemaEngineLANHooks hooks = { .send = intercept, .tick = tick };
  assert(ZemaEngineLANInstall(&hooks));
  hooks.send = 0; hooks.tick = 0;
  assert(!ZemaEngineLANInstall(&hooks));
  assert(w2c_game_f1(&g, large, 4) == large + 17);
  assert(w2c_game_f2(&g, 1.25) == 5.5);
  w2c_game_f3(&g); assert(ticks == 106);
  return 0;
}
''')
            binary = root / 'adapter-test'
            subprocess.run(['/usr/bin/clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            str(root / 'main.c'), str(root / 'ZemaEngineLAN.c'), '-o', str(binary)],
                           check=True, capture_output=True, timeout=60)
            subprocess.run([str(binary)], check=True, capture_output=True, timeout=10)


if __name__ == '__main__':
    unittest.main()
