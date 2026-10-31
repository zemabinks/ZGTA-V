"""Execute authenticated engine state transitions against the actual draw adapters.

The fixture contains five original WASM bodies, not a reimplementation of their
state changes. Only direct callees and the stack-global index are relocated;
remaining host uniforms/state helpers are inert, typed imports. No game/start
function, resource loader, renderer or network session is instantiated.
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
# Original index, exact debug name, signature and raw code-body digest.
PINS = {
    64694: ('CShaderLib::SetStippleAlpha(unsigned int, bool)', ['i32','i32'], [],
            '2c9c7ba0b43e9ec48d613b7c49cf81b41c7707fa2f0f4d7059463f0d1bd53a2d'),
    64697: ('CShaderLib::ResetAlpha(bool, bool)', ['i32','i32'], [],
            'f84563ce451e81cef89c6e12bb44605ac25049d97887c3ae39529adcb8d8e916'),
    64708: ('CShaderLib::SetMSAAParams(rage::grcDevice::MSAAMode const&, bool)', ['i64'], [],
            '7e0fadb9a4e004494b2fbc258ceb8514625ae134ddf26734868f375a8794bed3'),
    43886: ('CShaderLib::ResetStippleAlpha()', [], [],
            '424b128b29a2b2e72d43d1b4e5d36a5d271de76b42e67cab300f197d6a448136'),
    9894: ('rage::grcStateBlock::SetBlendState(rage::grcStateBlock::grcBlendStateHandleEnum, unsigned int, unsigned long)',
           ['i32','i32','i64'], [], 'cd76c45c7fdf8adc8220bb777271c87d344322848d0f9f88af82555c4f0e2584'),
}
TABLE_PINS = {
    7344240: '884f278a64c266ef34867319781b0a4c5914f653810708336107a500b8c24778',
    7344304: 'b87826b95285d0856e865236d713a540bf4ddf204f338ba08932779250c18246',
}


def authenticated_inputs():
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
    r = b.gate.Reader(sections[10]); all_bodies = [r.take(r.uint()) for _ in range(r.count())]
    bodies = {}
    for index, (name, params, results, digest) in PINS.items():
        raw = all_bodies[index - imported]
        if (names.get(name) != [index] or types[indices[index]] != (params, results)
                or hashlib.sha256(raw).hexdigest() != digest):
            raise ValueError('Original state-function identity/type/body changed: ' + str(index))
        bodies[index] = raw
    r = b.gate.Reader(sections[11]); count = r.count()
    if count != 4077:
        raise ValueError('Original passive data layout changed')
    for _ in range(2638):
        if r.uint() != 1:
            raise ValueError('Expected original passive data segment')
        segment = r.take(r.uint())
    tables = {}
    for address, digest in TABLE_PINS.items():
        raw = segment[address - 7342850:address - 7342850 + 64]
        if len(raw) != 64 or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Original fade table changed')
        tables[address] = raw
    return bodies, tables


def relocate(raw, calls):
    """Decode each instruction, modifying only direct call/global immediates."""
    r = b.gate.Reader(raw)
    for _ in range(r.count()):
        r.uint(); kind = r.byte()
        if kind not in (0x7f, 0x7e, 0x7d, 0x7c, 0x7b):
            raise ValueError('Unexpected original local type')
    output = bytearray(raw[:r.pos]); seen = set()
    while r.pos < len(raw):
        start = r.pos; op = r.byte()
        if op == 0x10:
            index = r.uint()
            if index not in calls:
                raise ValueError('Unreviewed original direct callee: ' + str(index))
            output.extend(b'\x10' + b.leb(calls[index])); seen.add(index)
            continue
        if op in (0x23, 0x24):
            index = r.uint()
            if index != 0:
                raise ValueError('Unexpected original global')
            # Original stack-global0 remains global0 in the fixture.
            output.extend(bytes([op]) + b.leb(0))
            continue
        if op in (2, 3, 4): decoder.signed(r)
        elif op in (0x0c,0x0d,0x20,0x21,0x22): r.uint()
        elif op == 0x0e:
            for _ in range(r.count() + 1): r.uint()
        elif 0x28 <= op <= 0x3e: decoder.memarg(r)
        elif op in (0x41,0x42): decoder.signed(r)
        elif op == 0x43: r.take(4)
        elif op == 0x44: r.take(8)
        elif op == 0xfd:
            sub = r.uint()
            if sub <= 11 or sub in (92,93): decoder.memarg(r)
            elif sub in (12,13): r.take(16)
            elif 21 <= sub <= 34: r.take(1)
            elif 84 <= sub <= 91: decoder.memarg(r); r.take(1)
            elif sub > 0x113: raise ValueError('Unexpected original SIMD opcode')
        elif not (op in (0,1,5,0x0b,0x0f,0x1a,0x1b) or 0x45 <= op <= 0xc4):
            raise ValueError('Unexpected original instruction: ' + hex(op))
        output.extend(raw[start:r.pos])
    return bytes(output), seen


def fixture(module, originals):
    types = []
    def signature(params, results):
        value = (params, results)
        if value not in types: types.append(value)
        return types.index(value)
    imports = [
        ('lod',[],[]), ('unlock',['i64'],[]),
        ('begin',['i64','i32','i32','i32'],['i32']), ('end',[],[]),
        ('hint',['i64','i32','i32'],[]), ('current',[],['i64']),
        ('alloc',['i64'],['i64']), ('restore',['i64'],[]),
        ('emit',['i32','i64','i32'],[]), ('uniform',['i32','i64','i32'],[]),
        ('blend',['i32','i32'],[]), ('msaa',['i32','i64'],[]),
        ('predicate',[],['i32']),
    ]
    import_bytes = [b.string('mock') + b.string(n) + b'\0' + b.leb(signature(p,r)) for n,p,r in imports]
    ni = len(imports)
    original_order = list(PINS)
    relocated_indices = {index: ni + j for j,index in enumerate(original_order)}
    callee_map = dict(relocated_indices)
    callee_map.update({9859:9, 9893:10, 9871:11, 30146:12, 64689:12})
    bodies = []; functions = []; seen = set()
    for index in original_order:
        raw, calls = relocate(originals[index], callee_map)
        bodies.append(raw); seen.update(calls)
        functions.append(signature(PINS[index][1], PINS[index][2]))
    # Preserve and execute each production wrapper unchanged, with relocated
    # originals and existing typed emission dependencies only.
    wrapper_indices = {index: ni + len(bodies) + j for j,index in enumerate(module.HOOKS)}
    emitter_index = ni + len(bodies) + len(module.HOOKS)
    wrapped_originals = {44583:0, 9952:1, 9291:2, 9295:3,
                         64694:relocated_indices[64694], 43886:relocated_indices[43886]}
    code, emit = module.wrappers(wrapped_originals, (1,2,3,4), emitter_index,
        dict(hint=4,stack_current=5,stack_alloc=6,stack_restore=7,gpu_emit=8))
    wrapper_signatures = {44583:([],[]),9952:(['i64'],[]),9291:(['i64','i32','i32','i32'],['i32']),
                          9295:([],[]),64694:(['i32','i32'],[]),43886:([],[])}
    for index in module.HOOKS:
        bodies.append(code[index]); functions.append(signature(*wrapper_signatures[index]))
    bodies.append(emit); functions.append(signature(['i32'],[]))
    exported = {'begin':wrapper_indices[9291], 'end':wrapper_indices[9295],
                'alpha':wrapper_indices[64694], 'sample_reset':wrapper_indices[43886],
                'reset_alpha':relocated_indices[64697], 'set_msaa':relocated_indices[64708],
                'original_alpha':relocated_indices[64694], 'original_blend':relocated_indices[9894]}
    exports = [b.string(n) + b'\0' + b.leb(i) for n,i in exported.items()]
    exports += [b.string('memory') + b'\x02\0', b.string('engine_stack') + b'\x03\0']
    inverse = {name: kind for kind,name in b.gate.TYPES.items()}
    type_bytes = [b'\x60' + b.leb(len(p)) + bytes(inverse[v] for v in p)
                  + b.leb(len(r)) + bytes(inverse[v] for v in r) for p,r in types]
    globals_ = b'\x7e\x01' + module.i64(65536) + b'\x0b' + b''.join(
        b'\x7f\x01' + module.i32(v) + b'\x0b' for v in (0,255,0,0))
    wasm = b'\0asm\x01\0\0\0' + b.section(1,b.leb(len(types)) + b''.join(type_bytes))
    wasm += b.section(2,b.leb(ni) + b''.join(import_bytes))
    wasm += b.section(3,b.leb(len(functions)) + b''.join(b.leb(i) for i in functions))
    wasm += b.section(5,b'\x01\x04' + b.leb(512))
    wasm += b.section(6,b'\x05' + globals_)
    wasm += b.section(7,b.leb(len(exports)) + b''.join(exports))
    wasm += b.section(10,b.leb(len(bodies)) + b''.join(b.leb(len(v)) + v for v in bodies))
    return wasm, sorted(seen)


class FadeState104(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.originals, cls.tables = authenticated_inputs()

    def run_fixture(self, module):
        wasm, callees = fixture(module, self.originals)
        result = subprocess.run(['node',str(ROOT/'tests/fade_state104.cjs')],
            input=json.dumps(dict(wasm=base64.b64encode(wasm).decode(),
                                  tables={str(k):v.hex() for k,v in self.tables.items()})),
            text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout + result.stderr)
        report = json.loads(result.stdout)
        report['actual_original_callees'] = callees
        return report

    def test_authenticated_state_sequences_current_adapter(self):
        report = self.run_fixture(current)
        self.assertEqual(report['original_state_assertions'], 'PASS')
        failed = [row for row in report['cases'] if not row['passed']]
        self.assertEqual(failed, [], json.dumps(failed,indent=2))
        self.assertGreaterEqual(len(report['cases']),10)
        print('FADE_STATE104_ORIGINAL_WASM_PASS: ' + json.dumps(report,sort_keys=True))

    def test_retained103_negative_control_detects_stale_state(self):
        previous = ROOT.parents[2]/'zgta-fade103-20261028/native-port/engine-lan/render_hooks.py'
        if not previous.exists(): self.skipTest('Retained103 source unavailable')
        if hashlib.sha256(previous.read_bytes()).hexdigest() != '649f68726155464b2afa95c14d49086b77211e42501cff5e79bad4c6fa068c55':
            raise ValueError('Retained103 negative-control source changed')
        spec = importlib.util.spec_from_file_location('retained_fade103_state104',previous)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        report = self.run_fixture(module)
        self.assertEqual(report['original_state_assertions'], 'PASS')
        failed = {row['name'] for row in report['cases'] if not row['passed']}
        self.assertTrue({'reset_alpha_true','set_msaa_reset','sample_only_reset',
                         'authoritative_external_mask','msaa_all_ones_mask','msaa_zero_mask',
                         'msaa_reset_alpha_true'} <= failed,
                        json.dumps(report,indent=2))
        print('FADE_STATE104_BUILD103_NEGATIVE_CONTROL_PASS: ' + json.dumps(report,sort_keys=True))


if __name__ == '__main__': unittest.main()
