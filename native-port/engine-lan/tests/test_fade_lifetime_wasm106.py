"""Execute the authenticated original DrawInternal WASM and its inline EndDraw.

This bounded fixture relocates only direct calls, globals and indirect-call type
indices. It executes the original branches, two-pass loop and effect-clear store;
typed imports stand in for BeginDraw, effect-pass binding and geometry drawing.
No game start function, resource loader, GPU, asset or network session runs. This
proves adapter lifetime behavior, not that the owner's scene is visually fixed.
"""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import browser_wasm as b
import online_wasm as decoder
import render_hooks as current

ORIGINAL_SHA = '11ca8d2c04c5e843d18ff4aea4899d72c86973c6b031df334e67c446b2ae83e0'
BODY_SHA = 'e8251640feeefd16e5b2033fdc2641c262c1452cd3c6d23a5367b17209e74207'
NAME = 'rage::grmShader::DrawInternal(rage::grmShader::eDrawType, rage::grmModel const&, int, bool) const'
PARAMS = ['i64', 'i32', 'i64', 'i32']
RETAINED_SHA = 'dc0b606b1fcaa10e94672821f34f3e9fb888ab86cdd4a5fa1060de4053c872e0'


def authenticated_body():
    source = Path(os.environ.get('ZGTA_ORIGINAL_ENGINE', str(Path.home() /
        'Library/Application Support/ZRemote Controller/Games/playgta5-offline/mirror/playgta5.com/b/8b0b5899ed/game.wasm')))
    if not source.exists():
        raise unittest.SkipTest('Owner-supplied original WASM is unavailable')
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != ORIGINAL_SHA:
        raise ValueError('Unreviewed original engine identity')
    types, indices, names = b.gate.module_abi(data)
    sections = dict(b.gate.sections(data))
    r = b.gate.Reader(sections[3]); imported = len(indices) - r.count()
    r = b.gate.Reader(sections[10])
    bodies = [r.take(r.uint()) for _ in range(r.count())]; r.finish()
    raw = bodies[9299 - imported]
    if (names.get(NAME) != [9299] or types[indices[9299]] != (PARAMS, [])
            or hashlib.sha256(raw).hexdigest() != BODY_SHA):
        raise ValueError('Original DrawInternal name/type/body changed')
    if types[1] != (['i64'], []) or types[21] != ([], ['i32']):
        raise ValueError('Original indirect-call signatures changed')
    pin = next(row for row in current.LIFETIME_PINS if row['index'] == 9299)
    if pin['body_sha256'] != BODY_SHA or pin['params'] != PARAMS:
        raise ValueError('Production lifetime pin differs from authenticated input')
    return raw


def relocate(raw, calls, indirect_types):
    """Decode every instruction, preserving all non-index instruction bytes."""
    r = b.gate.Reader(raw)
    for _ in range(r.count()):
        r.uint()
        if r.byte() not in (0x7f, 0x7e):
            raise ValueError('Unexpected original local type')
    out = bytearray(raw[:r.pos]); seen = {'calls': [], 'globals': [], 'indirect_types': []}
    boundaries = {r.pos}
    while r.pos < len(raw):
        start = r.pos; opcode = r.byte()
        if opcode == 0x10:
            index = r.uint()
            if index not in calls:
                raise ValueError('Unreviewed DrawInternal callee: ' + str(index))
            out.extend(current.op(opcode, calls[index])); seen['calls'].append(index)
        elif opcode in (0x23, 0x24):
            index = r.uint()
            if index not in (1, 27):
                raise ValueError('Unreviewed original global: ' + str(index))
            out.extend(current.op(opcode, {1: 0, 27: 1}[index])); seen['globals'].append(index)
        elif opcode == 0x11:
            kind, table = r.uint(), r.uint()
            if table != 0 or kind not in indirect_types:
                raise ValueError('Unreviewed indirect-call boundary')
            out.extend(b'\x11' + b.leb(indirect_types[kind]) + b'\0')
            seen['indirect_types'].append(kind)
        else:
            if opcode in (2, 3, 4): decoder.signed(r)
            elif opcode in (0x0c, 0x0d, 0x20, 0x21, 0x22): r.uint()
            elif 0x28 <= opcode <= 0x3e: decoder.memarg(r)
            elif opcode in (0x41, 0x42): decoder.signed(r)
            elif not (opcode in (0, 1, 5, 0x0b, 0x0f, 0x1a, 0x1b) or 0x45 <= opcode <= 0xc4):
                raise ValueError('Unexpected original instruction: ' + hex(opcode))
            out.extend(raw[start:r.pos])
        boundaries.update((start, r.pos))
    needle = bytes.fromhex('4298e8f6054200370300')
    if raw.count(needle) != 1 or raw.index(needle) != 253:
        raise ValueError('Original inline effect-clear statement changed')
    if not {253, 258, 260, 263} <= boundaries:
        raise ValueError('Inline clear is not on original instruction boundaries')
    if seen != {'calls': [9291, 9543, 9549], 'globals': [1, 27], 'indirect_types': [1, 21]}:
        raise ValueError('Original DrawInternal dependency inventory changed')
    return bytes(out), seen


def fixture(module, raw, inline_cleanup):
    types = []
    def signature(params, results):
        value = (params, results)
        if value not in types: types.append(value)
        return types.index(value)
    imports = [
        ('lod', [], []), ('unlock', ['i64'], []),
        ('begin', ['i64', 'i32', 'i32', 'i32'], ['i32']), ('end', [], []),
        ('alpha', ['i32', 'i32'], []), ('reset', [], []),
        ('hint', ['i64', 'i32', 'i32'], []), ('current', [], ['i64']),
        ('alloc', ['i64'], ['i64']), ('restore', ['i64'], []),
        ('emit', ['i32', 'i64', 'i32'], []), ('bind_pass', ['i64', 'i32', 'i64'], []),
        ('end_pass', [], []), ('geometry', ['i64'], []),
    ]
    import_bytes = [b.string('mock') + b.string(n) + b'\0' + b.leb(signature(p, r))
                    for n, p, r in imports]
    ni = len(imports)
    wrappers = {index: ni + j for j, index in enumerate(module.HOOKS)}
    emitter_index, draw_index = ni + len(module.HOOKS), ni + len(module.HOOKS) + 1
    globals_ = (2, 3, 4, 5)
    code, emitter = module.wrappers({44583: 0, 9952: 1, 9291: 2, 9295: 3,
                                    64694: 4, 43886: 5}, globals_, emitter_index,
        dict(hint=6, stack_current=7, stack_alloc=8, stack_restore=9, gpu_emit=10))
    relocated, seen = relocate(raw, {9291: wrappers[9291], 9543: 11, 9549: 12},
        {1: signature(['i64'], []), 21: signature([], ['i32'])})
    if inline_cleanup:
        # This is the production injection, applied after typed index relocation.
        clear = (current.op(0x23, globals_[2]) + b'\x04\x40' + current.i32(0)
                 + current.op(0x24, globals_[2]) + current.i32(0)
                 + current.op(0x10, emitter_index) + b'\x0b')
        relocated = current.patch_inline_wasm(relocated, clear)
    signatures = {44583: ([], []), 9952: (['i64'], []),
                  9291: (['i64', 'i32', 'i32', 'i32'], ['i32']), 9295: ([], []),
                  64694: (['i32', 'i32'], []), 43886: ([], [])}
    functions = [signature(*signatures[index]) for index in module.HOOKS]
    functions += [signature(['i32'], []), signature(PARAMS, [])]
    bodies = [code[index] for index in module.HOOKS] + [emitter, relocated]
    inverse = {name: kind for kind, name in b.gate.TYPES.items()}
    type_bytes = [b'\x60' + b.leb(len(p)) + bytes(inverse[v] for v in p)
                  + b.leb(len(r)) + bytes(inverse[v] for v in r) for p, r in types]
    exports = [b.string('draw') + b'\0' + b.leb(draw_index),
               b.string('begin') + b'\0' + b.leb(wrappers[9291]),
               b.string('end') + b'\0' + b.leb(wrappers[9295]),
               b.string('memory') + b'\x02\0', b.string('active') + b'\x03\x04']
    global_bytes = b''.join(b'\x7e\x01' + current.i64(0) + b'\x0b' for _ in range(2))
    global_bytes += b''.join(b'\x7f\x01' + current.i32(v) + b'\x0b' for v in (0, 255, 0, 0))
    wasm = b'\0asm\x01\0\0\0' + b.section(1, b.leb(len(types)) + b''.join(type_bytes))
    wasm += b.section(2, b.leb(ni) + b''.join(import_bytes))
    wasm += b.section(3, b.leb(len(functions)) + b''.join(b.leb(v) for v in functions))
    # Original call_indirect indices are i64: retain a genuine table64 call.
    wasm += b.section(4, b'\x01\x70\x04\x01')
    wasm += b.section(5, b'\x01\x04' + b.leb(512))
    wasm += b.section(6, b'\x06' + global_bytes)
    wasm += b.section(7, b.leb(len(exports)) + b''.join(exports))
    wasm += b.section(9, b'\x01\x00' + current.i64(0) + b'\x0b\x01\x0d')
    wasm += b.section(10, b.leb(len(bodies)) + b''.join(b.leb(len(v)) + v for v in bodies))
    return wasm, seen


class FadeLifetimeWasm106(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = authenticated_body()
        previous = ROOT.parents[2] / 'zgta-fade105-20261028/native-port/engine-lan/render_hooks.py'
        if not previous.exists():
            raise unittest.SkipTest('Retained 104/105 adapter source is unavailable')
        if hashlib.sha256(previous.read_bytes()).hexdigest() != RETAINED_SHA:
            raise ValueError('Retained 104/105 negative-control source changed')
        spec = importlib.util.spec_from_file_location('retained105_lifetime106', previous)
        cls.previous = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.previous)

    def run_fixture(self, module, inline_cleanup):
        wasm, seen = fixture(module, self.raw, inline_cleanup)
        result = subprocess.run(['node', str(ROOT / 'tests/fade_lifetime_wasm106.cjs')],
            input=json.dumps(dict(wasm=base64.b64encode(wasm).decode())),
            text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        report['authenticated_original_sha256'] = BODY_SHA
        report['relocated_dependencies'] = seen
        return report

    def test_actual_drawinternal_current_cleanup(self):
        report = self.run_fixture(current, True)
        failed = [row for row in report['cases'] if not row['passed']]
        self.assertEqual(failed, [], json.dumps(report, indent=2))
        self.assertEqual(len(report['cases']), 6)
        print('FADE_LIFETIME106_ACTUAL_WASM_PASS: ' + json.dumps(report, sort_keys=True))

    def test_retained105_fails_both_lifetime_boundaries(self):
        report = self.run_fixture(self.previous, False)
        failed = {row['name'] for row in report['cases'] if not row['passed']}
        self.assertEqual(failed, {'inline_end_cleanup', 'consecutive_ordinary_draw',
            'begin_available_clears_stale', 'begin_empty_clears_stale',
            'begin_full_fallback_clears_stale'}, json.dumps(report, indent=2))
        print('FADE_LIFETIME106_RETAINED105_NEGATIVE_CONTROL_PASS: ' + json.dumps(report, sort_keys=True))

    def test_each_production_correction_has_independent_effect(self):
        entry_only = self.run_fixture(current, False)
        inline_only = self.run_fixture(self.previous, True)
        self.assertEqual({r['name'] for r in entry_only['cases'] if not r['passed']},
                         {'inline_end_cleanup'})
        self.assertEqual({r['name'] for r in inline_only['cases'] if not r['passed']},
                         {'begin_available_clears_stale', 'begin_empty_clears_stale',
                          'begin_full_fallback_clears_stale'})


if __name__ == '__main__': unittest.main()
