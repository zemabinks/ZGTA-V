"""Index-preserving browser socket hooks; outputs only into a new Build folder.

Append original-function copies and use typed table trampolines. No imports are
added, no old function index moves, no game/renderer/data file is overwritten.
The game start function is deferred until typed callbacks have been installed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / 'app'
sys.path.insert(0, str(APP / 'Scripts'))
import inspect_engine_lan as gate

# The established feature pipeline consumes the historical 60-hook online
# stage. Append the lifecycle hook afterward so its existing pins and all
# offline output stay unchanged.
FEATURE_LAN_BEFORE_CLOSE = '3f6dfdff90454d3943e73e26c523c0820e57a74f2ae55360bf9f8c48ac90971f'


def append_socket_close(data):
    if hashlib.sha256(data).hexdigest() != FEATURE_LAN_BEFORE_CLOSE:
        raise ValueError('Unreviewed feature LAN engine for socket lifecycle extension')
    contract = json.loads(gate.CONTRACT.read_text())
    hook = next(h for h in contract['hooks'] if h['field'] == 'socket_close')
    types, indices, names = gate.module_abi(data)
    if names.get(hook['name']) != [hook['index']] or types[indices[hook['index']]] != (hook['params'], hook['results']):
        raise ValueError('Socket lifecycle engine ABI changed')
    parts = list(gate.sections(data)); sections = dict(parts)
    r = gate.Reader(sections[3]); functions = [r.uint() for _ in range(r.count())]; r.finish()
    imported = len(indices) - len(functions)
    r = gate.Reader(sections[10]); bodies = [r.take(r.uint()) for _ in range(r.count())]; r.finish()
    original = bodies[hook['index'] - imported]
    if hashlib.sha256(original).hexdigest() != hook['body_sha256']:
        raise ValueError('Socket lifecycle original body changed')
    r = gate.Reader(sections[4])
    if r.count() != 1 or r.byte() != 0x70:raise ValueError('Expected one lifecycle function table')
    flags, minimum = r.uint(), r.uint(); maximum = r.uint() if flags & 1 else None; r.finish()
    if flags & ~5:raise ValueError('Unexpected lifecycle table flags')
    original_export = 'zema:lan:original:socket_close'
    r = gate.Reader(sections[7]); count = r.count(); old_exports = r.take(len(sections[7])-r.pos)
    check = gate.Reader(sections[7]); check.count()
    for _ in range(count):
        name = check.text(); check.byte(); check.uint()
        if name == original_export:raise ValueError('Socket lifecycle already installed')
    bodies[hook['index']-imported] = b'\x00\x20\x00' + (b'\x42' if flags & 4 else b'\x41') + sleb(minimum) + b'\x11' + leb(indices[hook['index']]) + b'\x00\x0b'
    bodies.append(original); functions.append(indices[hook['index']])
    output = bytearray(data[:8])
    for kind, raw in parts:
        if kind == 3:raw = leb(len(functions)) + b''.join(leb(i) for i in functions)
        elif kind == 4:raw = b'\x01\x70' + leb(flags) + leb(minimum+1) + (leb(maximum+1) if maximum is not None else b'')
        elif kind == 7:raw = leb(count+1) + old_exports + string(original_export) + b'\x00' + leb(len(indices))
        elif kind == 10:raw = leb(len(bodies)) + b''.join(leb(len(v))+v for v in bodies)
        output.extend(section(kind,raw))
    output = bytes(output); new_types, new_indices, _ = gate.module_abi(output)
    if new_types != types or new_indices != indices + [indices[hook['index']]]:
        raise ValueError('Socket lifecycle changed existing engine ABI indices')
    return output, dict(hook, slot=minimum, original_export=original_export)


def leb(n):
    out = bytearray()
    while True:
        b = n & 127; n >>= 7; out.append(b | (128 if n else 0))
        if not n:
            return bytes(out)


def sleb(n):
    if type(n) is not int or not -(1 << 63) <= n < (1 << 63):
        raise ValueError('Signed WASM immediate exceeds i64')
    out = bytearray()
    while True:
        b = n & 127; n >>= 7
        done = (n == 0 and not b & 64) or (n == -1 and bool(b & 64))
        out.append(b if done else b | 128)
        if done:
            return bytes(out)


def string(s):
    b = s.encode(); return leb(len(b)) + b


def section(kind, body):
    return bytes([kind]) + leb(len(body)) + body


def auxiliary(hooks):
    # Imported JS functions become typed WASM exports that can enter funcref tables.
    inverse = {name: kind for kind, name in gate.TYPES.items()}
    types = []; imports = []; exports = []
    for i, h in enumerate(hooks):
        types.append(b'\x60' + leb(len(h['params'])) + bytes(inverse[t] for t in h['params']) +
                     leb(len(h['results'])) + bytes(inverse[t] for t in h['results']))
        imports.append(string('zema') + string(h['field']) + b'\x00' + leb(i))
        exports.append(string(h['field']) + b'\x00' + leb(i))
    return b'\0asm\x01\0\0\0' + section(1, leb(len(types)) + b''.join(types)) + section(2, leb(len(imports)) + b''.join(imports)) + section(7, leb(len(exports)) + b''.join(exports))


def transform(data, contract):
    inspection = gate.inspect(data, contract)
    hooks = [h for h in inspection['hooks'] if h['group'] == 'vnet']
    if not hooks:
        raise ValueError('Socket hook contract absent')
    types, indices, _ = gate.module_abi(data)
    parts = list(gate.sections(data)); bodies = None; functions = None; start = None; table = None; export_body = None
    for kind, body in parts:
        r = gate.Reader(body)
        if kind == 3:
            functions = [r.uint() for _ in range(r.count())]; r.finish()
        elif kind == 4:
            if r.count() != 1 or r.byte() != 0x70:
                raise ValueError('Expected one funcref table')
            flags = r.uint(); minimum = r.uint(); maximum = r.uint() if flags & 1 else None; r.finish()
            if flags & ~5 or minimum > 1_000_000 or (maximum is not None and maximum < minimum):
                raise ValueError('Unsupported function table limits')
            table = flags, minimum, maximum
        elif kind == 7:
            export_body = body
            count = r.count()
            for _ in range(count):
                name = r.text(); r.byte(); r.uint()
                if name.startswith('zema:lan:'):
                    raise ValueError('Engine already contains LAN exports')
        elif kind == 8:
            start = r.uint(); r.finish()
        elif kind == 10:
            bodies = [r.take(r.uint()) for _ in range(r.count())]; r.finish()
    if table is None or functions is None or bodies is None or export_body is None:
        raise ValueError('Incomplete engine function layout')
    imported = len(indices) - len(functions)
    flags, minimum, maximum = table
    originals = []; additions = []; mappings = []
    for i, h in enumerate(hooks):
        defined = h['index'] - imported
        if not 0 <= defined < len(bodies):
            raise ValueError('A required socket hook is imported')
        original = len(indices) + i
        originals.append(bodies[defined]); functions.append(indices[h['index']])
        slot = minimum + i
        call = b''.join(b'\x20' + leb(p) for p in range(len(h['params'])))
        bodies[defined] = b'\x00' + call + (b'\x42' if flags & 4 else b'\x41') + sleb(slot) + b'\x11' + leb(indices[h['index']]) + b'\x00\x0b'
        name = 'zema:lan:original:' + h['field']
        additions.append(string(name) + b'\x00' + leb(original))
        mappings.append(dict(h, slot=slot, original_export=name))
    bodies.extend(originals)
    if start is not None:
        additions.append(string('zema:lan:start') + b'\x00' + leb(start))
    r = gate.Reader(export_body); count = r.count()
    new_exports = leb(count + len(additions)) + r.take(len(export_body) - r.pos) + b''.join(additions)
    output = bytearray(data[:8])
    for kind, body in parts:
        if kind == 3:
            body = leb(len(functions)) + b''.join(leb(i) for i in functions)
        elif kind == 4:
            body = b'\x01\x70' + leb(flags) + leb(minimum + len(hooks))
            if maximum is not None:
                body += leb(maximum + len(hooks))
        elif kind == 7:
            body = new_exports
        elif kind == 8:
            continue
        elif kind == 10:
            body = leb(len(bodies)) + b''.join(leb(len(b)) + b for b in bodies)
        output.extend(section(kind, body))
    output = bytes(output)
    # Parser-level invariants; this is not execution of the original game.
    new_types, new_indices, _ = gate.module_abi(output)
    if new_types != types or new_indices[:len(indices)] != indices:
        raise ValueError('Original type/function indices changed')
    metadata = {'format': 'zema-browser-engine-lan-v1', 'engine_sha256': contract['engine_sha256'],
                'patched_sha256': hashlib.sha256(output).hexdigest(), 'table64': bool(flags & 4),
                'hooks': mappings, 'auxiliary_wasm': list(auxiliary(hooks)),
                'deferred_start': start is not None, 'online_startup_ready': False,
                'runtime_verified': False, 'transport': 'EXPLICIT_LOCAL_WEBSOCKET'}
    return output, metadata


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    try:
        output = args.output.absolute(); build = APP.absolute() / 'Build'
        if output.parent != build or '..' in output.parts or output.exists():
            raise ValueError('Use a new immediate child of the isolated app Build folder')
        if any(path.is_symlink() for path in (output, *output.parents)):
            raise ValueError('Symlinked browser output refused')
        contract = json.loads(gate.CONTRACT.read_text()); gate.verify_reference(args.reference, contract)
        patched, metadata = transform(args.engine.read_bytes(), contract)
        build.mkdir(exist_ok=True); output.mkdir(mode=0o700)
        (output / 'game.engine-lan.wasm').write_bytes(patched)
        (output / 'engine-lan-module.json').write_text(json.dumps(metadata, indent=2) + '\n')
        (output / 'engine-lan-module.js').write_text('globalThis.ZemaEngineLanModule=' + json.dumps(metadata) + ';\n')
        print(json.dumps({'output': str(output), 'hooks': len(metadata['hooks']), 'original_indices_preserved': True,
                          'online_startup_ready': False, 'runtime_verified': False}))
    except (OSError, ValueError, KeyError) as error:
        p.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
