# Exact map artwork from the FiveM reference — candidate 55

The official blip reference supplies actual 32×32 images for the missing modern
markers. The previously examined decompiled minimap export instead embedded
placeholder textures for the sampled symbols. This candidate imports 22 actual
reference images, with recorded URLs and hashes in
`app/Resources/ModernBlips/catalog.json`.

`app/Scripts/build_modern_blips.py` encodes their pixels as standard premultiplied ARGB
DefineBitsLossless2 bitmaps with one clipped bitmap-filled rectangle per icon.
Build 54’s row-run vector shapes worked in the full map atlas but disappeared
in the pause-map preview and legend. The bitmap path fixes both UI passes; no
second archive or legend script modification is needed. It appends definitions
and export names, and extends only the pinned `Blips.getListOfBlips` method with
sparse numeric members. All 426 original array entries remain unchanged; 22 new
IDs are added. Unused IDs remain undefined. The existing engine initializer
skips undefined array entries, retaining its normal name lookup and rendering.
No new WebAssembly hook, allocator, input injection or per-frame polling is used.

The generator creates a reproducible binary delta for the pinned original RPF.
It changes one encrypted 16-byte table row and appends the updated minimap movie.
Every other original archive byte is retained. Runtime consumers verify both
the original and final SHA-256, size limits, edit bounds and exact prior bytes.
No original game file is modified. The delta grows a temporary archive from
720,896 to 786,782 bytes and does not download the game.

The browser serves the matching manifest and explicitly refreshes this one
archive to bypass obsolete OPFS blocks; other game and save caches are retained.
Offline mod snapshots inherit the matching manifest. Native local-game startup
creates an equivalent manifest/file override, with original indices and other
mod overrides retained. A one-time immutable native reader verifies the overlay
hash and size even if Settings previously initialized the old manifest. It does
not rewrite old packed-cache blocks or mutate active cache indices. Custom
minimap archives take priority. Stream-only iOS
startup currently retains the built-in alternatives; exact artwork there is
not implemented by the local-file overlay and remains a separate gap.

## Verification boundaries

The pixel decoder, bitmap pixels and geometry, actual pinned AS2 array bytecode, original-entry preservation,
sparse IDs, exports, delta integrity, manifest indices and compiled Swift
application of the same delta have automated checks. Browser visual acceptance
and physical iPhone appearance must be recorded separately. Do not label this
candidate visually verified merely because those offline checks pass.

Build 55 passes 74 distinct focused checks: 63 source/native/worker checks
and 11 disposable loopback HTTP checks. The
generator reproduces the bundled delta exactly. An independent SWF bitmap decoder
checks every premultiplied ARGB pixel and the bitmap fill transform of all 22 icons. Compiled Swift and
Objective-C fixtures verify delta parity, source/custom-mod preservation,
preloader size compatibility, tail reads, bounds and corrupt-input refusal.
All browser modes and mod snapshots serve matching full/ranged archive bytes
and manifest lengths.

Chrome follow-up on 21 October 2026: a fresh isolated game reached the world.
The Build 54 map displayed LD but modern legend slots were blank. Temporary
source diagnostics established correct names, instantiated clips, 16×16 bounds,
full opacity, visibility and valid final transforms. Importing or duplicating
vector symbols into other movies did not fix the blank UI pass. Those diagnostic
assets are not shipped. Re-encoding the same source pixels as embedded lossless
bitmaps fixed the map preview, full map and legend using only the minimap delta.

Screenshots under `verification/map-icons-20261021/` show 16 distinct modern
symbols in the live legend, including casino, comic store, skydiving, Lamar,
three heist variants, LS Car Meet, both showrooms, Maude, Miguel’s heist prep,
RC time trial, movie collectibles, Ron and SecuroServ. Automated bitmap checks
cover all 22 packaged variants; not every conditional marker was live in this
session. Selected Ron and Lamar contacts retained readable detail panels and
correct colours. Physical iPhone appearance remains untested. Earlier startup
stalls, including stalls on the original archive, are not claimed fixed.
No matched FPS improvement or completed multiplayer recovery is claimed.

For an isolated browser comparison, `serve_browser.py --original-map-icons`
retains the installed archive and its original manifest size. Restarting the
helper only changes the test launcher's in-memory overlays, never the mirror.

FiveM's reference is used for symbol IDs and artwork only. It is not evidence
that unsupported FiveM runtime features work in this port. Existing unseen text,
NULL sender metadata, startup stalls and full gameplay reconnect remain open.
