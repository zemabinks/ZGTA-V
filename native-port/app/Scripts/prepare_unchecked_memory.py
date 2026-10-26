"""Let PG_UNCHECKED_MEMORY builds skip wasm2c's per-access memory checks.

The engine's whole memory (its maximum size) is reserved and mapped at boot,
followed by an inaccessible guard region (EngineHost.c), so in-range accesses
need no check and runaway ones past the end still fault. This removes the
overflow check and size compare on every load/store, plus the call-depth
counter on every call. Run after prepare_heap_diagnostics.py.
"""
from pathlib import Path
root = Path(__file__).resolve().parents[1]

def patch(path):
    s = path.read_text()
    original = s
    add_old = '  uint64_t ret;\n#if __has_builtin(__builtin_add_overflow)'
    add_new = '  uint64_t ret;\n#if PG_UNCHECKED_MEMORY\n  return a + b;\n#elif __has_builtin(__builtin_add_overflow)'
    if add_new not in s:
        if s.count(add_old) != 1: raise RuntimeError(f'{path.name}: checked_add_u64 changed')
        s = s.replace(add_old, add_new)
    range_head = '#define RANGE_CHECK(mem, offset, len)'
    marker = '#if PG_UNCHECKED_MEMORY\n#define RANGE_CHECK(mem, offset, len)\n#else\n'
    if marker not in s:
        if s.count(range_head) != 1: raise RuntimeError(f'{path.name}: RANGE_CHECK changed')
        start = s.index(range_head)
        end = s.index('} while (0);', start) + len('} while (0);')
        s = s[:start] + marker + s[start:end] + '\n#endif' + s[end:]
    depth_old = '#if WASM_RT_STACK_DEPTH_COUNT\n#define FUNC_PROLOGUE'
    depth_new = '#if WASM_RT_STACK_DEPTH_COUNT && !PG_UNCHECKED_MEMORY\n#define FUNC_PROLOGUE'
    if depth_new not in s:
        if s.count(depth_old) != 1: raise RuntimeError(f'{path.name}: FUNC_PROLOGUE changed')
        s = s.replace(depth_old, depth_new)
    if s != original: path.write_text(s)

for name in ['game-impl.h', 'game-heap-impl.h']:
    path = root / 'Generated' / name
    if path.exists(): patch(path)
