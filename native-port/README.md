# Mugoat · iOSVN

Mugoat is the native C/Metal variant requested for the Muguet project. It imports the GTA V Port host source at revision `2cf36db9ed719c8233008a1efeb80e24f99b0b16`, then changes app identity, interface and packaging. The engine and renderer are reused directly, not reimplemented behind similar-looking settings.

## Runtime

- Compatible engine bytes are translated with the pinned WABT `wasm2c-native` tool and compiled by Clang to ARM64. No Wasmtime or wgpu is linked into Mugoat.
- The dedicated Metal renderer, CPU BC1–BC7 fallback, measured device memory recommendation, 384 MiB streaming reserve and signed eviction budgets are inherited from the native host.
- Game shaders are translated and bundled in a `.metallib`; runtime pipeline creation still exists.
- FPS measures rendering submissions, with stale measurements expiring after a stall. It does not display the requested cap as a measured rate.
- A failed boot can lower graphics quality/resolution to a previously stable setting.

## Identity and compatibility

- Name: Mugoat. Interface brand: iOSVN. Bundle ID: `vn.iosvn.mugoat`.
- Version: 1.0.0, build 1. Target iOS 16.4 or newer, arm64. Lowering the original host's deployment target is a build compatibility experiment, not proof of performance on iPhone X or every iOS version.
- This installs alongside Muguet, keeping its data and saves separate. Import or select compatible game data containing `data/` and `b/8b0b5899ed/`. Files are validated before use. Saves are not automatically migrated; keep the old app and its files.
- Free Apple ID and extra-memory entitlement variants are packaged separately. Extra-memory support depends on the actual signing profile and device, not on an IPA filename or purchased certificate alone.
- Existing Muguet Rust multiplayer hooks are not part of this native variant. Built-in cheat utilities remain available. Generic Lua native APIs and arbitrary RPF/model/texture patching are not implemented in this build.

## Interface

The start screen has a dark teal/violet background, Mugoat/iOSVN header, game-data status, two mode choices and one main Play action. Graphics/FPS, touch layout and game utilities are grouped in a separate column. The main column scrolls on short displays. Graphics quality changes require relaunch; resolution and controls can change during play.

The icon remains the native Port icon as requested. Only Los Santos is exposed; the experimental map selector is removed and previously saved test-map selections resolve to Los Santos. The UI has a persisted Vietnamese/English selector on the home screen and in Settings. This selects the app's interface language; it does not translate GTA V's own game assets.

Save game shows existing files, modification times and sizes under the engine's Story/Free-roam save directories. A single action creates a checked `.mugoatsave` backup in Files › Mugoat › SaveBackups and opens the share sheet. Import is available before starting the engine, verifies all entries, rejects traversal/symlinks and corruption, backs up existing saves, and rolls replaced files back on I/O failure. It restores matching files without deleting other save slots. The app copies saves already written by GTA V; it does not claim to force an in-game checkpoint through an unavailable native API.

No log is uploaded by the app's support button; it opens the system share sheet so the player chooses where to save or send it. Optional diagnostic networking inherited from upstream remains disabled by default.

## Validation

The workflow checks streaming budget overflow/eviction boundaries, FPS and percentile accounting, generated native thread/runtime behavior, BC decoder parity, ARM64 compilation, signed IPA structure, and actual UIKit previews on small/large simulators. These checks do not verify gameplay on a physical iPhone. Compare with Muguet using identical game data, location, resolution, quality, frame cap, signing entitlement and thermal conditions.

Host license notices are preserved in `LICENSE` and bundled `Resources/Licenses/`. iOSVN is the interface/distribution brand, not a replacement for upstream code copyrights. No game textures, models, maps or licensed commercial content is committed to this source tree.
