"""Let scripts stop waiting for texture dictionaries the game files don't have.

HAS_STREAMED_TEXTURE_DICT_LOADED (graphics_commands::HasStreamedTxdLoaded, f50534) looks the
name up in the texture dictionary store and answers false when it isn't there. The pinned
scripts are newer than the game files: Los Santos Customs (carmod_shop) waits for "MPShopSale"
before it shows its menu, that dictionary is in none of the game's archives, and the shop hung
with the car inside and no menu. pg_streamed_txd_loaded answers true for a name the store has
never heard of (it can never load), so the script continues and draws nothing for it. Names the
store knows still report their real state.
"""
from pathlib import Path
import re
root = Path(__file__).resolve().parents[1]
FUNCTION = '50534'
MARK = 'pg_streamed_txd_loaded('
done = False
for path in sorted((root / 'Generated').glob('game_*.c')):
    s = path.read_text()
    found = re.search(r'^u32 w2c_game_f' + FUNCTION + r'\(w2c_game\* instance, u64 var_p0\) \{$', s, re.M)
    if not found: continue
    start, end = found.start(), s.index('\n}\n', found.start())
    body = s[start:end]
    if MARK not in body:
        # Keep the name: var_p0 is reused as a pointer while the store is searched.
        prologue = '  FUNC_PROLOGUE;\n'
        tail = '    var_B1:;\n    var_i0 = var_l2;\n    goto var_Bfunc;\n'
        if body.count(prologue) != 1 or body.count(tail) != 1 or 'var_l3 = var_i1;' not in body:
            raise RuntimeError(f'Pinned f{FUNCTION} (graphics_commands::HasStreamedTxdLoaded) changed')
        body = body.replace(prologue, prologue + '  u64 pg_txd_name = var_p0;\n', 1)
        body = body.replace(tail, '    var_B1:;\n    var_l2 = pg_streamed_txd_loaded(instance, pg_txd_name, var_l3, var_l2);\n'
                            '    var_i0 = var_l2;\n    goto var_Bfunc;\n', 1)
        s = s[:start] + body + s[end:]
        include = '#include "game-missing-txd-impl.h"'
        if include not in s: s = s.replace('#include "game-impl.h"', include, 1)
        path.write_text(s)
    done = True
    break
if not done: raise RuntimeError(f'Pinned function f{FUNCTION} not found')
(root / 'Generated/game-missing-txd-impl.h').write_text(
    '#include "game-impl.h"\n'
    'extern u32 pg_streamed_txd_loaded(w2c_game *instance, u64 name, u32 hash, u32 loaded);\n')
