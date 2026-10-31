# Compatible map symbols — Build 53

The supplied minimap movie exposes 426 sprite names. Several modern online
scripts request newer sprite IDs, so the original setter rejects the request
and leaves an ordinary dot. The owner approved matching built-in GTA symbols
when the exact modern artwork is absent.

`app/Source/BlipFallbacks.json` is the shared list of 19 approved substitutions.
Run `app/Scripts/generate_blip_fallbacks.py --check` to verify the generated C
and JavaScript tables. Existing nonzero engine results always take priority.
On a miss, the bridge looks up the compatible ID in the engine's own initialized
table and checks the exact NUL-terminated asset name before returning its
engine-owned pointer. It does not rewrite game memory, marker IDs, names,
colours, scripts or original asset archives. Unknown requests remain unchanged.

The native pinned getter mutates its input argument during its binary search.
Its adapter now preserves the caller's original reference before the search;
the fixture compiles and executes the actual generated getter to cover this.
Bounds, corrupt names/pointers, valid original priority, logging failures and
all 19 routes are covered by the browser/native regression fixtures.

## Chrome observations, 21 October 2026

Tested the real browser engine in isolated room `QA-MAP-ICONS`, not the shared
ZRemote relay. The map and legend displayed Lamar's L, Maude's bounty symbol,
Ron’s contact symbol, garage symbols for LS Car Meet/Luxury Autos, business
symbols, race flags and older heist symbols. Names and colours remained visible.
The first Lamar candidate (`radar_lamar_family`) drew an F in this old movie;
the final route uses the visually confirmed L (`radar_lester_family`). Asset
names alone were therefore not treated as proof of the displayed artwork.

The focused suite has 61 distinct checks: 48 existing browser/text/native
checks, three new compatibility tests, and ten local HTTP tests. The initial
combined run caught a stale fixture after the Lamar correction; the corrected
three-test suite passed. The other 58 checks passed.

## Acceptance limits

These are compatible older symbols, not the exact modern console artwork.
The native adapter is covered by the real-getter harness; physical iPhone
appearance still requires testing the packaged build. No FPS improvement or
complete multiplayer recovery is claimed. Unseen missing text and NULL sender
metadata remain separate open investigations.
