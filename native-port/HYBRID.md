# Mugoat native integration

The release entry point is `.github/workflows/build-game-ipa.yml`, which calls
`build-mugoat-native.yml`. Root Rust/wgpu sources remain for reference and
protocol reuse, and are not the release engine.

`app/Scripts/prepare_online_exports.py` validates required multiplayer natives
and exports typed aliases. It does not add imports or change function indices:
the Port patches for pad 0, memory budgets, movies and missing dictionaries
still target the pinned original functions. All non-export WASM sections are
asserted byte-identical. `prepare_online_c.py` generates typed C dispatch from
the actual wasm2c header and inserts hooks in the original game-thread bodies.
Missing mandatory natives, wrong signatures or unmatched hooks stop the build.

`online-bridge` reuses `src/mp.rs`, `src/proto.rs` and `src/server.rs`. Its only
external crate is anyhow. The FFI facade checks value tags/arity and memory
accesses check overflow and the current mapped size. Entity changes run on
the engine's script thread; UDP threads do not call game functions. Offline
hooks return immediately and do not create network threads or replica state.

`DragCamera.swift` tracks each camera/Aim/Fire finger independently. Port's
movement stick and contextual buttons stay intact. Relative motion is queued
in the host and consumed in `pg_virtual_pad_apply`, rather than overwritten
by UIKit's next poll. The engine sees its normal pad 0, preserving targeting
assistance. The helper bounds the frame interval and rejects non-finite input.

Minimum deployment target is 16.0 in the project, preview and shader compiler.
Do not lower a finished binary's minimum-OS metadata: rebuild its dependencies.
Use the existing green V on black at `../assets/mugoat_logo.png` for both asset
catalog consumers. Preserve third-party license notices bundled in the app.

Validation covers native FFI, shared-memory boundaries, UDP join/relay/leave,
code-generation signatures, touch-motion lifetime, 30/60/120 Hz mappings,
streaming-budget arithmetic, FPS accounting, save integrity, futex runtime and
BC decoding. Physical-device frame pacing, thermal behavior, Jetsam recovery
and full multiplayer gameplay are separate from these build-time checks.
