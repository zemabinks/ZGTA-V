"""Exact reviewed engine pin for Glue 5's memory-file address correction.

Inspection only: callers must integrate the typed descriptor into their
index-preserving transformation and install the explicit JavaScript callback.
"""
import hashlib
import browser_wasm as b

ENGINE_SHA256 = '11ca8d2c04c5e843d18ff4aea4899d72c86973c6b031df334e67c446b2ae83e0'
NAME = 'rage::fiDevice::MakeMemoryFileName(char*, int, void const*, unsigned long, bool, char const*)'
BODY_SHA256 = '3bf0f7632417fac9a02fa60cfb1e5fdee80c87d8955ee8124c61fdab1f3c9da6'
UPSTREAM = '0db284d99ddc2b36291c4a29b17ad69bd93c5bb5'
HOOK = {'field': 'memory_file_name', 'index': 1652,
        'params': ['i64', 'i32', 'i64', 'i64', 'i32', 'i64'], 'results': [],
        'name': NAME, 'body_sha256': BODY_SHA256}


def pin(types, indices, names, bodies, imported):
    """Verify this exact function in a caller's already admitted engine."""
    if names.get(NAME) != [HOOK['index']]:
        raise ValueError('Memory filename function name/index changed')
    if types[indices[HOOK['index']]] != (HOOK['params'], HOOK['results']):
        raise ValueError('Memory filename function ABI changed')
    body = bodies[HOOK['index'] - imported]
    if len(body) != 63 or hashlib.sha256(body).hexdigest() != BODY_SHA256:
        raise ValueError('Memory filename function body changed')
    return dict(HOOK)


def inspect(data):
    """Inspect original bytes without executing or changing a game module."""
    if hashlib.sha256(data).hexdigest() != ENGINE_SHA256:
        raise ValueError('Unreviewed engine for memory filename inspection')
    types, indices, names = b.gate.module_abi(data)
    sections = dict(b.gate.sections(data))
    r = b.gate.Reader(sections[3]); imported = len(indices) - r.count()
    r = b.gate.Reader(sections[10])
    bodies = [r.take(r.uint()) for _ in range(r.count())]; r.finish()
    return pin(types, indices, names, bodies, imported)
