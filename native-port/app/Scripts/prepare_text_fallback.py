"""Hook only the pinned generated native text getter; original translations win."""
import argparse
import hashlib
from pathlib import Path

SIGNATURE = 'u64 w2c_game_f77480(w2c_game* instance, u32 var_p0) {'
BODY_SHA256 = '7b32f618cc7685d5956e6466844b50c5ec9d72bb750cd5cb2b8beca0ef537913'
RETURN = '  return var_j0;'
PATCHED_RETURN = '  return pg_missing_label(instance, var_p0, var_j0);'
INCLUDE = '#include "game-text-fallback-impl.h"\n'
# The generated part already includes unguarded game-impl.h; never include it twice.
HEADER = '#include "game.h"\nextern u64 pg_missing_label(w2c_game *, u32, u64);\n'


def patch(source):
    if source.count(SIGNATURE) != 1:
        raise ValueError('Pinned native text getter missing or duplicated')
    start = source.index(SIGNATURE)
    end = source.index('\n}\n', start)+3
    body = source[start:end]
    patched = PATCHED_RETURN in body
    original = body.replace(PATCHED_RETURN, RETURN) if patched else body
    if hashlib.sha256(original.encode()).hexdigest() != BODY_SHA256 or original.count(RETURN) != 1:
        raise ValueError('Pinned native text getter changed')
    if patched:
        if INCLUDE not in source:
            raise ValueError('Native fallback declaration missing')
        return source
    return INCLUDE + source[:start] + body.replace(RETURN, PATCHED_RETURN) + source[end:]


def prepare(generated):
    matches = []
    for path in sorted(generated.glob('game_*.c')):
        source = path.read_text()
        if SIGNATURE in source:
            matches.append((path, patch(source)))
    if len(matches) != 1:
        raise ValueError('Expected one pinned native text getter')
    path, source = matches[0]
    path.write_text(source)
    (generated/'game-text-fallback-impl.h').write_text(HEADER)
    print('Native text fallback: pinned f77480 in ' + path.name)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--generated', type=Path, default=Path(__file__).resolve().parents[1]/'Generated')
    args = p.parse_args()
    prepare(args.generated)
