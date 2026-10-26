"""Export multiplayer natives without changing any function index.

Port's pinned C patches depend on original function indices. Adding host
imports (as the Wasmtime patcher does) would silently invalidate them.
"""
import argparse
import json
import re
from pathlib import Path

HOOKS = {
    'script': 'GtaThread::Update(int)',
    'explosion': 'CExplosionManager::AddExplosion(CExplosionManager::CExplosionArgs&, CProjectile*, bool)',
    'timewarp': 'CTimeWarper::SetTargetTimeWarp(TW_Dir)',
}

def leb(value):
    result = bytearray()
    while True:
        b = value & 127
        value >>= 7
        result.append(b | (128 if value else 0))
        if not value: return bytes(result)

class Reader:
    def __init__(self, data): self.data, self.pos = data, 0
    def uint(self):
        value, shift = 0, 0
        while True:
            b = self.data[self.pos]; self.pos += 1
            value |= (b & 127) << shift
            if not b & 128: return value
            shift += 7
            if shift > 70: raise ValueError('Invalid LEB128')
    def string(self):
        n = self.uint(); b = self.data[self.pos:self.pos+n]; self.pos += n
        if len(b) != n: raise ValueError('Truncated name')
        return b.decode('utf-8')
    def rest(self): return self.data[self.pos:]

def string(value):
    value = value.encode('utf-8'); return leb(len(value)) + value

def sections(wasm):
    if wasm[:8] != b'\0asm\x01\0\0\0': raise ValueError('Not a WASM module')
    r = Reader(wasm); r.pos = 8
    while r.pos < len(wasm):
        start = r.pos; kind = wasm[r.pos]; r.pos += 1; size = r.uint()
        body = wasm[r.pos:r.pos+size]; r.pos += size
        if len(body) != size: raise ValueError('Truncated section')
        yield kind, body, wasm[start:r.pos]

def prepare(wasm, commands):
    names, globals_, original_exports = {}, {}, {}
    parts = list(sections(wasm))
    for kind, body, _ in parts:
        r = Reader(body)
        if kind == 0 and r.string() == 'name':
            for subkind, subbody, _ in sections(b'\0asm\x01\0\0\0' + r.rest()):
                if subkind not in (1, 7): continue
                target = names if subkind == 1 else globals_
                m = Reader(subbody)
                for _ in range(m.uint()):
                    index, name = m.uint(), m.string()
                    target.setdefault(name, index)
        elif kind == 7:
            for _ in range(r.uint()):
                name = r.string(); export_kind = r.data[r.pos]; r.pos += 1
                original_exports[name] = (export_kind, r.uint())
    hooks = {key: names[name] for key, name in HOOKS.items()}
    tls = globals_['__tls_base']  # Fail rather than guessing the TLS global.
    wanted = {f'mp:{name}': (0, names[symbol]) for name, symbol in commands if symbol in names}
    required = ['PlayerPedId', 'GetEntityCoords', 'CreatePed', 'CreateVehicle', 'RequestModel', 'HasModelLoaded', 'SetEntityCoordsNoOffset']
    for name in required:
        if 'mp:' + name not in wanted: raise ValueError('Missing required native ' + name)
    wanted['mugoat:tls-base'] = (3, tls)
    for name in ['emscripten_stack_get_current', '_emscripten_stack_alloc', '_emscripten_stack_restore']:
        if name not in original_exports: raise ValueError('Missing stack export ' + name)
    if any(name in original_exports for name in wanted): raise ValueError('Already patched')
    output = bytearray(wasm[:8])
    for kind, body, raw in parts:
        if kind == 7:
            r = Reader(body); count = r.uint()
            entries = b''.join(string(name) + bytes([ek]) + leb(index) for name, (ek, index) in wanted.items())
            body = leb(count + len(wanted)) + r.rest() + entries
            output.extend(bytes([kind]) + leb(len(body)) + body)
        else: output.extend(raw)
    # Every section except exports must remain byte-for-byte identical.
    indices = {name: index for name, (ek, index) in wanted.items() if ek == 0}
    return bytes(output), {'hooks': hooks, 'exports': list(wanted), 'indices': indices, 'missing': [n for n, s in commands if s not in names]}

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('engine', type=Path); p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[3]
    text = (root / 'src/mp.rs').read_text(encoding='utf-8').split('const ACTIVE_THREAD_TLS')[0]
    commands = re.findall(r'\("([^"]+)", "([^"]+)"\)', text)
    output, metadata = prepare(args.engine.read_bytes(), commands)
    args.out.write_bytes(output)
    args.out.with_suffix('.json').write_text(json.dumps(metadata, indent=2))
    print(f'Native online: exported {len(metadata["exports"])} natives; original indices unchanged; {len(metadata["missing"])} optional natives absent.')
