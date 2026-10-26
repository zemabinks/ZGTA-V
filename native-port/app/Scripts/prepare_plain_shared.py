"""PG_PLAIN_SHARED=1 builds: every ordinary load and store on the shared memory is a plain access.

wasm2c makes them relaxed atomics on volatile pointers with a forced read, which keeps the
compiler from optimising any engine code (see prepare_plain_dsp.py). Wasm atomics (i32_atomic_*,
wait/notify) are untouched. Off by default; the flag exists to measure and test it.
"""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
LOAD_OLD = '''    t1 result;                                                                \\
    result = atomic_load_explicit(                                            \\
        (_Atomic volatile t1*)MEM_ADDR(mem, addr, sizeof(t1)),                \\
        memory_order_relaxed);                                                \\
    t3 ret = (t3)(t2)result;                                                  \\
    force_read(ret);                                                          \\
    return ret;                                                               \\'''
LOAD_NEW = '''    t1 result;                                                                \\
    PG_SHARED_LOAD_BODY(t1, result);                                          \\
    t3 ret = (t3)(t2)result;                                                  \\
    PG_SHARED_FORCE_READ(force_read, ret);                                    \\
    return ret;                                                               \\'''
STORE_OLD = '''    t1 wrapped = (t1)value;                                                   \\
    atomic_store_explicit(                                                    \\
        (_Atomic volatile t1*)MEM_ADDR(mem, addr, sizeof(t1)), wrapped,       \\
        memory_order_relaxed);                                                \\'''
STORE_NEW = '''    t1 wrapped = (t1)value;                                                   \\
    PG_SHARED_STORE_BODY(t1, wrapped);                                        \\'''
PRELUDE = '''#if PG_PLAIN_SHARED
#define PG_SHARED_LOAD_BODY(t1, result) memcpy(&result, (const void*)(uintptr_t)MEM_ADDR(mem, addr, sizeof(t1)), sizeof(t1))
#define PG_SHARED_STORE_BODY(t1, wrapped) memcpy((void*)(uintptr_t)MEM_ADDR(mem, addr, sizeof(t1)), &wrapped, sizeof(t1))
#define PG_SHARED_FORCE_READ(force_read, value)
#else
#define PG_SHARED_LOAD_BODY(t1, result) result = atomic_load_explicit((_Atomic volatile t1*)MEM_ADDR(mem, addr, sizeof(t1)), memory_order_relaxed)
#define PG_SHARED_STORE_BODY(t1, wrapped) atomic_store_explicit((_Atomic volatile t1*)MEM_ADDR(mem, addr, sizeof(t1)), wrapped, memory_order_relaxed)
#define PG_SHARED_FORCE_READ(force_read, value) force_read(value)
#endif
'''
for name in ['game-impl.h', 'game-heap-impl.h']:
    path = root / 'Generated' / name
    if not path.exists(): continue
    s = path.read_text()
    if 'PG_SHARED_LOAD_BODY' in s: continue
    if s.count(LOAD_OLD) != 1 or s.count(STORE_OLD) != 1: raise RuntimeError(f'{name}: shared load/store changed')
    s = s.replace(LOAD_OLD, LOAD_NEW).replace(STORE_OLD, STORE_NEW)
    anchor = '#define DEFINE_SHARED_LOAD('
    s = s.replace(anchor, PRELUDE + anchor, 1)
    path.write_text(s)
print('plain shared accesses: available with PG_PLAIN_SHARED=1')
