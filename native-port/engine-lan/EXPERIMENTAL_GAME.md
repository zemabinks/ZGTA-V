# Separate experimental Engine LAN game

This batch connects the game host to the earlier transport and 52 online,
character and stat callbacks. It prepares a separate local iPhone build and
browser launcher. **Actual game entry, character creation/restart, two-player
movement and reconnect remain unverified.** No fixture result is gameplay proof.

## Interface and save wiring

Four reserved role slots resolve to entries matching the exact requested WASM
signature before the original indirect-call check. Ordinary indices and wrong
role/signature pairs keep trapping. Native C uses the real type hashes and
prototypes; browser no-op/SIMD stubs remain in WASM rather than crossing the JS
ABI. The exact engine decoder rewrites 91,659 indirect-call sites without
changing original function/type indices. Both rewritten full modules validate.

The host installs checked interface objects using the pinned engine allocator.
Sign-in results include the durable local profile identity. This is explicit
local LAN identity, not an official service account or a claim that all Social
Club methods are implemented. The upstream no-op role remains a typed stub.

One dedicated browser worker owns the profile and IndexedDB. Every engine
thread shares the same bounded RPC buffer and serialized save operations.
Interface readiness and new-character masks are shared rather than copied into
conflicting thread-local state.
Saves acknowledge only a completed strict-durability transaction. Current and
previous bytes are retained atomically, unexpected disk changes are refused,
and corrupt data is not replaced or silently recovered. The tests exercise
four writers and restart through the same RPC using a disposable filesystem
adapter. That earlier fixture limitation is now superseded by the disposable real-Chrome
profile audit in [the audit record](AUDIT_20261016.md). Actual game saves remain
unverified; the historical fixture receipt is retained unchanged.

Browser profiles use `zema-engine-lan-profiles-v1`; engine user files use
`zema-engine-lan-userdata-v1` on a separate origin, port 18887. Native profiles
use Documents/zema-engine-lan-profile-v1 in the new app container. No existing
Story save, app container, browser mirror or original asset file is migrated.
An exact-length, validated in-memory gameconfig overlay supplies the same
broadcast capacities to both clients; GET ranges and batch asset reads agree.

## Intel build and separate package

`prepare_experimental.py` stages new AppRoot sources and APFS-cloned verified
cached dependencies. It refuses changed source anchors, engine ABI or shader
inputs. The native generator adds 1,979 typed table entries and patches only
the stage. The ordinary app target and original Intel build remain unchanged.

The combined `engine-lan-lab` Rust archive links the existing online bridge and
new backend with one Rust runtime, using the existing private toolchain and
locked offline inputs. The staged Xcode project excludes source asset catalogs
and reuses the compiled device catalog and Metal pair. No new shader compilation,
package download, hosted runner, paid service or Apple account is required.

The separate app is **zema Engine LAN Lab**, bundle
`com.zemabinks.gtamp.enginelanlab`. The original experimental package is build 21;
the separate audit package is build 22. Its TrollStore package requests
only the original increased-memory and extended-address-space entitlements.
Ad-hoc signature verification establishes package integrity, not actual memory
grants on a phone. The original IPA is never an output target.
The current connection-audit correction is build 27 in
`Package-ConnectionAudit-20261017`; see [the build 26 audit](BUILD26_AUDIT.md).
Earlier packages remain preserved. The current native retry is build 28 in
`Package-ProfileStartup-20261017`, correcting [profile startup](PROFILE_STARTUP_FIX.md).
It uses the same v5 browser stage as build 27.

`build_experimental.py` checks staged source bytes, requires a committed source
revision, runs the existing two-job local Xcode command, rejects unexpected
shader/catalog compilation and records exact source/input/executable hashes.
`package_experimental.py` requires that successful receipt, verifies cached
resources, copies into a new Payload directory, retains attribution, signs,
checks the real entitlement plist and tests the IPA archive CRC. Existing
package outputs are refused rather than overwritten. Build products, executable
game data and all user files remain ignored local outputs.

## Paired test when back home

Use the same explicit Mac LAN IP and room on both clients. The experimental
relay is separate from the existing snapshot bridge; it does not communicate
with an unmodified stock glue5 Android/desktop client or use public discovery.
Do not expose it publicly. Private remote play uses the separate explicit
[Tailscale procedure](TAILSCALE.md) after the LAN trial. From this repository,
in separate terminals:

```sh
python3 -B native-port/engine-lan/relay.py --bind YOUR_MAC_LAN_IP --port 47540 --duration 1800
python3 -B native-port/engine-lan/serve_browser.py \
  --mirror "$HOME/Library/Application Support/ZRemote Controller/Games/playgta5-offline/mirror/playgta5.com" \
  --stage native-port/app/Build/EngineLAN-FeaturesBrowser-20261017-v12
```

Open `http://127.0.0.1:18887/` in Chrome, enter
`ws://YOUR_MAC_LAN_IP:47540/engine-lan`, room `LOS-SANTOS` and a player name,
then connect. Preparation and networking begin only on that button. In the
separate iPhone lab app, import/select your existing lawful game assets, open
Engine LAN, use the same endpoint/room, connect and tap Play.

First establish character creation and saved-character restart on each client.
Then check both peers see movement, and a short same-session reconnect. Do not
replace or delete a working app/save if entry fails; retain the exact error.
For a short disconnect, use **Settings → Engine LAN → Reconnect same session**
on iPhone, or the browser's **Reconnect** badge. The reservation lasts 20 seconds;
a changed relay epoch or expired reservation requires restarting the lab client.
Do not change the relay or room underneath a running game.
No installation, game launch, phone access or home-LAN service was performed
by this preparation batch.

## Validation and rollback

The current batch's fixture results and exact log hashes are in
`tests/experimental_validation.json`. They include native checked-dispatch traps,
real typed WASM dispatch, concurrent shared-save restart and external-change
refusal, explicit launcher sequencing, fixed-length asset overlays and disposable
loopback HTTP ranges/batches/path checks. Existing callback, transport, Rust and
offline app regressions also pass. Full native build/package receipts are kept
next to the local artifact, separate from fixture evidence.

Rollback: stop only the explicitly started experimental relay/server, close
port 18887 and keep using the untouched current IPA/browser bridge. The new
bundle ID can coexist; no original folder, profile, trust, billing, deployment
or other service setting needs restoring. Attribution remains in
THIRD_PARTY_NOTICES.md and in the package.

The current menu uses the v6 controller/trainer extension of the preserved v5
stage. See `BROWSER_LAUNCHER.md` for offline mods, analog input and verification
limits. Historical v5 transport/ABI evidence above is retained.
