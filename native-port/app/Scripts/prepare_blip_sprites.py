"""Bridge the exact minimap getter; valid original assets always take priority."""
import argparse
import hashlib
from pathlib import Path

SIGNATURE='u64 w2c_game_f35144(w2c_game* instance, u64 var_p0) {'
BODY_SHA256='e1b8e4076d667cef97441cf0024a0187879e625cce2cbc6160e25a8f8573843e'
RETURN='  return var_j0;'
OLD_PATCHED_RETURN='  return pg_blip_name_diagnostic(instance, var_p0, var_j0);'
PATCHED_RETURN='  return pg_blip_name_diagnostic(instance, pg_blip_reference, var_j0);'
PRESERVE='  const u64 pg_blip_reference = var_p0;\n'
INCLUDE='#include "game-blip-diagnostics-impl.h"\n'
HEADER='#include "game.h"\nextern u64 pg_blip_name_diagnostic(w2c_game *, u64, u64);\n'

def patch(source):
    if source.count(SIGNATURE)!=1:raise ValueError('Pinned native blip getter missing or duplicated')
    start=source.index(SIGNATURE);end=source.index('\n}\n',start)+3;body=source[start:end]
    original=body.replace(PATCHED_RETURN,RETURN).replace(OLD_PATCHED_RETURN,RETURN)
    original=original.replace(SIGNATURE+'\n'+PRESERVE,SIGNATURE+'\n')
    if hashlib.sha256(original.encode()).hexdigest()!=BODY_SHA256 or original.count(RETURN)!=1:
        raise ValueError('Pinned native blip getter changed')
    # The generated original reassigns var_p0 during binary search. Preserve the caller's reference.
    wanted=original.replace(SIGNATURE+'\n',SIGNATURE+'\n'+PRESERVE).replace(RETURN,PATCHED_RETURN)
    output=source[:start]+wanted+source[end:]
    return output if INCLUDE in output else INCLUDE+output

def prepare(generated):
    import generate_blip_fallbacks
    for path,text in generate_blip_fallbacks.outputs().items():
        if path.read_text()!=text:raise ValueError("Shared sprite fallback table differs: "+str(path))
    # The reviewed partition is fixed. Refuse a different generated layout.
    generated=Path(generated);part=generated/'game_19.c';source=patch(part.read_text())
    part.write_text(source);(generated/'game-blip-diagnostics-impl.h').write_text(HEADER)
    print('Native blip diagnostics: pinned f35144 in '+part.name)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generated',type=Path,default=Path(__file__).resolve().parents[1]/'Generated')
    prepare(parser.parse_args().generated)
