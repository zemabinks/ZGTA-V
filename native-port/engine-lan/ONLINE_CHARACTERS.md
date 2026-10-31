# Engine-LAN entry and character callbacks

This milestone follows transport commit `160dcdb2999427b883a57f596e04bea8c4cc2908`.
It does not change the existing IPA, app target, generated game C, original
Intel folder, shaders, Story saves, browser mirror or existing multiplayer bridge.

## Implemented boundaries

All 52 pinned non-socket interfaces have strictly typed native declarations,
original-function adapters and callback routing. Native C implements local
gamer identity, online-entry gates, scoped LAN/stat operations, profile status,
local member-file reads/writes, grow-buffer naming, missing/packed stats and
float-bit/masked-value preservation. Existing engine stats keep their original
behavior; supplemental storage is used only when an engine lookup reports a
missing key. A bounded packed-miss cache follows the actual engine map revision,
avoiding repeated formatting/error output for absent stats.

Only the known hardware-offline bail is ignored. Real ROS credentials are not
invented; validity is supplied only within the local stats operation, restored
for nested calls. No official service is contacted. Script changes require the
exact MainTransition name, offset, page bounds and original bytes. Mismatches
are left untouched. Store catalog state is local/empty; UGC is unavailable.

`ZemaLanAttachOnlineEngine` binds the real pinned C originals and callback table
only when explicitly supplied a complete profile/interface/allocator host.
It is absent from the standard app's startup path. There is no untyped generic
function-pointer fallback or disabled WASM type check.

`online.js` implements equivalent callbacks. Tests call all 52 through typed
WASM exports, including i64 BigInt and float ABI boundaries, and read the exact
snapshot saved by the compiled C/Rust/Swift fixture. This is a single-owner
browser profile implementation; it is not yet a pthread-shared storage host.

## Profile and disk safety

The dependency-free Rust profile store has stable local identity, exact file
keys, supplemental stat bits, bounded record/file/total sizes and deterministic
binary snapshots. CRC32 detects accidental corruption; it is not authentication.
Import rejects duplicates, noncanonical order, traversal-like keys, invalid
identities/types, truncation and checksum failures before changing state. Import
is restricted to initialization, not a live replacement of modified data.
No filename sanitization silently merges distinct file paths.

The explicit Swift disk host uses a new caller-selected `zema-engine-lan-*`
directory, 0700/0600 permissions, regular user-owned files, symlink refusal,
bounded reads, temporary exclusive writes, fsync, atomic replacement, an exact
before-write comparison and a previous-good snapshot. It never selects a backup
automatically. This is a single-writer store, not an adversarial concurrent-writer
filesystem lock. Network/auto-save/migration are not started by importing it.

A member-file save reports success only after the supplied durable host returns
success. Failed commits retain the dirty in-memory data for a later explicit
retry and report failure to the game. Existing disk bytes remain available.
Native and browser encode the same character-file/stat format byte-for-byte.

The restart regression caught Foundation turning an existing `/private/var`
path into its `/var` symlink alias during standardization. The implementation
now preserves and checks the explicit path instead of weakening symlink checks.

## Remaining game integration at this historical milestone

The later [experimental game integration](EXPERIMENTAL_GAME.md) addresses the
table, shared-storage and launch wiring below. This record preserves the
callback-only milestone at `f85873812fc58ba4b7d6d8f6a96d1729f9c5d09e`.

Game readiness remains **false** on both platforms. No full game, iPhone or
four-platform runtime result is established. Remaining work:

1. Install verified Social Club interface objects with a correctly typed entry
   for every reachable virtual method. Cached C confirms profile sign-in uses
   `u32(void*,u64)` while GetSignInInfo uses `u64(void*,u64,u64)`; a single generic
   callback does not satisfy both. The supplied `prepare_interfaces` boundary
   deliberately refuses to guess on behalf of a real game host.
2. Bind shared, durable browser profile storage across the owner worker and
   pthreads. The current socket worker remains the accepted transport-only
   version; no in-memory-only save is labeled durable.
3. Connect the engine allocator, launch arguments and exact-length broadcast
   data configuration, then build separate experimental artifacts using the
   already verified Intel Metal pair. The current game C patch plan is unapplied.
4. At home, test actual character creation, saved-character restart, peer
   admission, visible movement and reconnect. No device action is needed now.

## Validation and rollback

`tests/test_online_callbacks.py` compiles synthetic originals with the production
C callbacks, real Rust profile library and production Swift disk host. It uses
only temporary private directories, no game engine or network. It checks a new
process restoring saved binary data, deterministic no-op save, previous-good
backup, corruption/permissions/symlink refusal, valid-checksum malformed records,
native/browser format parity and 52 typed browser callbacks. Rust unit tests,
strict Mac/iPhone SDK checks, ARM64 C objects/library and the previous offline
regressions are checked separately. Final execution passed **8 new callback
tests, 12 transport tests, 85 existing Python app tests and 11 Rust tests**, plus
62 Swift preference checks, 6 mod-error checks and the save harness. All three
ARM64 C objects and the Rust iPhone library compiled; strict iPhone Swift type
checking passed. The desktop fixture compiled with warnings treated as errors.
See `tests/online_validation.json` for the actual scope and hashes.

Rollback is to keep using the untouched current IPA/browser bridge. The new
code is isolated and not enabled by the standard app target. Disposable test
data may be left aside; no existing build, profile, trust or setting needs
restoring. No paid service, hosted build, installation or device action is used.
Upstream attribution is retained in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
