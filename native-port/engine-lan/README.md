# zema engine LAN — native ↔ browser transport

The [Build 35 input and tools update](BUILD35_INPUT_AND_TOOLS.md) includes Build 34 and fixes stale browser input, native model-name truncation and delayed completion messages belonging to an older action. It remains one combined test build.

The [Build 34 connection recovery update](BUILD34_CONNECTION_RECOVERY.md) includes Build 33 and fixes concealed stalled sends, misleading connection-phase errors and delayed browser join-send failures. One Build 34 installation covers the combined test batch.

The [Build 33 core multiplayer batch](BUILD33_CORE_MULTIPLAYER.md) adds browser world tools, native spawn failure reasons and remembered relay/room settings. Its paired test checklist combines the new changes with names, movement and long-run checks.

The [Build 32 name-label repair](BUILD32_GAMER_TAGS.md) adapts glue5's movie layout correction to native and browser clients. The human has now reported paired player visibility; corrected name placement still needs a fresh visual test.

The [Build 31 Mod Manager update](BUILD31_WORLD_TOOLS.md) adds queued private-LAN vehicle spawning and waypoint teleport, with native signature checks and bounded destination loading. Paired runtime behavior still needs testing.

The [separate experimental game integration](EXPERIMENTAL_GAME.md) now connects
all 60 typed callbacks, checked Social Club tables, a shared durable browser
profile owner and the native profile host. Only the separately staged lab app
and browser enable these paths. They still require real gameplay, character
restart and paired iPhone/Mac verification. Earlier fixture receipts below
retain their original milestone scope.

The [2026-10-16 audit](AUDIT_20261016.md) adds a reversible Xbox-label option
inside Controls layout, same-session reconnect controls and save/memory safety
regressions. It also verifies real Chrome IndexedDB persistence using a private
disposable profile, without launching GTA or touching existing browser data.
The [three-style controls update](CONTROLS_APPEARANCE.md) adds PlayStation labels
and replaces the selector's two layered backgrounds with one background.
The [launcher correction](LAUNCH_MODES.md) restores Story and Free Roam alongside
optional Engine LAN, with separate offline launch routing in build 24.
The [build 24 feature audit](BUILD24_FEATURE_AUDIT.md) records the retention
matrix and restores the existing multiplayer settings as an alternate backend
in build 25, with explicit LAN capability messages.
The [Tailscale compatibility update](TAILSCALE.md) prepares explicit private VPN
IPv4 endpoints and a separately opted-in relay bind, preserving LAN operation.
Actual VPN transport and paired gameplay still need a human trial.
The [build 26 audit](BUILD26_AUDIT.md) corrects cancelled browser admissions and
silent-relay detection in native/browser transports, with a separate build 27.
The [build 28 profile startup correction](PROFILE_STARTUP_FIX.md) resolves only
the OS Documents anchor, retaining strict checks on profile data and showing the
installed build number. It still needs a real iPhone retry.
The [browser launcher update](BROWSER_LAUNCHER.md) adds pre-game graphics and mode
selection, protected offline save management and standard-controller PC-input
compatibility. It documents the native features that still need browser ports.

The current zema TrollStore IPA and its existing source/build tree are preserved.
All work here is isolated from `~/Documents/GTA-MP-IntelBuild/`. The existing
Intel Metal shader/reflection pair is reused unchanged for future native builds;
this transport does not change the renderer or compile shaders. It uses no paid
server, workflow, Apple account, new entitlement or subscription.

## Data path

```
native game socket hook → bounded Rust queues → Swift URLSessionWebSocket
                 ↕ explicit local Mac WebSocket relay ↕
browser network worker → shared queues → typed WASM socket hooks
```

The socket offsets and opaque engine DATA layout follow the pinned glue5
source at `a62e56a5b6423071c2f32c9c3446bca74734d9c3`. Attribution and the
source/interface pins are in [the integration handoff](../../docs/GLUE5_ENGINE_LAN_20261016.md)
and `../app/Tests/glue5_engine_lan_contract.json`. This is our explicit local
transport adaptation; it does **not** implement stock glue5's UDP HELLO/PEERS,
DHT discovery, NAT punching or LAN sweep. Sharing DATA framing alone does not
establish interoperability with an unmodified glue5 Android/desktop client.
No public discovery or external peer connection happens automatically.

`src/lib.rs` owns virtual addresses, bound ports, per-port datagram queues and
transport state. It has no dependencies and no network/file I/O. The C API
accepts frames only after explicit admission. Wrong destinations, self echoes,
invalid fields and packets above 2048 bytes are refused. Incoming/outgoing queues
are bounded at 256 frames each, with 128 handles and 32 distinct ports. Small
outgoing buffers do not silently lose a frame. Disconnect clears pending frames;
resume must retain the same address and relay epoch, otherwise restart is
required. Session identity is not silently replaced beneath a running engine.

`src/engine.rs` implements the eight virtual network hooks against the current
bounded memory provider. It validates memory ranges/overflow and preserves
original create/select/profiler calls. `EngineLanHost.c` provides typed callbacks
for the generated C adapter. The standard Xcode app target does not include or
activate this experimental backend. No original game C part is patched here.

`EngineLanSession.swift` and `EngineLanBindings.swift` connect the iPhone ABI to
the relay. Networking starts only on explicit `connect()`. Endpoints must be
local or Tailscale IPv4 WebSocket URLs ending in `/engine-lan`. Generation guards reject old
socket callbacks; sends and queues are bounded and stalled sends time out.
The resume capability is held only in memory, never printed or placed in saves.

`relay.py` has no dependencies. It assigns addresses, isolates rooms, validates
sender addresses, supports short same-address resumes and closes slow peers.
Its CLI binds only an explicitly selected local IPv4 address, defaults to
loopback and stops after a bounded duration. Browser origins are limited to the
local game origins on ports 18886 and the separate experimental 18887. Do not expose this trusted-LAN relay
to the public Internet. It serves no assets and accesses no application data.

## Browser engine and worker integration

`browser_wasm.py` requires the exact approved engine/reference hashes. It appends
original-function copies and typed table trampolines for the pinned socket hooks.
Existing function indices, imports, unmodified bodies, memory, data and shader
inputs remain intact. It supports the actual engine's 64-bit function table.
The WASM start function is deferred until typed callbacks have been installed.
This preserves WebAssembly signature checks; no unchecked indirect-call flag
or unknown-build override is introduced.

`browser.js` provides the socket callbacks, shared bounded queues and a client
with explicit connect/disconnect/resume. `network-worker.js` keeps WebSocket I/O
outside the blocked game worker. Each pthread receives the same shared queue
buffer; Select is awakened with Atomics rather than an event-loop polling guess.
There is no network or timer activity when these modules are merely imported.

The owned lifecycle extension pins `rage::netSocket::NativeShutdown()` at 184
with its exact name, signature and WASM body hash. Native shutdown preserves
the engine's socket lock; the browser calls the original shutdown before
reclaiming its virtual handle. Closing the last handle on a port discards that
port's incoming queue; closing an alias preserves its surviving peer's queue.
Closed handles and ports can be reused without exhausting the 128 handle / 32 port
live limits. Transport reconnects clear queued datagrams but retain socket
mappings. The browser feature stage adds this single hook after the historical
online transformation, preserving its original input pins and offline output.
Rebinding an existing socket to its same port (or port 0) succeeds without
allocating another handle or discarding queued packets; changing ports fails.
As with the engine itself, callers must serialize shutdown/reinitialization of
the same socket object; the browser preserves the original shutdown locking.

`stage_browser.py` checks exact hashes for the existing `game.js`, `loader.js`
and `io_worker.js`, and writes only separate ignored Build outputs. It wires
the owner worker and pthread instantiation paths. Both save restore and save
write use a separate experimental IndexedDB name. The original mirror,
BrowserLab sources, Story saves and working browser bridge are unchanged.

The real patched full `game.wasm` passes `WebAssembly.validate` in the existing
Node runtime. This does not execute the game. Synthetic WASM fixtures exercise
both 32-bit and 64-bit tables, typed Send/Receive/Bind calls and deferred startup.
No game code/assets are committed.

## Tests and reproducibility

Use only the already installed private Rust toolchain. No installation or
online dependency resolution is needed: this crate has zero dependencies and
its lockfile is committed. Keep Cargo/Rustup homes isolated as in the Intel
build handoff. All target outputs belong under `../app/Build/EngineLAN/`.

```
cargo build --offline --locked --manifest-path native-port/engine-lan/Cargo.toml \
  --target-dir native-port/app/Build/EngineLAN/RustHost
cargo test --offline --locked --manifest-path native-port/engine-lan/Cargo.toml \
  --target-dir native-port/app/Build/EngineLAN/RustHost
python3 -B native-port/engine-lan/tests/test_transport.py
```

The last command uses disposable **ephemeral 127.0.0.1 sockets**, never the
home LAN, iPhone or game. It builds/runs synthetic C/Swift/Node fixtures. The
native fixture uses the actual Rust C socket API and production Swift transport;
the browser uses actual patched synthetic WASM functions and the production
WebSocket client. Native→browser→native payloads pass through the real relay.
All owned fixtures and sockets are closed afterward. A sandbox may require
separate execution permission for localhost binds; that is not a game/device
verification result.

Additional checks: native unit tests; iPhone ARM64 library compilation using
the existing target; strict Swift type checking against both Mac and iPhone
SDKs; C host glue syntax against the real cached engine headers; browser shared
worker Select wakeup; bounded queues; stale callbacks; room isolation; spoofed
sender rejection; resume/expiry; masks/origin/frame limits; and the earlier
85-test offline app/adapter suite. Results are recorded with their actual scope,
not counted as on-device execution or completed GTA Online features.

The 2026-10-16 validation passed 12 new transport tests (including binary packets
with NUL and high-bit bytes), 8 Rust unit tests, the existing 85 Python tests,
62 Swift preference checks, 6 mod-error checks and the save round-trip harness.
The iPhone ARM64 library compiled; strict Mac/iPhone Swift checks, cached-engine
C checks and patched full-engine WASM validation passed. The compact receipt is
[tests/backend_validation.json](tests/backend_validation.json). Logs and staged
artifacts remain in the separate ignored Build directory; no game was launched.

## Historical transport milestone and rollback

At the original transport milestone, the remaining task was to connect the implemented 52 online-entry/character/stat hooks to their checked
host function-table and browser storage boundaries before enabling either
game-launch gate. The current
runtime and browser enforce indirect-call types; upstream's generic interface
stubs cannot simply be copied into those tables. Preserve type checking and
separate new profile storage while adapting them. Then build a separate
experimental IPA with the staged Intel inputs and verify real peer admission,
visible movement/rejoin and saved characters on the home LAN.

Rollback: stop the explicitly started test relay/client and keep using the
unchanged existing IPA/browser bridge. No original folder, app, save, trust,
billing, service, deployment or system configuration needs restoring.
