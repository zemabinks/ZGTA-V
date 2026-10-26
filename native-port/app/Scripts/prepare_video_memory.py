"""Give the engine a video memory size that fits the device.

The graphics setup (f9975) reads the adapter's dedicated video memory (+48 of the adapter
record) and derives the texture streaming budget from it; the browser build reports about 4 GB
everywhere. pg_video_memory replaces the value with a budget from the app's memory limit.
"""
from pathlib import Path
import re
root = Path(__file__).resolve().parents[1]
FUNCTION = '9975'
MARK = 'pg_video_memory('
OLD = '(u64)checked_add_u64(var_j1, 48u));\n  var_l0 = var_j1;\n'
NEW = '(u64)checked_add_u64(var_j1, 48u));\n  var_j1 = pg_video_memory(var_j1);\n  var_l0 = var_j1;\n'
done = False
for path in sorted((root / 'Generated').glob('game_*.c')):
    s = path.read_text()
    found = re.search(r'^void w2c_game_f' + FUNCTION + r'\(w2c_game\* instance\) \{$', s, re.M)
    if not found: continue
    start, end = found.start(), s.index('\n}\n', found.start())
    body = s[start:end]
    if MARK not in body:
        if body.count(OLD) != 1 or '3962438ull' not in body:
            raise RuntimeError(f'Pinned f{FUNCTION} (video memory setup) changed')
        s = s[:start] + body.replace(OLD, NEW, 1) + s[end:]
        if 'extern u64 pg_video_memory(u64);' not in s:
            s = s.replace('#include "game-heap-impl.h"', '#include "game-heap-impl.h"\nextern u64 pg_video_memory(u64);', 1)
            if 'extern u64 pg_video_memory(u64);' not in s: raise RuntimeError('Run prepare_heap_diagnostics first')
        path.write_text(s)
    done = True
    break
if not done: raise RuntimeError(f'Pinned function f{FUNCTION} not found')
