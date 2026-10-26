# glue5 adaptation provenance

OnlineCallbacks.c, online.js and their interface bindings adapt behavior and
interface layouts from mempage4k/glue5 at commit
`a62e56a5b6423071c2f32c9c3446bca74734d9c3`, specifically
`crates/glue5-runtime/src/{online,cloud,stats}.rs` and the corresponding
`crates/glue5-game/hooks/` files. The name-label layout repair in
`ZemaGamerTagLayout.h` and `gamer_tags.js` additionally adapts
`crates/glue5-runtime/src/gamer_tags.rs` from that same pinned revision
(SHA-256 `6998d0b6a16350f76947f19b21c2b6612a1015c5ea8657905fb3577b61f24306`). The exact original file hashes are retained in
`../app/Tests/glue5_engine_lan_contract.json`.

Source: https://github.com/mempage4k/glue5

The pinned workspace declares **MIT OR Apache-2.0**. This adaptation uses the
MIT option. The pinned tree did not supply a separate license/notice file.
Original glue5 authorship remains credited here; zema is the downstream app's
branding and does not replace upstream attribution. The enclosing downstream
source remains governed by its existing GPL-3.0-or-later license.

MIT License — glue5 contributors (mempage4k/glue5)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

## October 2026 source review

Independent depth/stencil invalidation in `browser_gpu.py` follows the separate
aspect tracking reviewed in c22dev/muguet revision
`1b4600b052b864c78fe36180073ff406663b7e0b` (`src/gpu.rs`, GPL-3.0).
Source: https://github.com/c22dev/muguet/tree/1b4600b052b864c78fe36180073ff406663b7e0b

Mod changes deferred until restart, interrupted-read handling and removal of the
per-file unoptimized engine build were informed by kevinerikjs/gta5-ios-port
revision `8e2e46281159d09005fea4748b5b9926e919fc0a`. The queue, guarded I/O helper
and reuse-flag verification are downstream implementations; no IPA executable
code was copied. Source inventory and hashes: `tests/upstream-review-20261021.json`.
Source: https://github.com/kevinerikjs/gta5-ios-port/tree/8e2e46281159d09005fea4748b5b9926e919fc0a

## Shared engine guards and limiter waits

The exact deleted-entity, dependency-descriptor and destroyed-phase guards, and
the reset-lock/context-lock flush ordering in engine_safety.py and
NativeEngineSafety.h adapt the gta5-ios-port scripts/RenderListGuard at
8e2e46281159d09005fea4748b5b9926e919fc0a. Its complete MIT notice is already
retained in app/Resources/Licenses/Native-Port-MIT.txt (byte-identical to the
reviewed upstream LICENSE).

Skeleton/dependency budget protection and reducing limiter busy-waits follow
Glue 5 runtime/src/draw_lists.rs, frame_pace.rs and waits.rs at
3c422f43560ad6e2abfe5d2ef07ab83d5d3729c6, GPL-3.0. The bounded micro-wait
keeps this port's existing limiter and cap, and uses its existing futex.
Audio waits reuse the existing elapsed sample and wake at the original
EndDraw counter increment, without importing Glue 5's thread-local hook system.

The browser's dependency-function check uses the standard WebAssembly typed
reference test, with no invocation of a job to test it:
https://github.com/WebAssembly/gc/blob/main/test/core/gc/ref_test.wast

## Single-file Story save import

The SGTA5 title header, Default profile directory, and manual-slot numbering
follow `app/App/SaveImport.swift` from kevinerikjs/gta5-ios-port at
`8e2e46281159d09005fea4748b5b9926e919fc0a` (MIT notice retained above).
`StorySave.swift` and `browser-saves.js` independently add bounded reading,
empty-slot selection, exclusive writes/transactions, and preservation of
autosave and existing backup files. Header validation does not convert saves
from newer game versions or establish that a particular save loads in-game.

## Visibility-scanner event wait

The bounded scanner event wait adapts Glue 5 `runtime/src/waits.rs` at
`3c422f43560ad6e2abfe5d2ef07ab83d5d3729c6` (GPL-3.0). This port scopes it
to the one pinned BuildRenderLists poll call and keeps all other event callers
unchanged. Existing scanner completion counters, event state and notification
path remain authoritative; a timed-out wait never marks the scan complete.

## Glue 5 resource reclamation and control scheduling (24 October 2026)

Adapted from mempage4k/glue5, GPL-3.0, revision ed3d31bf3c84eddbc6fab39227490db6f0b097de. Resource page lifecycle: commit 950a8ab5235c412fead3805b7b5f25e6072ff49c, crates/glue5-runtime/src/memory.rs. Exact control-thread classification: commit b5d1fafd5927489d6e445d9adf201f06282ca7c8, crates/glue5-runtime/src/threads.rs. Original copyright and GPL notices remain in the retained upstream reference and project LICENSE. This native C adaptation retains the port's existing dynamic memory-pressure policy; no upstream game files or binaries are included.
