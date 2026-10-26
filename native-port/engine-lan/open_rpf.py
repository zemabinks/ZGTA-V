"""Recognize OpenIV's plaintext RPF table marker in the pinned older engine.

Only OPEN skips the table cipher. Other keys execute the exact original body;
archive bytes, resource decoding, metadata validation and protocol stay intact.
Format reference: dexyfex/CodeWalker, RpfFile.ReadHeader (OPEN is plaintext).
"""
import hashlib
import json
from pathlib import Path
import re

import browser_wasm as b

INDEX = 1194
OPEN = 0x4e45504f
BODY_SHA = '2e8687a33f1b5f9aee5fdc34864d60f2c765721d7a9d887e838c9061ba9b9133'
C_SHA = '4c3f20f5127a88d19ac872bf077d96c5f6b4eba78982cd044a78db6c47cef5c1'
INPUTS = {
    '11ca8d2c04c5e843d18ff4aea4899d72c86973c6b031df334e67c446b2ae83e0',
    'ab52643cff5089a0daf4199dec33622f580eadce80bc51995e8c693c57b3b8f2',
    '05c5101804c83bdf808c0de9e23b2a8d0679d310235dd74461bd8077f02af59b',
}
C_GUARD = '  if (var_p0 == 0x4e45504fu) return; /* OpenIV plaintext TOC */\n'
WASM_GUARD = b'\x20\x00\x41' + b.sleb(OPEN) + b'\x46\x04\x40\x0f\x0b'
PATTERN = re.compile(r'(?ms)^void w2c_game_f1194\([^\n]*\) \{\n.*?^\}')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def native_body(text):
    found = list(PATTERN.finditer(text))
    if len(found) != 1:
        raise ValueError('Expected one pinned RPF cipher function')
    return found[0]


def patch_native(data, undo=False):
    text = data.decode()
    match = native_body(text)
    body = match[0]
    start = body.index('\n') + 1
    original = body
    if undo:
        if body[start:start + len(C_GUARD)] != C_GUARD or body.count(C_GUARD) != 1:
            raise ValueError('OPEN RPF native guard changed')
        original = body[:start] + body[start + len(C_GUARD):]
    if sha(original.encode()) != C_SHA:
        raise ValueError('Unreviewed native RPF cipher body')
    patched = original if undo else original[:start] + C_GUARD + original[start:]
    return (text[:match.start()] + patched + text[match.end():]).encode()


def stage_native(folder):
    file = folder / 'game_1.c'
    before = file.read_bytes()
    after = patch_native(before)
    file.write_bytes(after)
    return {'format': 'zgta-open-rpf-v1', 'index': INDEX,
            'before_sha256': sha(before), 'after_sha256': sha(after),
            'scope': 'OPEN_PLAINTEXT_TABLES_ONLY', 'archive_bytes_changed': False,
            'runtime_verified': False}


def verify_native(folder):
    patch_native((folder / 'game_1.c').read_bytes(), undo=True)


def patch_body(body):
    if sha(body) != BODY_SHA:
        raise ValueError('Unreviewed WASM RPF cipher body')
    reader = b.gate.Reader(body)
    for _ in range(reader.count()):
        reader.uint(); reader.byte()
    return body[:reader.pos] + WASM_GUARD + body[reader.pos:]


def transform(data):
    if sha(data) not in INPUTS:
        raise ValueError('Unreviewed OPEN RPF engine input')
    types, indices, _ = b.gate.module_abi(data)
    if types[indices[INDEX]] != (['i32', 'i64', 'i32'], []):
        raise ValueError('RPF cipher ABI changed')
    parts = list(b.gate.sections(data))
    sections = dict(parts)
    reader = b.gate.Reader(sections[3])
    functions = [reader.uint() for _ in range(reader.count())]; reader.finish()
    imported = len(indices) - len(functions)
    reader = b.gate.Reader(sections[10])
    bodies = [reader.take(reader.uint()) for _ in range(reader.count())]; reader.finish()
    bodies[INDEX - imported] = patch_body(bodies[INDEX - imported])
    code = b.leb(len(bodies)) + b''.join(b.leb(len(body)) + body for body in bodies)
    result = data[:8] + b''.join(b.section(kind, code if kind == 10 else raw) for kind, raw in parts)
    if b.gate.module_abi(result)[:2] != (types, indices):
        raise ValueError('OPEN RPF patch changed the ABI')
    return result, {'format': 'zgta-open-rpf-v1', 'index': INDEX,
                    'input_sha256': sha(data), 'patched_sha256': sha(result),
                    'original_body_sha256': BODY_SHA,
                    'scope': 'OPEN_PLAINTEXT_TABLES_ONLY', 'new_imports': 0,
                    'archive_bytes_changed': False, 'runtime_verified': False}
