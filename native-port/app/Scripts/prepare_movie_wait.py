"""Give the pinned engine's video loading a time limit.

CMovie::WaitTillLoaded is inlined in five CMovieMgr functions: it sleeps 1 ms at a time until the
video is loaded or marked as failed (bit 32 of the flags at +96), with no limit. The game files have
no .bik videos, and a load that never answered froze the game whenever a TV came on or changed
show. Each of those sleeps goes through pg_movie_wait instead, which marks the video as failed
after a short wait.
"""
from pathlib import Path
import re
root = Path(__file__).resolve().parents[1]
FUNCTIONS = {
    '80969': 'CMovieMgr::UpdateFrame',
    '81493': 'CMovie::Play',
    '80987': 'CMovieMgr::Delete',
    '81494': 'CMovieMgr::Stop',
    '81507': 'CMovieMgr::GetTime',
}
# The failure-flag test followed by sysIpcSleep(1), as WABT writes it.
loop = re.compile(
    r'(?P<i>[ ]+)var_j0 = (?P<movie>var_[lp]\d+);\n'
    r'(?P=i)var_i0 = i32_load8_u_shared\(wasm_rt_local_memory_base, wasm_rt_local_memory_size, instance->w2c_env_memory, \(u64\)checked_add_u64\(var_j0, 96u\)\);\n'
    r'(?P=i)var_i1 = 32u;\n(?P=i)var_i0 &= var_i1;\n(?P=i)if \(var_i0\) \{goto var_B\d+;\}\n'
    r'(?P=i)(?:var_i0 = 1u;\n(?P=i)w2c_game_f135\(instance, var_i0\);|pg_movie_wait\(instance, (?P=movie)\);)\n')
def patch(match):
    i, movie = match['i'], match['movie']
    if 'pg_movie_wait' in match.group(0): return match.group(0)
    head = match.group(0).rsplit('\n', 3)[0]
    return f'{head}\n{i}pg_movie_wait(instance, {movie});\n'
done = set()
for path in sorted((root / 'Generated').glob('game_*.c')):
    s = original = path.read_text()
    for function in FUNCTIONS:
        found = re.search(r'^\S.* w2c_game_f' + function + r'\(w2c_game\* instance[^;\n]*\{$', s, re.M)
        if not found: continue
        start, end = found.start(), s.index('\n}\n', found.start())
        body = s[start:end]
        if len(loop.findall(body)) != 1:
            raise RuntimeError(f'Pinned video wait in f{function} ({FUNCTIONS[function]}) changed')
        s = s[:start] + loop.sub(patch, body) + s[end:]
        done.add(function)
    if s != original:
        include = '#include "game-movie-wait-impl.h"'
        if include not in s: s = s.replace('#include "game-impl.h"', include, 1)
        path.write_text(s)
missing = set(FUNCTIONS) - done
if missing: raise RuntimeError('Pinned functions not found: ' + ', '.join(f'f{f}' for f in sorted(missing)))
(root / 'Generated/game-movie-wait-impl.h').write_text('#include "game-impl.h"\nextern void pg_movie_wait(w2c_game *instance, uint64_t movie);\n')
