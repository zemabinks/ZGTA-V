"""Name the engine function in "Invalid call_indirect" crash logs.

A crash log's native addresses only mean something with the exact binary that crashed, and
players build their own. wasm2c checks every indirect call (a C++ virtual call or function
pointer in the engine) with CHECK_CALL_INDIRECT; when the fast check fails it calls
func_types_eq_slowpath, which traps when the call is invalid. This adds a note just before the
slow path with the calling function's generated name (w2c_game_fN, which funcnames.tsv turns into
the engine function) and the table index, so pg_record_trap can print it.
Runs on every generated header that defines the check (game-impl.h and the copies made from it).
"""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
OLD = '   func_types_eq_slowpath(&(table), ft, x))'
NEW = '   (pg_note_call_indirect(__func__, (x), (table).size), func_types_eq_slowpath(&(table), ft, x)))'
DECL = 'void pg_note_call_indirect(const char *function, uint32_t index, uint32_t size);\n'
patched = 0
for path in sorted((root / 'Generated').glob('*.h')):
    s = path.read_text()
    if '#define CHECK_CALL_INDIRECT' not in s or 'pg_note_call_indirect' in s: continue
    if s.count(OLD) != 1: raise RuntimeError(f'CHECK_CALL_INDIRECT changed in {path.name}')
    s = s.replace('#define CHECK_CALL_INDIRECT', DECL + '#define CHECK_CALL_INDIRECT', 1).replace(OLD, NEW, 1)
    path.write_text(s); patched += 1
print(f'trap context: {patched} headers patched')
