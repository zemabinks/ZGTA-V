"""Pinned, index-preserving far-light upload and missing fade-technique hooks.

Adapted from Glue5 5e2354af/e2bffe29 (GPL-3.0). The existing engine bodies,
types, imports, table slots and networking ABI remain fixed. Browser wrappers
are WASM code, not JavaScript calls on each draw. Native wrappers retain exact
generated originals. This is static source evidence, not gameplay validation.
"""
import hashlib
import json
from pathlib import Path
import re
import browser_wasm as b

ROOT = Path(__file__).resolve().parent
PINS = json.loads((ROOT / 'render-hooks-pins.json').read_text())
HOOKS = (44583, 9952, 9291, 9295, 64694, 43886)
FORCED, DEFERRED, FADES = 6634168, 21490232, (7248300, 7248304, 7248320)
MARKER = b'zgta-render-hooks98'


def op(code, value):
    return bytes([code]) + b.leb(value)


def i32(value):
    return b'\x41' + b.sleb(value)


def i64(value):
    return b'\x42' + b.sleb(value)


def load32(address):
    return i64(address) + b'\x28\x02\x00'


def store32(address, value):
    return i64(address) + value + b'\x36\x02\x00'


def body(locals_, instructions):
    return b.leb(len(locals_)) + b''.join(b.leb(count) + bytes([kind]) for count, kind in locals_) + instructions + b'\x0b'


def wrappers(originals, globals_, emit, dependencies=None, legacy98=False, legacy103=False, legacy104=False):
    """Generate wrappers parameterized by indices, also used by executable tests."""
    if legacy98:
        lod, alpha, stippling = globals_
        invert = None
    else:
        lod, alpha, stippling, invert = globals_
    get = lambda n: op(0x20, n)
    set_ = lambda n: op(0x21, n)
    gg = lambda n: op(0x23, n)
    gs = lambda n: op(0x24, n)
    call = lambda n: op(0x10, n)
    deps = dependencies or dict(hint=244, stack_current=91109, stack_alloc=91108, stack_restore=91107, gpu_emit=550)
    orig = lambda n: call(originals[n])
    emit_ = lambda value: value + call(emit)
    code = {}
    # Preserve nested entry state; no hint can escape the rendering call.
    code[44583] = body([(1, 0x7f)], gg(lod) + set_(0) + i32(1) + gs(lod) + orig(44583) + get(0) + gs(lod))
    # Large buffers only; small-buffer hints would linger in the D3D hint table.
    resource = get(0) + b'\x29\x03' + b.leb(80)
    offset = get(0) + b'\x28\x02' + b.leb(96)
    size = get(0) + b'\x28\x02' + b.leb(100)
    code[9952] = body([], gg(lod) + b'\x04\x40' + resource + i64(0) + b'\x52' + size + i32(128 << 10) + b'\x4b\x71\x04\x40' + resource + offset + size + call(deps['hint']) + b'\x0b\x0b' + get(0) + orig(9952))
    args = b''.join(get(p) for p in range(4))
    # Locals 4=passes,5=forced group,6=original 16-bit mask,7=2x2 phase bits.
    clear = gg(stippling) + b'\x04\x40' + i32(0) + gs(stippling) + emit_(i32(0)) + b'\x0b'
    begin = (b'' if legacy98 or legacy103 or legacy104 else clear) + args + orig(9291) + set_(4)
    begin += get(4) + get(3) + b'\x72\x04\x40' + get(4) + b'\x0f\x0b'
    begin += load32(FORCED) + set_(5)
    begin += get(5) + i32(0) + b'\x48\x04\x40' + get(4) + b'\x0f\x0b'
    is_fade = b''.join(get(5) + load32(at) + b'\x46' + (b'\x72' if j else b'') for j, at in enumerate(FADES))
    begin += is_fade + b'\x45\x04\x40' + get(4) + b'\x0f\x0b'
    if legacy98:
        # Frozen Build98–102 producer recipe; never used for a new runtime.
        begin += store32(FORCED, load32(DEFERRED)) + args + orig(9291) + set_(4) + store32(FORCED, get(5))
        begin += get(4) + b'\x04\x40'
        begin += gg(alpha) + i32(255) + gg(alpha) + i32(255) + b'\x49\x1b' + i32(16) + b'\x6c' + i32(127) + b'\x6a' + i32(255) + b'\x6e' + set_(6)
        begin += get(6) + i32(16) + b'\x49\x04\x40'
        begin += emit_(get(6) + i32(1) + get(6) + i32(1) + b'\x4b\x1b') + i32(1) + gs(stippling) + b'\x0b\x0b' + get(4)
        code[9291] = body([(3, 0x7f)], begin)
        code[9295] = body([], orig(9295) + gg(stippling) + b'\x04\x40' + i32(0) + gs(stippling) + emit_(i32(0)) + b'\x0b')
        code[64694] = body([], get(0) + gs(alpha) + get(0) + get(1) + orig(64694))
        code[43886] = body([], i32(255) + gs(alpha) + orig(43886))
    else:
        # The original non-MSAA globalFade shader keeps a phase iff its mask
        # nibble is 15. Read the original guest table, preserving its quantization
        # and invert complement; a Bayer coverage approximation is not equivalent.
        clamped = gg(alpha) + i32(255) + gg(alpha) + i32(255) + b'\x49\x1b'
        address = i64(7344304) + clamped + i32(3) + b'\x76' + i32(1) + b'\x74\xad\x7c'
        shadow_mask = address + b'\x2f\x01\x00' + i32(0) + gg(invert) + b'\x6b\x73' + i32(65535) + b'\x71'
        if legacy103:
            begin += shadow_mask + set_(6)
        else:
            # GlobalFade has additional original reset paths (64697/64708).
            # Read its authoritative state at this draw, not the last setter
            # arguments. MSAA intentionally leaves that 16-bit field stale;
            # preserve its separate path and observe real sample-mask resets.
            begin += load32(12623176) + load32(7344224) + b'\x4b\x04\x40'
            begin += i64(12433376) + b'\x29\x03\x00' + i64(-1) + b'\x51\x04\x40' + i32(65535) + set_(6)
            begin += b'\x05' + i64(12433376) + b'\x29\x03\x00\x50\x04\x40' + i32(0) + set_(6)
            begin += b'\x05' + shadow_mask + set_(6) + b'\x0b\x0b'
            begin += b'\x05' + i64(23984584) + b'\x2f\x01\x00' + set_(6) + b'\x0b'
        phases = b''
        for phase in range(4):
            phases += get(6) + i32(phase * 4) + b'\x76' + i32(15) + b'\x71' + i32(15) + b'\x46' + i32(phase) + b'\x74'
            if phase: phases += b'\x72'
        begin += phases + set_(7)
        # An empty missing-technique draw stays missing: do not enter Deferred.
        begin += get(7) + b'\x45\x04\x40' + get(4) + b'\x0f\x0b'
        begin += store32(FORCED, load32(DEFERRED)) + args + orig(9291) + set_(4) + store32(FORCED, get(5))
        begin += get(4) + b'\x04\x40' + get(7) + i32(15) + b'\x47\x04\x40'
        begin += emit_(get(7) + i32(16) + b'\x72') + i32(1) + gs(stippling) + b'\x0b\x0b' + get(4)
        code[9291] = body([(4, 0x7f)], begin)
        code[9295] = body([], orig(9295) + gg(stippling) + b'\x04\x40' + i32(0) + gs(stippling) + emit_(i32(0)) + b'\x0b')
        code[64694] = body([], get(0) + gs(alpha) + get(1) + gs(invert) + get(0) + get(1) + orig(64694))
        code[43886] = body([], i32(255) + gs(alpha) + i32(0) + gs(invert) + orig(43886))
    # Private stack payload, restored after synchronous ring-copy Emit.
    emitter = body([(2, 0x7e)], call(deps['stack_current']) + set_(1) + i64(16) + call(deps['stack_alloc']) + set_(2) + get(2) + get(0) + b'\x36\x02\x00' + i32(65) + get(2) + i32(1) + call(deps['gpu_emit']) + get(1) + call(deps['stack_restore']))
    return code, emitter


def inspect(data):
    digest = hashlib.sha256(data).hexdigest()
    if digest not in (PINS['offline_sha256'], PINS['online_sha256']):
        raise ValueError('Unreviewed render hook input engine')
    types, indices, names = b.gate.module_abi(data)
    parts = list(b.gate.sections(data)); sections = dict(parts)
    r = b.gate.Reader(sections[3]); functions = [r.uint() for _ in range(r.count())]; r.finish()
    imported = len(indices) - len(functions)
    r = b.gate.Reader(sections[10]); bodies = [r.take(r.uint()) for _ in range(r.count())]; r.finish()
    for row in PINS['functions']:
        index = row['index']
        if names.get(row['name']) != [index] or types[indices[index]] != (row['params'], row['results']):
            raise ValueError('Render hook name/index/type changed: ' + row['name'])
        want = row['online_body_sha256'] if digest == PINS['online_sha256'] else row['body_sha256']
        if hashlib.sha256(bodies[index - imported]).hexdigest() != want:
            raise ValueError('Render hook original body changed: ' + row['name'])
    return parts, types, indices, functions, imported, bodies


def append(data, legacy98=False, legacy103=False, legacy104=False):
    parts, types, indices, functions, imported, bodies = inspect(data)
    sections = dict(parts)
    # This engine imports only memory/table/functions; globals are defined here.
    r = b.gate.Reader(sections[2])
    for _ in range(r.count()):
        r.text(); r.text(); kind = r.byte()
        if kind == 0: r.uint()
        elif kind == 1: b.gate.valtype(r); b.gate.limits(r)
        elif kind == 2: b.gate.limits(r)
        else: raise ValueError('Unexpected imported global/tag in render engine')
    r.finish()
    r = b.gate.Reader(sections[6]); ng = r.count(); old_globals = r.take(len(sections[6]) - r.pos)
    originals = {index: len(indices) + j for j, index in enumerate(HOOKS)}
    emitter_index = len(indices) + len(HOOKS)
    initial_globals = (0, 255, 0) if legacy98 else (0, 255, 0, 0)
    global_indices = tuple(ng + j for j in range(len(initial_globals)))
    code, emitter = wrappers(originals, global_indices, emitter_index, legacy98=legacy98, legacy103=legacy103, legacy104=legacy104)
    if not (legacy98 or legacy103 or legacy104):
        clear = op(0x23, global_indices[2]) + b'\x04\x40' + i32(0) + op(0x24, global_indices[2]) + i32(0) + op(0x10, emitter_index) + b'\x0b'
        for row in LIFETIME_PINS:
            index = row['index']
            original = bodies[index - imported]
            key = 'online_body_sha256' if hashlib.sha256(data).hexdigest() == PINS['online_sha256'] else 'body_sha256'
            if hashlib.sha256(original).hexdigest() != row[key]:
                raise ValueError('Inlined EndDraw body changed: ' + str(index))
            bodies[index - imported] = patch_inline_wasm(original, clear)
    originals_bodies = [bodies[index - imported] for index in HOOKS]
    for index in HOOKS: bodies[index - imported] = code[index]
    bodies.extend(originals_bodies + [emitter])
    emitter_type = types.index((['i32'], []))
    functions.extend([indices[index] for index in HOOKS] + [emitter_type])
    out = bytearray(data[:8])
    for kind, raw in parts:
        if kind == 3: raw = b.leb(len(functions)) + b''.join(b.leb(t) for t in functions)
        elif kind == 6: raw = b.leb(ng + len(initial_globals)) + old_globals + b''.join(b'\x7f\x01' + i32(v) + b'\x0b' for v in initial_globals)
        elif kind == 10: raw = b.leb(len(bodies)) + b''.join(b.leb(len(v)) + v for v in bodies)
        out.extend(b.section(kind, raw))
    out.extend(b.section(0, b.string(MARKER.decode())))
    out = bytes(out)
    nt, ni, _ = b.gate.module_abi(out)
    if nt != types or ni[:len(indices)] != indices:
        raise ValueError('Render hook append moved an existing ABI index')
    return out, dict(format='zgta-render-hooks98-v1' if legacy98 else 'zgta-render-hooks103-v1' if legacy103 else 'zgta-render-hooks104-v1' if legacy104 else 'zgta-render-hooks106-v1', input_sha256=hashlib.sha256(data).hexdigest(),
                     output_sha256=hashlib.sha256(out).hexdigest(), hooks=list(HOOKS), inline_end_hooks=[] if legacy98 or legacy103 or legacy104 else [r['index'] for r in LIFETIME_PINS],
                     original_indices_preserved=True, added_imports=0, stipple_opcode=65,
                     runtime_verified=False)


def append_legacy98(data):
    """Reproduce a frozen Build98–102 artifact; not a new runtime producer."""
    return append(data, legacy98=True)


def append_legacy103(data):
    """Reproduce the frozen Build103 artifact, including its stale shadow state."""
    return append(data, legacy103=True)


def append_legacy104(data):
    """Reproduce exact Build104/105 engine bytes without lifecycle correction."""
    return append(data, legacy104=True)


def native_function(text, index):
    found = list(re.finditer(r'(?ms)^(?:void|u32|u64) w2c_game_f' + str(index) + r'\([^\n]*\) \{\n.*?^\}', text))
    if len(found) != 1: raise ValueError('Missing/duplicate native render hook ' + str(index))
    return found[0]


NATIVE_HEADER = '''/* Glue5-compatible far-light hints and per-draw fade state. */
extern _Thread_local u32 pg98_rendering_lod, pg98_stipple_alpha, pg98_stippling, pg103_stipple_invert;
static inline u32 pg98_load32(w2c_game* i,u64 a){return i32_load_shared(NULL,0,i->w2c_env_memory,a);}
static inline void pg98_store32(w2c_game* i,u64 a,u32 v){i32_store_shared(NULL,0,i->w2c_env_memory,a,v);}
static inline void pg98_stipple(w2c_game* i,u32 level){
  u64 top=w2c_game_emscripten_stack_get_current(i),at=w2c_game_0x5Femscripten_stack_alloc(i,16);
  pg98_store32(i,at,level); w2c_game_f550(i,65,at,1); w2c_game_0x5Femscripten_stack_restore(i,top);
}
'''
NATIVE_STATE = '_Thread_local u32 pg98_rendering_lod=0, pg98_stipple_alpha=255, pg98_stippling=0, pg103_stipple_invert=0;\n'
NATIVE_BODIES = {
44583: '''void w2c_game_f44583(w2c_game* instance) {
  u32 previous=pg98_rendering_lod;pg98_rendering_lod=1;
  pg98_original_44583(instance);pg98_rendering_lod=previous;
}''',
9952: '''void w2c_game_f9952(w2c_game* instance, u64 var_p0) {
  if(pg98_rendering_lod){
    u64 resource=i64_load_shared(NULL,0,instance->w2c_env_memory,var_p0+80);
    u32 offset=pg98_load32(instance,var_p0+96),size=pg98_load32(instance,var_p0+100);
    if(resource && size>(128u<<10))w2c_game_f244(instance,resource,offset,size);
  }
  pg98_original_9952(instance,var_p0);
}''',
9291: '''u32 w2c_game_f9291(w2c_game* instance, u64 var_p0, u32 var_p1, u32 var_p2, u32 var_p3) {
  u32 passes=pg98_original_9291(instance,var_p0,var_p1,var_p2,var_p3);
  if(passes || var_p3)return passes;
  u32 forced=pg98_load32(instance,6634168);
  if((int32_t)forced<0 || (forced!=pg98_load32(instance,7248300) && forced!=pg98_load32(instance,7248304) && forced!=pg98_load32(instance,7248320)))return passes;
  u32 a=pg98_stipple_alpha>255?255:pg98_stipple_alpha;
  u32 raw=i32_load16_u_shared(NULL,0,instance->w2c_env_memory,7344304ull+((u64)(a>>3)*2));
  raw=(raw^(0u-pg103_stipple_invert))&65535u;
  u32 mask=0;
  for(u32 phase=0;phase<4;phase++)if(((raw>>(phase*4))&15u)==15u)mask|=1u<<phase;
  if(!mask)return passes;
  pg98_store32(instance,6634168,pg98_load32(instance,21490232));
  passes=pg98_original_9291(instance,var_p0,var_p1,var_p2,var_p3);
  pg98_store32(instance,6634168,forced);
  if(passes && mask!=15){pg98_stipple(instance,16u|mask);pg98_stippling=1;}
  return passes;
}''',
9295: '''void w2c_game_f9295(w2c_game* instance) {
  pg98_original_9295(instance);
  if(pg98_stippling){pg98_stippling=0;pg98_stipple(instance,0);}
}''',
64694: '''void w2c_game_f64694(w2c_game* instance, u32 var_p0, u32 var_p1) {
  pg98_stipple_alpha=var_p0;pg103_stipple_invert=var_p1;pg98_original_64694(instance,var_p0,var_p1);
}''',
43886: '''void w2c_game_f43886(w2c_game* instance) {
  pg98_stipple_alpha=255;pg103_stipple_invert=0;pg98_original_43886(instance);
}'''}



# Exact Build98–102 wrapper bytes are retained solely for authenticated reversal
# when a verified reusable native stage is cloned for Build103. Unknown or mixed
# additions are rejected; original function pins and whole-file gates still apply.
LEGACY_HEADER = NATIVE_HEADER.replace(', pg103_stipple_invert;', ';')
LEGACY_STATE = '_Thread_local u32 pg98_rendering_lod=0, pg98_stipple_alpha=255, pg98_stippling=0;\n'
LEGACY_BODIES = dict(NATIVE_BODIES)
LEGACY_BODIES[9291] = '''u32 w2c_game_f9291(w2c_game* instance, u64 var_p0, u32 var_p1, u32 var_p2, u32 var_p3) {
  u32 passes=pg98_original_9291(instance,var_p0,var_p1,var_p2,var_p3);
  if(passes || var_p3)return passes;
  u32 forced=pg98_load32(instance,6634168);
  if((int32_t)forced<0 || (forced!=pg98_load32(instance,7248300) && forced!=pg98_load32(instance,7248304) && forced!=pg98_load32(instance,7248320)))return passes;
  pg98_store32(instance,6634168,pg98_load32(instance,21490232));
  passes=pg98_original_9291(instance,var_p0,var_p1,var_p2,var_p3);
  pg98_store32(instance,6634168,forced);
  if(passes){
    u32 a=pg98_stipple_alpha>255?255:pg98_stipple_alpha,level=(a*16+127)/255;
    if(level<16){pg98_stipple(instance,level?level:1);pg98_stippling=1;}
  }
  return passes;
}'''
LEGACY_BODIES[64694] = '''void w2c_game_f64694(w2c_game* instance, u32 var_p0, u32 var_p1) {
  pg98_stipple_alpha=var_p0;pg98_original_64694(instance,var_p0,var_p1);
}'''
LEGACY_BODIES[43886] = '''void w2c_game_f43886(w2c_game* instance) {
  pg98_stipple_alpha=255;pg98_original_43886(instance);
}'''

# Exact Build103 adapters remain reversible; their shader predicate was correct
# but the cached setter arguments missed original GlobalFade reset paths.
BUILD103_HEADER = NATIVE_HEADER
BUILD103_STATE = NATIVE_STATE
BUILD103_BODIES = dict(NATIVE_BODIES)
NATIVE_HEADER = NATIVE_HEADER.replace('per-draw fade state.', 'authoritative per-draw fade state (Build104).')
_old_mask = '''  u32 a=pg98_stipple_alpha>255?255:pg98_stipple_alpha;
  u32 raw=i32_load16_u_shared(NULL,0,instance->w2c_env_memory,7344304ull+((u64)(a>>3)*2));
  raw=(raw^(0u-pg103_stipple_invert))&65535u;'''
_current_mask = '''  u32 raw;
  if(pg98_load32(instance,12623176)>pg98_load32(instance,7344224)){
    u64 samples=i64_load_shared(NULL,0,instance->w2c_env_memory,12433376);
    if(samples==UINT64_MAX)raw=65535u;
    else if(!samples)raw=0;
    else{
      u32 a=pg98_stipple_alpha>255?255:pg98_stipple_alpha;
      raw=i32_load16_u_shared(NULL,0,instance->w2c_env_memory,7344304ull+((u64)(a>>3)*2));
      raw=(raw^(0u-pg103_stipple_invert))&65535u;
    }
  }else raw=i32_load16_u_shared(NULL,0,instance->w2c_env_memory,23984584);'''
assert NATIVE_BODIES[9291].count(_old_mask) == 1
NATIVE_BODIES[9291] = NATIVE_BODIES[9291].replace(_old_mask, _current_mask)


# Build104/105 remain reproducible, including their incomplete cleanup lifetime.
BUILD104_HEADER = NATIVE_HEADER
BUILD104_STATE = NATIVE_STATE
BUILD104_BODIES = dict(NATIVE_BODIES)
NATIVE_HEADER = NATIVE_HEADER.replace('(Build104)', '(Build106 draw lifetime)')
NATIVE_CLEAR = '  if(pg98_stippling){pg98_stippling=0;pg98_stipple(instance,0);}'
NATIVE_BODIES[9291] = NATIVE_BODIES[9291].replace(
    '  u32 passes=pg98_original_9291', NATIVE_CLEAR + '\n  u32 passes=pg98_original_9291', 1)
LIFETIME_PINS = json.loads((ROOT / 'render-lifetime-pins106.json').read_text())['functions']


def patch_inline_wasm(raw, clear):
    # Exact original body pins are checked by the caller. Require one complete
    # original EndDraw reset instruction sequence, never a guessed byte offset.
    needle = i64(12432408) + i64(0) + b'\x37\x03\x00'
    if raw.count(needle) != 1:
        raise ValueError('Expected one inlined EndDraw effect reset')
    return raw.replace(needle, needle + clear, 1)


def _inline_native(text, filename, reverse=False):
    for row in LIFETIME_PINS:
        if row['file'] != filename:
            continue
        match = native_function(text, row['index'])
        value = match[0]
        needle = row['native_reset']
        if reverse:
            if value.count(needle + '\n' + NATIVE_CLEAR) != 1:
                raise ValueError('Inlined EndDraw cleanup differs: ' + str(row['index']))
            value = value.replace(needle + '\n' + NATIVE_CLEAR, needle, 1)
        if hashlib.sha256(value.encode()).hexdigest() != row['native_sha256']:
            raise ValueError('Inlined EndDraw native body changed: ' + str(row['index']))
        if not reverse:
            if value.count(needle) != 1:
                raise ValueError('Expected one inlined native EndDraw reset')
            value = value.replace(needle, needle + '\n' + NATIVE_CLEAR, 1)
        text = text[:match.start()] + value + text[match.end():]
    return text


def native_files(lifetime=True):
    result = {r['file'] for r in PINS['native'] if r['index'] in HOOKS}
    if lifetime: result.update(r['file'] for r in LIFETIME_PINS)
    return sorted(result)


def transform_native(text, rows, filename=None):
    return _transform_native(text, rows, NATIVE_STATE, NATIVE_BODIES, lifetime=True, filename=filename)


def _transform_native(text, rows, state, bodies, lifetime=False, filename=None):
    if lifetime:
        if filename is None:
            files = {r['file'] for r in rows}
            if len(files) != 1: raise ValueError('Explicit native part name required')
            filename = files.pop()
        text = _inline_native(text, filename)
    # The generated implementation headers intentionally have no include guard.
    # Insert after them, before functions, without including them a second time.
    first = re.search(r'(?m)^(?:void|u32|u64|f32|f64) w2c_game_f\d+\(', text)
    if not first: raise ValueError('Native generated implementation layout changed')
    prefix = '#include "game-render-hooks98.h"\n'
    if any(row['index'] == 9291 for row in rows): prefix += state
    text = text[:first.start()] + prefix + text[first.start():]
    for row in rows:
        index = row['index']
        if index not in HOOKS: continue
        match = native_function(text, index)
        if hashlib.sha256(match[0].encode()).hexdigest() != row['sha256']:
            raise ValueError('Native render original changed: ' + str(index))
        original = 'static ' + match[0].replace('w2c_game_f' + str(index) + '(', 'pg98_original_' + str(index) + '(', 1)
        text = text[:match.start()] + original + '\n\n' + bodies[index] + text[match.end():]
    return text


def stage_native(generated):
    generated = Path(generated)
    header = generated / 'game-render-hooks98.h'
    previous = None
    if header.exists():
        current = header.read_text()
        if current == NATIVE_HEADER:
            verify_native(generated)
            return
        if current == LEGACY_HEADER:
            previous = (LEGACY_STATE, LEGACY_BODIES, False)
        elif current == BUILD104_HEADER:
            previous = (BUILD104_STATE, BUILD104_BODIES, False)
        elif current == BUILD103_HEADER:
            previous = (BUILD103_STATE, BUILD103_BODIES, False)
        else:
            raise ValueError('Unrecognized existing native render header')
    staged = {}
    for filename in native_files():
        rows = [row for row in PINS['native'] if row['file'] == filename and row['index'] in HOOKS]
        original = (generated / filename).read_bytes()
        if previous is not None:
            if filename in native_files(False):
                original = _undo_native_part(original, filename, *previous)
        text = transform_native(original.decode(), rows, filename)
        # Validate every new output before the first filesystem mutation.
        if _undo_native_part(text.encode(), filename, NATIVE_STATE, NATIVE_BODIES, True) != original:
            raise ValueError('Native render migration changed original bytes')
        staged[filename] = text
    for filename, text in staged.items():
        (generated / filename).write_text(text)
    header.write_text(NATIVE_HEADER)
    verify_native(generated)


def verify_native(generated):
    generated = Path(generated)
    if (generated / 'game-render-hooks98.h').read_text() != NATIVE_HEADER:
        raise ValueError('Native render header differs')
    for filename in native_files():
        _undo_native_part((generated / filename).read_bytes(), filename, NATIVE_STATE, NATIVE_BODIES, True)


def undo_native_part(data, filename):
    """Validate/remove only our exact additions for older whole-part verifiers.

    Their original before/after digests remain authoritative. Reversal never
    sanitizes unrelated edits: those bytes survive and fail the older digest.
    No receipt or expected hash is rewritten to accept composed changes.
    """
    errors = []
    for state, bodies, lifetime in ((NATIVE_STATE, NATIVE_BODIES, True),
                          (BUILD104_STATE, BUILD104_BODIES, False),
                          (BUILD103_STATE, BUILD103_BODIES, False),
                          (LEGACY_STATE, LEGACY_BODIES, False)):
        try:
            return _undo_native_part(data, filename, state, bodies, lifetime)
        except ValueError as error:
            errors.append(str(error))
    raise ValueError('No exact reviewed native render variant: ' + '; '.join(errors))


def _undo_native_part(data, filename, state, bodies, lifetime=False):
    rows = [row for row in PINS['native'] if row['file'] == filename and row['index'] in HOOKS]
    text = data.decode('utf-8')
    if not rows and not (lifetime and any(r['file'] == filename for r in LIFETIME_PINS)):
        if 'pg98_' in text or 'pg103_' in text or 'game-render-hooks98.h' in text:
            raise ValueError('Render additions in an unreviewed native part')
        return data
    original_text = text
    prefix = '#include "game-render-hooks98.h"\n'
    if any(row['index'] == 9291 for row in rows): prefix += state
    if text.count(prefix) != 1 or text.count('#include "game-render-hooks98.h"') != 1:
        raise ValueError('Native render injected include/state differs')
    text = text.replace(prefix, '', 1)
    for row in rows:
        index = row['index']
        if native_function(text, index)[0] != bodies[index]:
            raise ValueError('Native render wrapper differs')
        matches = list(re.finditer(r'(?ms)^static (?:void|u32|u64) pg98_original_' + str(index) + r'\([^\n]*\) \{\n.*?^\}', text))
        if len(matches) != 1: raise ValueError('Native render original absent/duplicated')
        m = matches[0]
        original = m[0][7:].replace('pg98_original_' + str(index) + '(', 'w2c_game_f' + str(index) + '(', 1)
        if hashlib.sha256(original.encode()).hexdigest() != row['sha256']:
            raise ValueError('Native render original differs')
        pair = m[0] + '\n\n' + bodies[index]
        if text.count(pair) != 1: raise ValueError('Native render original/wrapper layout differs')
        text = text.replace(pair, original, 1)
    if lifetime: text = _inline_native(text, filename, reverse=True)
    # Exact round trip also fixes the insertion point and rejects duplicate or
    # orphan state/macros while preserving unrelated source bytes for hashing.
    if _transform_native(text, rows, state, bodies, lifetime, filename) != original_text:
        raise ValueError('Native render additions do not round-trip exactly')
    if 'pg98_' in text or 'pg103_' in text or 'game-render-hooks98.h' in text:
        raise ValueError('Unexpected native render additions remain')
    return text.encode('utf-8')
