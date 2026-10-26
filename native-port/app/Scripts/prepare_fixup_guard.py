"""Keep a resource with an invalid pointer from ending the game.

datResourceMap lookup (f2092) turns a file-relative pointer (0x5... virtual, 0x6... physical)
into the delta to the chunk it was placed in. A pointer that is not in the map is fatal ("Invalid
fixup, address 0x2fff8000 is neither virtual nor physical"). Players hit it on two fences in the
Vinewood Hills (ch2_07_fence_03, ch2_07d_fencing_02), always with the same address: the start of
a chunk the resource itself had just been placed in, so the pointer was being fixed up a second
time. pg_fixup_already_placed answers delta 0 for an address inside one of the resource's placed
chunks (it is already right) and logs it; any other address still stops the game as before.
"""
from pathlib import Path
import re
root = Path(__file__).resolve().parents[1]
FUNCTION = '2092'
MARK = 'pg_fixup_miss('
OLD = '  var_B3:;\n  var_j0 = var_p0;\n'
V1 = '  if (pg_fixup_already_placed(instance, var_p0, var_p1)) { var_j0 = 0ull; goto var_B2; }\n'
NEW = ('  var_B3:;\n  { u64 pg_delta; if (pg_fixup_miss(instance, var_p0, var_p1, &pg_delta)) { var_j0 = pg_delta; goto var_B2; } }\n'
       '  var_j0 = var_p0;\n')
done = False
for path in sorted((root / 'Generated').glob('game_*.c')):
    s = path.read_text()
    found = re.search(r'^u64 w2c_game_f' + FUNCTION + r'\(w2c_game\* instance, u64 var_p0, u64 var_p1\) \{$', s, re.M)
    if not found: continue
    start, end = found.start(), s.index('\n}\n', found.start())
    body = s[start:end]
    if MARK not in body and V1 in body:
        body = body.replace(V1, NEW.split('\n', 1)[1].split('\n')[0] + '\n', 1)
        s = s[:start] + body + s[end:]
        path.write_text(s)
    elif MARK not in body:
        if body.count(OLD) != 1 or '1322386ull' not in body or '4120u' not in body:
            raise RuntimeError(f'Pinned f{FUNCTION} (datResourceMap fixup lookup) changed')
        s = s[:start] + body.replace(OLD, NEW, 1) + s[end:]
        include = '#include "game-fixup-guard-impl.h"'
        if include not in s: s = s.replace('#include "game-impl.h"', include, 1)
        path.write_text(s)
    done = True
    break
if not done: raise RuntimeError(f'Pinned function f{FUNCTION} not found')

# The same lookup is inlined into pgBase::pgBase (f2080, the page map pointer every resource starts
# with) and pgBaseMetaDataDebugNameType::Place (f2107, debug metadata). The fences' bad value
# 0xffff7fffffff7fff arrives through pgBase.
INLINED = {
    '2080': ('u64 w2c_game_f2080(w2c_game* instance, u64 var_p0) {', '  var_B6:;\n  var_j1 = var_l3;\n',
             '  var_B6:;\n  { u64 pg_delta; if (pg_fixup_miss(instance, var_l3, var_l4, &pg_delta)) { var_j1 = pg_delta; goto var_B5; } }\n  var_j1 = var_l3;\n'),
    '2107': ('void w2c_game_f2107(w2c_game* instance, u64 var_p0, u64 var_p1, u64 var_p2) {', '    var_B4:;\n    var_j1 = var_p2;\n',
             '    var_B4:;\n    { u64 pg_delta; if (pg_fixup_miss(instance, var_p2, var_l4, &pg_delta)) { var_j1 = pg_delta; goto var_B3; } }\n    var_j1 = var_p2;\n'),
}
for path in sorted((root / 'Generated').glob('game_*.c')):
    s = path.read_text(); changed = False
    for number, (head, old, new) in INLINED.items():
        if head not in s: continue
        start = s.index(head); end = s.index('\n}\n', start); body = s[start:end]
        if 'pg_fixup_miss(' in body: continue
        if body.count(old) != 1 or '1322386ull' not in body: raise RuntimeError(f'Pinned f{number} (inlined fixup lookup) changed')
        s = s[:start] + body.replace(old, new, 1) + s[end:]; changed = True
    if changed:
        include = '#include "game-fixup-guard-impl.h"'
        if include not in s:
            first = re.search(r'^#include "game-[a-z-]*impl\.h"$', s, re.M)
            s = s[:first.end()] + '\nextern u32 pg_fixup_miss(w2c_game *instance, u64 map, u64 address, u64 *delta);' + s[first.end():]
        path.write_text(s)
(root / 'Generated/game-fixup-guard-impl.h').write_text(
    '#include "game-impl.h"\n'
    'extern u32 pg_fixup_miss(w2c_game *instance, u64 map, u64 address, u64 *delta);\n')

# atArray<datOwner<grcTexture>> placement (f5710) constructs a texture for every entry.
# pg_texture_already_placed answers 1 for an address an earlier entry already holds (placed once),
# and 2 for an entry whose file pointer is in the physical (GPU data) segment: the Vinewood Hills
# fences' embedded texture dictionaries point a texture there, at pixel data, and constructing a
# texture from it read garbage and crashed. Such an entry becomes null (the texture is missing).
TEXTURE_HEAD = 'void w2c_game_f5710(w2c_game* instance, u64 var_p0, u64 var_p1) {'
TEXTURE_OLD = '      w2c_game_f9531(instance, var_j0, var_j1);\n'
TEXTURE_NEW = '      { u32 pg_t = pg_texture_already_placed(instance, var_p0, var_l4, var_j0); if (pg_t == 2) var_p1 = 0; else if (!pg_t) w2c_game_f9531(instance, var_j0, var_j1); }\n'
TEXTURE_V1 = '      if (!pg_texture_already_placed(instance, var_p0, var_l4, var_j0)) w2c_game_f9531(instance, var_j0, var_j1);\n'
for path in sorted((root / 'Generated').glob('game_*.c')):
    s = path.read_text()
    if TEXTURE_HEAD not in s: continue
    start = s.index(TEXTURE_HEAD); end = s.index('\n}\n', start); body = s[start:end]
    if TEXTURE_V1 in body:
        s = s[:start] + body.replace(TEXTURE_V1, TEXTURE_NEW, 1) + s[end:]
        path.write_text(s)
    elif 'pg_texture_already_placed(' not in body:
        if body.count(TEXTURE_OLD) != 1: raise RuntimeError('Pinned f5710 (texture array placement) changed')
        s = s[:start] + body.replace(TEXTURE_OLD, TEXTURE_NEW, 1) + s[end:]
        first = re.search(r'^#include "game-[a-z-]*impl\.h"$', s, re.M)
        s = s[:first.end()] + '\nextern u32 pg_texture_already_placed(w2c_game *instance, u64 array, u64 index, u64 address);' + s[first.end():]
        path.write_text(s)
    break

# pgBase::pgBase (f2080) writes the resource's page map into space the resource file reserved for
# it: counts at +8 (virtual) and +9 (physical), then one entry per page from +16. Some resources are
# placed in one page more than they reserved (the two Vinewood Hills fences: room for 4, placed in
# 5), and the extra entry overwrote whatever followed the map; for the fences that was their texture
# dictionary, and the game crashed at the end of Marriage Counseling. pg_page_map_reserved reads
# what the file reserved before the counts are overwritten; entries past it go to a side table
# (pg_page_map_store) instead of memory. pgBase::RegenerateMap (f2082), which the engine uses to
# free a resource, sees them through pg_page_map_swap: they are put in place for the call only.
PAGEMAP_HEAD = 'u64 w2c_game_f2080(w2c_game* instance, u64 var_p0) {'
PAGEMAP_LABEL = '  var_B7:;\n'
PAGEMAP_LABEL_NEW = '  var_B7:;\n  u32 pg_reserved = pg_page_map_reserved(instance, var_l1);\n'
PAGEMAP_SUM = '  var_i0 = var_l10;\n  var_i1 = var_l11;\n  var_i0 += var_i1;\n  var_l10 = var_i0;\n'
PAGEMAP_SUM_NEW = PAGEMAP_SUM + '  var_l10 = pg_page_map_entries(instance, var_l1, var_l10, pg_reserved);\n  var_i0 = var_l10;\n'
for path in sorted((root / 'Generated').glob('game_*.c')):
    s = path.read_text()
    if PAGEMAP_HEAD not in s: continue
    start = s.index(PAGEMAP_HEAD); end = s.index('\n}\n', start); body = s[start:end]
    if 'pg_page_map_entries(' not in body:
        if body.count(PAGEMAP_LABEL) != 1 or body.count(PAGEMAP_SUM) != 1: raise RuntimeError('Pinned f2080 (pgBase page map) changed')
        body = body.replace(PAGEMAP_LABEL, PAGEMAP_LABEL_NEW, 1).replace(PAGEMAP_SUM, PAGEMAP_SUM_NEW, 1)
        s = s[:start] + body + s[end:]
        first = re.search(r'^#include "game-[a-z-]*impl\.h"$', s, re.M)
        s = s[:first.end()] + '\nextern u32 pg_page_map_reserved(w2c_game *instance, u64 map);\nextern u32 pg_page_map_entries(w2c_game *instance, u64 map, u32 pages, u32 reserved);' + s[first.end():]
        path.write_text(s)
    break
PAGEMAP_STORE = ('    var_j1 = var_l2;\n    var_j2 = var_l6;\n    var_j1 |= var_j2;\n'
                 '    i64_store_shared(wasm_rt_local_memory_base, wasm_rt_local_memory_size, instance->w2c_env_memory, (u64)(var_j0), var_j1);\n')
PAGEMAP_STORE_NEW = ('    var_j1 = var_l2;\n    var_j2 = var_l6;\n    var_j1 |= var_j2;\n'
                     '    if (!pg_page_map_store(instance, var_l4 - 16, var_l1, var_j1, pg_reserved))\n'
                     '    i64_store_shared(wasm_rt_local_memory_base, wasm_rt_local_memory_size, instance->w2c_env_memory, (u64)(var_j0), var_j1);\n')
REGEN_HEAD = 'void w2c_game_f2082(w2c_game* instance, u64 var_p0, u64 var_p1) {'
for path in sorted((root / 'Generated').glob('game_*.c')):
    s = path.read_text()
    if PAGEMAP_HEAD not in s: continue
    start = s.index(PAGEMAP_HEAD); end = s.index('\n}\n', start); body = s[start:end]
    if 'pg_page_map_store(' not in body:
        if body.count(PAGEMAP_STORE) != 1: raise RuntimeError('Pinned f2080 (page map store) changed')
        s = s[:start] + body.replace(PAGEMAP_STORE, PAGEMAP_STORE_NEW, 1) + s[end:]
    if 'pg_regenerate_map_body(' not in s:
        if s.count(REGEN_HEAD) != 1: raise RuntimeError('Pinned f2082 (pgBase::RegenerateMap) changed')
        start = s.index(REGEN_HEAD); end = s.index('\n}\n', start) + 3
        s = (s[:start] + 'static void pg_regenerate_map_body(w2c_game* instance, u64 var_p0, u64 var_p1) {' + s[start + len(REGEN_HEAD):end]
             + REGEN_HEAD + '\n  pg_page_map_swap(instance, var_p0, 1);\n  pg_regenerate_map_body(instance, var_p0, var_p1);\n  pg_page_map_swap(instance, var_p0, 0);\n}\n' + s[end:])
    if 'extern u32 pg_page_map_store(' not in s:
        first = re.search(r'^#include "game-[a-z-]*impl\.h"$', s, re.M)
        s = s[:first.end()] + '\nextern u32 pg_page_map_store(w2c_game *instance, u64 map, u64 index, u64 entry, u32 reserved);\nextern void pg_page_map_swap(w2c_game *instance, u64 base, u32 in);' + s[first.end():]
    path.write_text(s)
    break

