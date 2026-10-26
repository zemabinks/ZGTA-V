"""Let scripts on the GTA VI test map (env_test) run like the GTA V map.

GET_INDEX_OF_CURRENT_LEVEL (f53281, registered by name in the native table) answers the index
of the loaded level. The startup script only launches main (and through it the phone, cheats
and the rest of free roam) on the GTA V level; on env_test it places the player and stops, so
Sandbox on the test map had no phone. pg_script_level_index can answer the GTA V index there.
"""
from pathlib import Path
import re
root = Path(__file__).resolve().parents[1]
FUNCTION = '53281'
MARK = 'pg_script_level_index('
OLD = '  var_B0:;\n  i32_store_shared('
NEW = '  var_B0:;\n  var_i1 = pg_script_level_index(var_i1);\n  i32_store_shared('
done = False
for path in sorted((root / 'Generated').glob('game_*.c')):
    s = path.read_text()
    found = re.search(r'^void w2c_game_f' + FUNCTION + r'\(w2c_game\* instance, u64 var_p0\) \{$', s, re.M)
    if not found: continue
    start, end = found.start(), s.index('\n}\n', found.start())
    body = s[start:end]
    if MARK not in body:
        if body.count(OLD) != 1 or '6722536ull' not in body:
            raise RuntimeError(f'Pinned f{FUNCTION} (GET_INDEX_OF_CURRENT_LEVEL) changed')
        s = s[:start] + body.replace(OLD, NEW, 1) + s[end:]
        include = '#include "game-level-index-impl.h"'
        if include not in s: s = s.replace('#include "game-impl.h"', include, 1)
        path.write_text(s)
    done = True
    break
if not done: raise RuntimeError(f'Pinned function f{FUNCTION} not found')
(root / 'Generated/game-level-index-impl.h').write_text(
    '#include "game-impl.h"\n'
    'extern u32 pg_script_level_index(u32 index);\n')
