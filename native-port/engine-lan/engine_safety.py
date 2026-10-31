"""Pinned engine guards shared by native C and browser WASM.

Append pure WASM helpers: no new imports, host crossings, worker, or per-frame
allocation. Original indices and every unselected body remain unchanged.
"""
import hashlib
import json
from pathlib import Path
import re
import struct
import browser_wasm as b

ROOT = Path(__file__).resolve().parent
PINS = json.loads((ROOT / 'engine-safety-pins.json').read_text())
SELECTED = (2861, 5273, 6968, 9695, 28266, 29099, 44489, 47953, 65693)
ROWS = {row['index']: row for row in PINS['functions']}
HELPER_NAMES = ('range', 'deleted_entity', 'draw_budget', 'drop_destroyed_phases', 'stale_job', 'frame_idle_ns', 'frame_idle_wait', 'audio_idle_ns', 'audio_idle_wait', 'render_notify', 'visibility_poll')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def get(n):
    return b'\x20' + b.leb(n)

def put(n):
    return b'\x21' + b.leb(n)

def i32(n):
    return b'\x41' + b.sleb(n)

def i64(n):
    return b'\x42' + b.sleb(n)

def call(n):
    return b'\x10' + b.leb(n)

def f32(n):
    return b'\x43'+struct.pack('<f',n)

def f64(n):
    return b'\x44'+struct.pack('<d',n)

def returning(value):
    return b'\x04\x40' + i32(value) + b'\x0f\x0b'

def locals_end(groups, code):
    return b.leb(len(groups)) + b''.join(b.leb(count) + bytes([kind]) for count, kind in groups) + code + b'\x0b'

def helpers(first, memory64=True, table64=True, job_type=4, job_resolution=None):
    """Emit the same bounded predicates as NativeEngineSafety.h."""
    range_fn = first
    def load(pointer, kind, offset=0):
        opcode, align = {'u64': (0x29, 3), 'u32': (0x28, 2), 'u16': (0x2f, 1), 'u8': (0x2d, 0)}[kind]
        return pointer + (b'' if memory64 else b'\xa7') + bytes([opcode, align]) + b.leb(offset)
    def store(pointer, value, opcode, align, offset=0):
        return pointer + (b'' if memory64 else b'\xa7') + value + bytes([opcode, align]) + b.leb(offset)
    def valid(pointer, count):
        return pointer + count + call(range_fn)
    memory_size = b'\x3f\x00' + (b'' if memory64 else b'\xad') + i64(16) + b'\x86'
    range_code = (get(0) + b'\x50' + returning(0) +
                  memory_size + put(2) + get(1) + get(2) + b'\x56' + returning(0) +
                  get(0) + get(2) + get(1) + b'\x7d\x58')
    deleted = (valid(get(0), i64(80)) + b'\x45' + returning(0) +
               load(get(0), 'u64', 8) + i64(-2459565876494606883) + b'\x51' +
               load(get(0), 'u64', 72) + i64(-2459565876494606883) + b'\x51\x71')
    budget = (valid(get(0), i64(41)) + b'\x45' + returning(0) +
              load(get(0), 'u8', 40) + put(1) +
              get(1) + i32(3) + b'\x47' + get(1) + i32(4) + b'\x47\x71' + returning(0) +
              valid(i64(11012104), i64(8)) + valid(i64(11012152), i64(8)) + b'\x71\x45' + returning(0) +
              load(i64(11012104), 'u64') + put(2) + valid(get(2), i64(16908)) + b'\x04\x40' +
              load(get(2), 'u16', 16906) + put(3) + get(3) + b'\x04\x40' +
              load(get(2), 'u16', 16904) + i32(8) + b'\x6a' + get(3) + b'\x4f' + returning(1) + b'\x0b\x0b' +
              load(i64(11012152), 'u64') + put(2) + valid(get(2), i64(83812)) + b'\x45' + returning(0) +
              load(get(2), 'u32', 83808) + i32(480) + b'\x4f')
    # locals: list/data/phase (i64); count/kept/index (i32).
    cell = lambda index: get(1) + get(index) + b'\xad' + i64(8) + b'\x7e\x7c'
    phases = (valid(i64(11547128), i64(8)) + b'\x45' + b'\x04\x40\x0f\x0b' +
              load(i64(11547128), 'u64') + put(0) + valid(get(0), i64(10)) + b'\x45\x04\x40\x0f\x0b' +
              load(get(0), 'u64') + put(1) + load(get(0), 'u16', 8) + put(3) +
              valid(get(1), get(3) + b'\xad' + i64(8) + b'\x7e') + b'\x45\x04\x40\x0f\x0b' +
              b'\x02\x40\x03\x40' + get(5) + get(3) + b'\x4f\x0d\x01' +
              load(cell(5), 'u64') + put(2) +
              valid(get(2), i64(8)) + b'\x04\x7f' + load(get(2), 'u64') + i64(4219920) + b'\x51\x05' + i32(0) + b'\x0b' +
              b'\x04\x40\x05' + store(cell(4), get(2), 0x37, 3) + get(4) + i32(1) + b'\x6a' + put(4) + b'\x0b' +
              get(5) + i32(1) + b'\x6a' + put(5) + b'\x0c\x00\x0b\x0b' +
              get(4) + get(3) + b'\x47\x04\x40' + store(get(0), get(4), 0x3b, 1, 8) + b'\x0b')
    table_size = b'\xfc\x10\x00' + (b'' if table64 else b'\xad')
    remap=b''.join(get(1)+i64(int(raw))+b'\x51\x04\x40'+i64(target)+put(1)+b'\x0b'
                  for raw,target in (job_resolution or {}).items())
    stale_job = (valid(get(0), i64(147)) + b'\x45' + returning(1) +
                 load(get(0), 'u64', 96) + put(1) + get(1) + table_size + b'\x5a' + returning(1) +
                 remap+get(1)+table_size+b'\x5a'+returning(1) +
                 get(1) + (b'' if table64 else b'\xa7') +
                 b'\x25\x00\xfb\x14' + b.sleb(job_type) + b'\x45' + returning(1) +
                 load(get(0), 'u8', 110) + i32(1) + b'\x71\x04\x7f' +
                 load(get(0), 'u32', 112) + i32(268435456) + b'\x4b\x05' + i32(0) + b'\x0b')
    frame_ns=(get(0)+f32(0.00005)+b'\x5e'+get(0)+f32(1.0)+b'\x5d\x71\x45\x04\x40'+i64(0)+b'\x0f\x0b'+
              get(0)+b'\xbb'+f64(500000000.0)+b'\xa2'+f64(1000000.0)+b'\xa4\xb1')
    frame_address=i64(25038496)+(b'' if memory64 else b'\xa7')
    frame_wait=(get(0)+call(first+5)+put(1)+get(1)+b'\x50\x04\x40\x0f\x0b'+
                valid(i64(25038496),i64(4))+b'\x45\x04\x40\x0f\x0b'+frame_address+
                frame_address+b'\xfe\x10\x02\x00'+get(1)+b'\xfe\x01\x02\x00\x1a')
    audio_ns=(get(0)+f32(0.02)+b'\x5e'+get(0)+f32(15.0)+b'\x5f\x71\x45\x04\x40'+i64(0)+b'\x0f\x0b'+
              get(0)+b'\xbb'+f64(0.02)+b'\xa1'+f64(1000000.0)+b'\xa2\xb1')
    audio_address=i64(6638636)+(b'' if memory64 else b'\xa7')
    audio_wait=(get(0)+call(first+7)+put(1)+get(1)+b'\x50'+returning(0)+
                valid(i64(6638636),i64(4))+valid(i64(12046712),i64(4))+b'\x71\x45'+returning(0)+
                audio_address+load(i64(12046712),'u32')+get(1)+b'\xfe\x01\x02\x00\x1a'+i32(1))
    render_notify=(valid(i64(6638636),i64(4))+b'\x45\x04\x40\x0f\x0b'+
                   audio_address+i32(-1)+b'\xfe\x00\x02\x00\x1a')
    event_address=get(0)+(b'' if memory64 else b'\xa7')
    waiter_address=get(0)+i64(4)+b'\x7c'+(b'' if memory64 else b'\xa7')
    # Exact original PollEvent operation for every out-of-scope event. Only
    # the BuildRenderLists call site is redirected to this helper.
    original_poll=event_address+i32(0)+b'\xfe\x41\x02\x00'+i32(1)+b'\x46'
    fallback=lambda condition:condition+b'\x04\x40'+original_poll+b'\x0f\x0b'
    take_event=event_address+i32(1)+i32(0)+b'\xfe\x48\x02\x00'
    visibility_poll=(
        fallback(valid(i64(11497192),i64(8))+b'\x45')+
        fallback(valid(get(0),i64(8))+b'\x45')+
        fallback(get(0)+i64(3)+b'\x83'+i64(0)+b'\x52')+
        fallback(load(i64(11497192),'u64')+get(0)+b'\x52')+
        fallback(event_address+b'\xfe\x10\x02\x00'+i32(1)+b'\x4b')+
        waiter_address+i32(1)+b'\xfe\x1e\x02\x00\x1a'+
        take_event+i32(1)+b'\x47\x04\x40'+
        event_address+i32(0)+i64(1000000)+b'\xfe\x01\x02\x00\x1a'+take_event+b'\x1a\x0b'+
        waiter_address+i32(1)+b'\xfe\x25\x02\x00\x1a'+i32(1))
    return [
        ((['i64', 'i64'], ['i32']), locals_end([(1, 0x7e)], range_code)),
        ((['i64'], ['i32']), locals_end([], deleted)),
        ((['i64'], ['i32']), locals_end([(1, 0x7f), (1, 0x7e), (1, 0x7f)], budget)),
        (([], []), locals_end([(3, 0x7e), (3, 0x7f)], phases)),
        ((['i64'], ['i32']), locals_end([(1,0x7e)], stale_job)),
        ((['f32'], ['i64']), locals_end([],frame_ns)),
        ((['f32'], []), locals_end([(1,0x7e)],frame_wait)),
        ((['f32'], ['i64']), locals_end([],audio_ns)),
        ((['f32'], ['i32']), locals_end([(1,0x7e)],audio_wait)),
        (([], []), locals_end([],render_notify)),
        ((['i64'], ['i32']), locals_end([],visibility_poll)),
    ]

def insert_start(body, extra):
    reader = b.gate.Reader(body)
    for _ in range(reader.count()):
        reader.uint(); reader.byte()
    return body[:reader.pos] + extra + body[reader.pos:]

def once(data, old, new):
    if data.count(old) != 1:
        raise ValueError('Exact engine guard anchor changed')
    return data.replace(old, new, 1)

def restore_code():
    """Wait after the reset lock and before the context lock, only if pending."""
    return (i64(8323016) + b'\x2d\x00\x00' + i32(1) + b'\x46\x04\x40' +
            i32(0) + call(5315) + b'\x0b')

def transform(data):
    digest = sha(data)
    allowed = {PINS['engine_sha256'], *PINS['browser_inputs'].values()}
    if digest not in allowed:
        raise ValueError('Unreviewed safety input engine')
    derived = digest == PINS['browser_inputs']['game.engine-lan.wasm']
    types, indices, names = b.gate.module_abi(data)
    parts = list(b.gate.sections(data)); sections = dict(parts)
    reader = b.gate.Reader(sections[3]); functions = [reader.uint() for _ in range(reader.count())]; reader.finish()
    imported = len(indices) - len(functions)
    reader = b.gate.Reader(sections[10]); bodies = [reader.take(reader.uint()) for _ in range(reader.count())]; reader.finish()
    for index in (*SELECTED, 126, 127, 5315, 9997, 10000):
        row = ROWS[index]
        expected = row['lan_body_sha256'] if derived else row['wasm_body_sha256']
        if names.get(row['name']) != [index] or types[indices[index]] != (row['params'], row['results']) or sha(bodies[index-imported]) != expected:
            raise ValueError('Engine safety ABI/body changed: ' + str(index))
    first = len(indices)
    if types[4] != (['i64'], ['i32']):
        raise ValueError('Dependency job function type changed')
    # Existing entities and jobs keep the engine's normal path. Only known
    # poisoned entries, exhausted skeleton budgets and stale phases are skipped.
    body = bodies[5273-imported]
    body = once(body, b'\x22\x18\x29\x03\x48',
                put(24) + get(24) + call(first+1) + b'\x0d\x00' + get(24) + b'\x29\x03\x48')
    bodies[5273-imported] = body
    bodies[44489-imported] = insert_start(bodies[44489-imported], get(0) + call(first+2) + returning(1))
    bodies[47953-imported] = insert_start(bodies[47953-imported], call(first+3))
    bodies[2861-imported] = once(bodies[2861-imported], b'\x20\x01\x2d\x00\x92\x01',
        get(1) + call(first+4) + b'\x04\x40' + i64(0) + put(1) + b'\x0c\x01\x0b' + b'\x20\x01\x2d\x00\x92\x01')
    bodies[29099-imported] = once(bodies[29099-imported], call(10000) + call(9997) + i64(0) + i64(599092),
                                call(10000) + restore_code() + call(9997) + i64(0) + i64(599092))
    idle_anchor=i64(7377528)+b'\x2a\x02\x00'+put(16)+get(18)+put(15)
    bodies[65693-imported]=once(bodies[65693-imported],idle_anchor,
        get(17)+get(19)+b'\x93'+get(18)+b'\x93'+call(first+6)+idle_anchor)
    # Keep the original measured elapsed value; no extra clock call/TLS hook.
    audio=bodies[6968-imported];reader=b.gate.Reader(audio)
    groups=[(reader.uint(),reader.byte()) for _ in range(reader.count())]
    extra_local=1+sum(n for n,_ in groups)
    if extra_local!=48:raise ValueError('Audio local layout changed')
    audio=b.leb(len(groups)+1)+b''.join(b.leb(n)+bytes([t]) for n,t in groups)+b'\x01\x7d'+audio[reader.pos:]
    audio=once(audio,get(25)+call(2868)+get(30)+b'\x5e\x0d\x01',
               get(25)+call(2868)+b'\x22'+b.leb(extra_local)+get(30)+b'\x5e\x0d\x01')
    anchor=i32(1)+call(135)+i64(6638636)+b'\x28\x02\x00'
    audio=once(audio,anchor,get(30)+get(extra_local)+b'\x93'+call(first+8)+b'\x45\x04\x40'+i32(1)+call(135)+b'\x0b'+i64(6638636)+b'\x28\x02\x00')
    bodies[6968-imported]=audio
    anchor=i64(6638636)+i64(6638636)+b'\x28\x02\x00'+i32(1)+b'\x6a\x36\x02\x00'
    bodies[9695-imported]=once(bodies[9695-imported],anchor,anchor+call(first+9))
    bodies[28266-imported]=once(bodies[28266-imported],call(126),call(first+10))
    additions = helpers(first,job_resolution=PINS['lan_job_resolution'] if derived else None)
    new_types = list(types)
    for signature, body in additions:
        if signature not in new_types: new_types.append(signature)
        functions.append(new_types.index(signature)); bodies.append(body)
    reader = b.gate.Reader(sections[7]); export_count = reader.count(); exports = reader.take(len(sections[7])-reader.pos)
    extra_exports = b''.join(b.string('zema:safety:' + name) + b'\x00' + b.leb(first+n) for n, name in enumerate(HELPER_NAMES))
    inverse = {value: key for key, value in b.gate.TYPES.items()}
    added_types = b''.join(b'\x60' + b.leb(len(p)) + bytes(inverse[v] for v in p) + b.leb(len(r)) + bytes(inverse[v] for v in r) for p, r in new_types[len(types):])
    output = bytearray(data[:8])
    for kind, raw in parts:
        if kind == 1: raw = b.leb(len(new_types)) + sections[1][len(b.leb(len(types))):] + added_types
        elif kind == 3: raw = b.leb(len(functions)) + b''.join(b.leb(v) for v in functions)
        elif kind == 7: raw = b.leb(export_count+len(additions)) + exports + extra_exports
        elif kind == 10: raw = b.leb(len(bodies)) + b''.join(b.leb(len(v))+v for v in bodies)
        output.extend(b.section(kind, raw))
    output = bytes(output)
    checked_types, checked_indices, _ = b.gate.module_abi(output)
    if checked_types[:len(types)] != types or checked_indices[:len(indices)] != indices:
        raise ValueError('Safety patch moved original engine ABI')
    return output, {'format': 'zgta-engine-safety-v1', 'input_sha256': digest, 'patched_sha256': sha(output),
        'modified_function_indices': list(SELECTED), 'helper_indices': dict(zip(HELPER_NAMES, range(first, first+len(HELPER_NAMES)))),
        'new_imports': 0, 'host_crossings': 0, 'runtime_verified': False,
        'dependency_guard': 'BOUNDS_FUNCTION_TYPE_AND_SCRATCH_LIMIT',
        'live_resize_restriction': 'UNCHANGED'}

def native_edits(index):
    memory = 'instance->w2c_env_memory->data, instance->w2c_env_memory->size'
    prologue = '  (void)wasm_rt_local_memory_size;\n'
    if index == 5273:
        old = ('    var_l24 = var_j0;\n    var_j0 = i64_load_shared(wasm_rt_local_memory_base, wasm_rt_local_memory_size, '
               'instance->w2c_env_memory, (u64)checked_add_u64(var_j0, 72u));\n')
        return old, old.replace('    var_l24 = var_j0;\n', '    var_l24 = var_j0;\n    if (pg_safety_deleted_entity(' + memory + ', var_j0)) goto var_B5;\n', 1)
    if index == 44489:
        return prologue, prologue + '  if (pg_safety_draw_budget(' + memory + ', var_p0)) { FUNC_EPILOGUE; return 1u; }\n'
    if index == 47953:
        return prologue, prologue + '  pg_safety_drop_destroyed_phases(' + memory + ');\n'
    if index == 2861:
        old = '    var_j0 = var_l1;\n    var_i0 = i32_load8_u_shared(wasm_rt_local_memory_base, wasm_rt_local_memory_size, instance->w2c_env_memory, (u64)checked_add_u64(var_j0, 146u));\n'
        table='instance->w2c_0x5F_indirect_function_table'
        guard=('    { int zema_bad = pg_safety_stale_job(' + memory + ', var_l1, '+table+'.size);\n'
               '      if (!zema_bad) { u64 zema_job = ZemaSocialResolve(&'+table+', w2c_game_t4, pg_safety_u64(instance->w2c_env_memory->data, var_l1 + 96));\n'
               '        zema_bad = zema_job >= '+table+'.size || '+table+'.data[zema_job].func_type != w2c_game_t4; }\n'
               '      if (zema_bad) { var_l1 = 0; goto var_L0; }\n    }\n')
        return old,guard+old
    if index == 29099:
        old = '  w2c_game_f10000(instance);\n  w2c_game_f9997(instance);\n  var_j0 = 0ull;\n  var_j1 = 599092ull;\n'
        return old, old.replace('  w2c_game_f9997(instance);', '  if (i32_load8_u_shared(wasm_rt_local_memory_base, wasm_rt_local_memory_size, instance->w2c_env_memory, 8323016ull) == 1u) w2c_game_f5315(instance, 0u);\n  w2c_game_f9997(instance);', 1)
    if index == 65693:
        old=('      var_j0 = 7377528ull;\n      var_f0 = f32_load_shared(wasm_rt_local_memory_base, wasm_rt_local_memory_size, '
             'instance->w2c_env_memory, (u64)(var_j0));\n      var_l16 = var_f0;\n      var_f0 = var_l18;\n')
        return old,'      pg_engine_frame_idle_wait(instance, (var_l17 - var_l19) - var_l18);\n'+old
    if index == 6968:
        old='          var_i0 = 1u;\n          w2c_game_f135(instance, var_i0);\n          var_j0 = 6638636ull;\n'
        return old,'          if (!pg_engine_audio_idle_wait(instance, var_l30 - var_f0)) w2c_game_f135(instance, 1u);\n          var_j0 = 6638636ull;\n'
    if index == 9695:
        old=('  var_j0 = 6638636ull;\n  var_j1 = 6638636ull;\n'
             '  var_i1 = i32_load_shared(wasm_rt_local_memory_base, wasm_rt_local_memory_size, instance->w2c_env_memory, (u64)(var_j1));\n'
             '  var_i2 = 1u;\n  var_i1 += var_i2;\n'
             '  i32_store_shared(wasm_rt_local_memory_base, wasm_rt_local_memory_size, instance->w2c_env_memory, (u64)(var_j0), var_i1);\n')
        return old,old+'  pg_engine_render_notify(instance);\n'
    if index == 28266:
        old='          var_i0 = w2c_game_f126(instance, var_j0);\n'
        return old,'          var_i0 = pg_engine_visibility_poll(instance, var_j0);\n'
    raise ValueError('Unreviewed native safety function')

def native_part(data, indices, undo=False):
    text = data.decode()
    include = '#include "game-engine-safety-impl.h"\n'
    if 28266 in indices: include += '#include "game-visibility-wait-impl.h"\n'
    for index in indices:
        row = ROWS[index]
        pattern = re.compile(r'(?ms)^\w+ w2c_game_f' + str(index) + r'\([^\n]*\) \{\n.*?^\}')
        found = list(pattern.finditer(text))
        if len(found) != 1: raise ValueError('Native safety definition missing/duplicated')
        match = found[0]; body = match[0]
        old, new = native_edits(index)
        original = once(body, new, old) if undo else body
        if sha(original.encode()) != row['c_body_sha256'] or len(original) != row['c_length']:
            raise ValueError('Native safety body differs: ' + str(index))
        body = original if undo else once(original, old, new)
        text = text[:match.start()] + body + text[match.end():]
    return (text.replace(include, '', 1) if undo else include + text).encode()

NATIVE_HEADER = b'''#include "game.h"
#include "ZemaSocial.h"
#include "../Source/NativeEngineSafety.h"
#include "../Source/WasmFutex.h"
#include <stdatomic.h>
static inline void pg_engine_frame_idle_wait(w2c_game *instance, float remaining) {
  uint64_t ns = pg_safety_frame_idle_ns(remaining);
  wasm_rt_shared_memory_t *m = instance->w2c_env_memory;
  if (!ns || !pg_safety_range(m->size, 25038496, 4)) return;
  uint32_t seen = atomic_load_explicit((_Atomic uint32_t *)(m->data + 25038496), memory_order_relaxed);
  (void)pg_atomic_wait32(m, 25038496, seen, ns);
}
static inline int pg_engine_audio_idle_wait(w2c_game *instance, float remaining_ms) {
  uint64_t ns = pg_safety_audio_idle_ns(remaining_ms);
  wasm_rt_shared_memory_t *m = instance->w2c_env_memory;
  if (!ns || !pg_safety_range(m->size, 6638636, 4) || !pg_safety_range(m->size, 12046712, 4)) return 0;
  uint32_t seen = atomic_load_explicit((_Atomic uint32_t *)(m->data + 12046712), memory_order_relaxed);
  (void)pg_atomic_wait32(m, 6638636, seen, ns);
  return 1;
}
static inline void pg_engine_render_notify(w2c_game *instance) {
  wasm_rt_shared_memory_t *m = instance->w2c_env_memory;
  if (pg_safety_range(m->size, 6638636, 4)) (void)pg_atomic_notify(m, 6638636, UINT32_MAX);
}
'''

VISIBILITY_NATIVE_HEADER = b'''#include "game.h"
#include "../Source/NativeEngineSafety.h"
#include "../Source/WasmFutex.h"
#include <stdatomic.h>
uint32_t w2c_game_f126(w2c_game *instance, uint64_t event);
/* Called only in BuildRenderLists, where the caller always rechecks the
 * scan counters after this poll. A timeout therefore skips only its old
 * extra Sleep(1); it never reports that the scan itself has completed. */
static inline uint32_t pg_engine_visibility_poll(w2c_game *instance, uint64_t event) {
  wasm_rt_shared_memory_t *m = instance->w2c_env_memory;
  if (!pg_safety_range(m->size, 11497192, 8) || !pg_safety_range(m->size, event, 8) ||
      (event & 3) || pg_safety_u64(m->data, 11497192) != event) return w2c_game_f126(instance, event);
  _Atomic uint32_t *state = (_Atomic uint32_t *)(m->data + event);
  _Atomic uint32_t *waiters = (_Atomic uint32_t *)(m->data + event + 4);
  if (atomic_load_explicit(state, memory_order_seq_cst) > 1) return w2c_game_f126(instance, event);
  atomic_fetch_add_explicit(waiters, 1, memory_order_seq_cst);
  uint32_t expected = 1;
  if (!atomic_compare_exchange_strong_explicit(state, &expected, 0, memory_order_seq_cst, memory_order_seq_cst)) {
    (void)pg_atomic_wait32(m, event, 0, 1000000);
    expected = 1;
    (void)atomic_compare_exchange_strong_explicit(state, &expected, 0, memory_order_seq_cst, memory_order_seq_cst);
  }
  atomic_fetch_sub_explicit(waiters, 1, memory_order_seq_cst);
  return 1;
}
'''

def verify_native_support(generated):
    for index in (126,127):
        row=ROWS[index];text=(Path(generated)/row['c_part']).read_text()
        matches=list(re.finditer(r'(?ms)^\w+ w2c_game_f'+str(index)+r'\([^\n]*\) \{\n.*?^\}',text))
        if len(matches)!=1 or sha(matches[0][0].encode())!=row['c_body_sha256']:
            raise ValueError('Native visibility event contract changed: '+str(index))

def stage_native(generated):
    generated = Path(generated)
    verify_native_support(generated)
    parts = {}
    for index in SELECTED:
        parts.setdefault(ROWS[index]['c_part'], []).append(index)
    receipt = {'format': 'zgta-native-engine-safety-v1', 'parts': []}
    for part, selected in parts.items():
        path = generated / part; original = path.read_bytes(); patched = native_part(original, selected)
        path.write_bytes(patched)
        receipt['parts'].append({'part': part, 'indices': selected, 'before_sha256': sha(original), 'after_sha256': sha(patched)})
    (generated / 'game-engine-safety-impl.h').write_bytes(NATIVE_HEADER)
    (generated / 'game-visibility-wait-impl.h').write_bytes(VISIBILITY_NATIVE_HEADER)
    (generated / 'engine-safety-plan.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt

def verify_native(generated):
    generated = Path(generated); record = json.loads((generated / 'engine-safety-plan.json').read_text())
    # Later rendering adapters wrap original functions without changing the
    # older safety transform. Validate and reverse just their exact additions
    # before applying the unchanged whole-part before/after digest checks.
    render = None
    if (generated / 'game-render-hooks98.h').exists():
        import render_hooks as render
        render.verify_native(generated)
    verify_native_support(generated)
    groups = {}
    for index in SELECTED: groups.setdefault(ROWS[index]['c_part'], []).append(index)
    if record['format'] != 'zgta-native-engine-safety-v1' or len(record['parts']) != len(groups):
        raise ValueError('Unexpected native safety plan')
    if {row['part'] for row in record['parts']} != set(groups):
        raise ValueError('Missing/duplicate native safety part')
    for row in record['parts']:
        if groups.get(row['part']) != row['indices']: raise ValueError('Native safety scope changed')
        data = (generated / row['part']).read_bytes()
        if render is not None: data = render.undo_native_part(data, row['part'])
        if sha(data) != row['after_sha256'] or sha(native_part(data, row['indices'], undo=True)) != row['before_sha256']:
            raise ValueError('Native safety part changed')
    if (generated / 'game-engine-safety-impl.h').read_bytes() != NATIVE_HEADER:
        raise ValueError('Native safety header changed')
    if (generated / 'game-visibility-wait-impl.h').read_bytes() != VISIBILITY_NATIVE_HEADER:
        raise ValueError('Native visibility wait header changed')
