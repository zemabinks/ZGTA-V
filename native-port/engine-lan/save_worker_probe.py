"""Bounded, forwarding-only probes for the pinned LAN save worker.

No save bytes, credentials, filenames or pointer values are logged. Existing
functions retain their indices and their original bodies as appended exports.
"""
import hashlib
import browser_wasm as b

INPUT = '15bbb51347f2fd655d1702534380382b4014696e60f79a0c5aad0c2d05b4e292'
JOIN_BODY = 'dd8db231c70efaab2b871c7d180c506548d96689cbb903f07bc7471228b2802e'
PINS = [
    ('save_thread_create', 128, 'rage::sysIpcCreateThread(void (*)(void*), void*, unsigned int, rage::sysIpcPriority, char const*, int, char const*)', ['i64','i64','i32','i32','i64','i64'], ['i64'], 'ef86ee7bdb92fb917578b5e559aec4410828085be974d374772395ce37f77e5d'),
    ('save_block_worker', 45253, 'SaveBlockDataThreadFunc(void*)', ['i64'], [], 'ae36154511e984ecee5133607896ac2c0f9a852877bd932e68e36a0a54853077'),
    ('save_builder_buffer', 2326, 'rage::psoBuilder::SaveToBuffer(char*, unsigned long)', ['i64','i64','i64'], ['i32'], '725ce68a4d55ba6f36ec45d91592ab45dc015c2163cc341ba3ae1676dfb039e5'),
]

def append(data):
    if hashlib.sha256(data).hexdigest() != INPUT:
        raise ValueError('Unreviewed LAN engine for save worker diagnostics')
    types, indices, names = b.gate.module_abi(data)
    parts = list(b.gate.sections(data)); sections = dict(parts)
    r = b.gate.Reader(sections[3]); functions = [r.uint() for _ in range(r.count())]; r.finish()
    imported = len(indices) - len(functions)
    r = b.gate.Reader(sections[10]); bodies = [r.take(r.uint()) for _ in range(r.count())]; r.finish()
    if names.get('rage::sysIpcWaitThreadExit(rage::sysIpcThreadId__*)') != [131] or types[indices[131]] != (['i64'],['i32']) or hashlib.sha256(bodies[131-imported]).hexdigest() != JOIN_BODY:
        raise ValueError('Completed-thread join sentinel ABI/body changed')
    r = b.gate.Reader(sections[4])
    if r.count() != 1 or r.byte() != 0x70: raise ValueError('Expected one save worker function table')
    flags, minimum = r.uint(), r.uint(); maximum = r.uint() if flags & 1 else None; r.finish()
    if flags & ~5: raise ValueError('Unexpected save worker table flags')
    r = b.gate.Reader(sections[7]); count = r.count(); old = r.take(len(sections[7])-r.pos)
    hooks, additions = [], []
    for number, (field, index, name, params, results, digest) in enumerate(PINS):
        original = bodies[index-imported]
        if names.get(name) != [index] or types[indices[index]] != (params, results) or hashlib.sha256(original).hexdigest() != digest:
            raise ValueError('Save worker ABI/body changed: '+field)
        alias = 'zema:lan:original:'+field
        slot = minimum+number
        args = b''.join(b'\x20'+b.leb(i) for i in range(len(params)))
        bodies[index-imported] = b'\0'+args+(b'\x42' if flags & 4 else b'\x41')+b.sleb(slot)+b'\x11'+b.leb(indices[index])+b'\0\x0b'
        bodies.append(original); functions.append(indices[index])
        additions.append(b.string(alias)+b'\0'+b.leb(len(indices)+number))
        hooks.append(dict(group='cloud', field=field, index=index, name=name, params=params, results=results, body_sha256=digest, slot=slot, original_export=alias))
    out = bytearray(data[:8])
    for kind, raw in parts:
        if kind == 3: raw = b.leb(len(functions))+b''.join(b.leb(i) for i in functions)
        elif kind == 4: raw = b'\x01\x70'+b.leb(flags)+b.leb(minimum+len(hooks))+(b.leb(maximum+len(hooks)) if maximum is not None else b'')
        elif kind == 7: raw = b.leb(count+len(hooks))+old+b''.join(additions)
        elif kind == 10: raw = b.leb(len(bodies))+b''.join(b.leb(len(v))+v for v in bodies)
        out.extend(b.section(kind, raw))
    output = bytes(out); new_types, new_indices, _ = b.gate.module_abi(output)
    if new_types != types or new_indices != indices+[indices[h['index']] for h in hooks]:
        raise ValueError('Save worker diagnostics moved existing ABI indices')
    return output, hooks
