#!/usr/bin/env python3
"""Offline gate for adapting glue5's engine LAN hooks to the Intel native port.

Reads only: never patches an engine, installs dependencies, discovers peers,
starts a game or changes an existing IPA. A matched ABI is not runtime proof.
Hook names/signatures describe the public glue5 source pinned in the contract.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

CONTRACT = Path(__file__).resolve().parents[1] / 'Tests/glue5_engine_lan_contract.json'
TYPES = {0x7f: 'i32', 0x7e: 'i64', 0x7d: 'f32', 0x7c: 'f64',
         0x7b: 'v128', 0x70: 'funcref', 0x6f: 'externref'}


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, length):
        end = self.pos + length
        if end > len(self.data):
            raise ValueError('Truncated WASM data')
        value = self.data[self.pos:end]
        self.pos = end
        return value

    def byte(self):
        return self.take(1)[0]

    def uint(self):
        value = 0
        for shift in range(0, 70, 7):
            byte = self.byte()
            value |= (byte & 127) << shift
            if not byte & 128:
                if value >= 1 << 64:
                    break
                return value
        raise ValueError('Invalid unsigned LEB128')

    def count(self):
        count = self.uint()
        if count > 1_000_000:
            raise ValueError('Oversized WASM vector')
        return count

    def text(self):
        return self.take(self.uint()).decode('utf-8')

    def finish(self):
        if self.pos != len(self.data):
            raise ValueError('Unexpected trailing WASM data')


def sections(data):
    reader = Reader(data)
    if reader.take(8) != b'\0asm\x01\0\0\0':
        raise ValueError('Expected WASM version 1')
    seen = set()
    while reader.pos < len(data):
        kind = reader.byte()
        body = reader.take(reader.uint())
        if kind and kind in seen:
            raise ValueError('Duplicate WASM section')
        seen.add(kind)
        yield kind, body


def valtype(reader):
    try:
        return TYPES[reader.byte()]
    except KeyError as error:
        raise ValueError('Unsupported WASM value type') from error


def limits(reader):
    flags = reader.uint()
    if flags & ~7:
        raise ValueError('Unsupported WASM limits')
    reader.uint()
    if flags & 1:
        reader.uint()


def module_abi(data):
    types, imports, functions = [], [], []
    names = defaultdict(list)
    body_count = None
    for kind, body in sections(data):
        reader = Reader(body)
        if kind == 1:
            for _ in range(reader.count()):
                if reader.byte() != 0x60:
                    raise ValueError('Expected a simple WASM function type')
                params = [valtype(reader) for _ in range(reader.count())]
                results = [valtype(reader) for _ in range(reader.count())]
                types.append((params, results))
        elif kind == 2:
            for _ in range(reader.count()):
                reader.text(); reader.text()
                imported = reader.byte()
                if imported == 0:
                    imports.append(reader.uint())
                elif imported == 1:
                    valtype(reader); limits(reader)
                elif imported == 2:
                    limits(reader)
                elif imported == 3:
                    valtype(reader)
                    if reader.byte() not in (0, 1):
                        raise ValueError('Invalid global mutability')
                elif imported == 4:
                    if reader.byte() != 0:
                        raise ValueError('Unsupported tag attribute')
                    reader.uint()
                else:
                    raise ValueError('Unsupported WASM import')
        elif kind == 3:
            functions = [reader.uint() for _ in range(reader.count())]
        elif kind == 10:
            body_count = reader.count()
            for _ in range(body_count):
                reader.take(reader.uint())
        elif kind == 0:
            if reader.text() != 'name':
                continue
            seen_indices = set()
            while reader.pos < len(body):
                subkind = reader.byte()
                subsection = Reader(reader.take(reader.uint()))
                if subkind != 1:
                    continue
                for _ in range(subsection.count()):
                    index, name = subsection.uint(), subsection.text()
                    if index in seen_indices:
                        raise ValueError('Duplicate function name index')
                    seen_indices.add(index)
                    names[name].append(index)
                subsection.finish()
        else:
            continue
        reader.finish()
    indices = imports + functions
    if body_count != len(functions) or any(i >= len(types) for i in indices):
        raise ValueError('Invalid function/type table')
    if any(i >= len(indices) for values in names.values() for i in values):
        raise ValueError('Function name outside the function table')
    return types, indices, names


def inspect(data, contract):
    digest = hashlib.sha256(data).hexdigest()
    if digest != contract['engine_sha256']:
        raise ValueError('Engine hash mismatch; do not guess addresses or allow an unknown build')
    types, indices, names = module_abi(data)
    hooks = contract['hooks']
    bodies = {}
    if any('body_sha256' in hook for hook in hooks):
        for kind, body in sections(data):
            if kind == 10:
                r = Reader(body); count = r.count(); imported = len(indices) - count
                for i in range(count):
                    raw = r.take(r.uint())
                    bodies[imported + i] = hashlib.sha256(raw).hexdigest()
    fields = [h['field'] for h in hooks]
    if not hooks or len(fields) != len(set(fields)):
        raise ValueError('Invalid or repeated hook contract')
    resolved = []
    for hook in hooks:
        matched = names.get(hook['name'], [])
        if len(matched) != 1 or matched[0] != hook['index']:
            raise ValueError('Missing, ambiguous or moved hook: ' + hook['field'])
        index = matched[0]
        params, results = types[indices[index]]
        if params != hook['params'] or results != hook['results']:
            raise ValueError('Hook signature mismatch: ' + hook['field'])
        if 'body_sha256' in hook and bodies.get(index) != hook['body_sha256']:
            raise ValueError('Hook body mismatch: ' + hook['field'])
        resolved.append(dict(hook, c_symbol='w2c_game_f' + str(index)))
    return {'format': 'zema-engine-lan-inspection-v1',
            'status': 'EXACT_ENGINE_HOOK_ABI_MATCH', 'engine_sha256': digest,
            'upstream_revision': contract['upstream_revision'],
            'hooks_resolved': len(resolved), 'groups': dict(Counter(h['group'] for h in hooks)),
            'hooks': resolved, 'runtime_enabled': False, 'runtime_verified': False,
            'browser_integration': 'NOT_IMPLEMENTED', 'network_operations': 0}


def verify_reference(root, contract):
    """Compare source bytes as data; do not run build scripts or import code."""
    for relative, expected in contract['upstream_files'].items():
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Unsafe reference path')
        current = root
        for part in path.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError('Reference paths must not be symlinks')
        if hashlib.sha256(current.read_bytes()).hexdigest() != expected:
            raise ValueError('Reviewed upstream source changed: ' + relative)


def inspect_generated(root, hooks):
    """Locate existing generated C definitions; do not rewrite or compile them."""
    for part in (root, *root.parents):
        if part.is_symlink():
            raise ValueError('Generated paths must not be symlinks')
    paths = sorted(p for p in root.glob('game_*.c') if re.fullmatch(r'game_\d+\.c', p.name))
    if len(paths) != 64:
        raise ValueError('Expected the existing 64-part generated engine')
    wanted = {hook['index']: hook for hook in hooks}
    found = defaultdict(list)
    pattern = re.compile(r'(?m)^(?:static )?(\w+) w2c_game_f(\d+)\(([^;{}]*)\) \{')
    c_types = {'u32': 'i32', 'u64': 'i64', 'f32': 'f32', 'f64': 'f64', 'v128': 'v128'}
    for path in paths:
        if path.is_symlink():
            raise ValueError('Generated files must not be symlinks')
        raw = path.read_bytes()
        for match in pattern.finditer(raw.decode('utf-8')):
            index = int(match[2])
            if index not in wanted:
                continue
            arguments = [p.strip() for p in match[3].split(',')]
            if not re.fullmatch(r'w2c_game\s*\*\s*\w+', arguments[0]):
                raise ValueError('Unexpected C engine instance parameter')
            try:
                params = [c_types[p.split()[0]] for p in arguments[1:]]
                results = [] if match[1] == 'void' else [c_types[match[1]]]
            except KeyError as error:
                raise ValueError('Unexpected generated C type') from error
            hook = wanted[index]
            if params != hook['params'] or results != hook['results']:
                raise ValueError('Generated C signature mismatch: ' + hook['field'])
            found[index].append({'field': hook['field'], 'part': path.name,
                                 'c_symbol': 'w2c_game_f' + str(index),
                                 'part_sha256': hashlib.sha256(raw).hexdigest()})
    if any(len(found[index]) != 1 for index in wanted):
        raise ValueError('Missing or duplicate generated C hook definition')
    return {'status': 'EXISTING_C_HOOK_ABI_MATCH', 'runtime_enabled': False,
            'parts_containing_hooks': len({rows[0]['part'] for rows in found.values()}),
            'definitions': [found[index][0] for index in sorted(wanted)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--generated', type=Path,
                        help='optional existing 64-part C tree; read-only ABI mapping')
    args = parser.parse_args()
    try:
        contract = json.loads(CONTRACT.read_text())
        verify_reference(args.reference, contract)
        result = inspect(args.engine.read_bytes(), contract)
        result['upstream_files'] = 'PINNED_SOURCE_BYTES_MATCH'
        if args.generated:
            result['generated_c'] = inspect_generated(args.generated, result['hooks'])
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
