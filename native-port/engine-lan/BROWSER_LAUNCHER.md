# Browser launcher, graphics, saves and controller compatibility

The local lab root on port 18887 is now a lightweight settings page. It contains
no engine Worker or WASM instantiation. Play explicitly navigates to a guarded
runtime page; that page requires a WebGPU adapter, shared memory and an exclusive
game lease before transferring the canvas or creating the loader. Engine LAN
also requires the admitted shared profile/network context. A failed admission
does not start the game. Existing caches are not unregistered or deleted.

Multiplayer is configured only in this launcher. Play automatically admits the
saved relay/room/player selection after the WebGPU and exclusive-game gates;
there is no second connection form. Failed or timed-out joins terminate their
workers and return to this launcher with the error and all bounded launch
preferences, including when preference storage is blocked. The game never starts
on a failed join. Leaving during admission cancels pending startup waits. Once
connected, only a small status/reconnect badge remains in play. The LAN loading
label says multiplayer rather than Story Mode.

## Settings coverage

The human clarified that browser parity excludes touch and gyro settings.
Native Icons/Xbox/PlayStation touch styles remain unchanged in the iPhone app.
The browser lists the remaining native feature categories honestly; listing a
feature does not establish an implemented engine callback.

| iPhone setting / feature | Browser behavior |
| --- | --- |
| Story / Free Roam | Explicit routes using the pinned original engine plus one controller hook, separate user databases and OPFS caches |
| Engine LAN | v7 loading observer over the preserved v5/v6 engine; existing explicit local/Tailscale IPv4 relay admission |
| Six graphics presets | Exact native quality option sets, shader quality 1, 432p through 2160p defaults |
| Resolution, screen shape, frame rate | Bounded fixed render size; 16:9 letterbox option; 30 / 60 / uncapped |
| Intel default | Performance, 540p, 30 FPS, two-core worker budget; no Retina auto-upsizing |
| Keyboard / mouse | Shared input-block adapter, mouse sensitivity and invert Y |
| External controller | Standard Gamepad API feeds native engine sticks, steering, buttons and analog triggers; physical play test pending |
| Camera / aim stick speeds | Separate browser controller look multipliers |
| Native assisted targeting | All four source-defined engine preferences, applied on the controller-update thread |
| Saves | List, individual/all export, checksummed import, atomic safety backup, export latest safety backup |
| Native backup / save folder interchange | Listed as unported; browser accepts its own bounded JSON archive only |
| Legacy UDP server / roles / PvP | Listed as unsupported by Engine LAN; not presented as working browser controls |
| Voice / wallet / purchases / inventory | Existing deferred integration boundaries remain open |
| Mod import / list / enable / disable / remove / DLC scan | Private open Legacy DLC RPF/ZIP imports, metadata/model validation, conflict detection and immutable offline overlays |
| Trainer / vehicle spawner / world effects | 29 source-defined English pad sequences and typed async model spawner; explicit offline requests only; gameplay effects unverified |
| RAM override | Chrome manages its allowance; native process-memory requests cannot increase it |
| Game files / preload / remove | Existing local mirror is used; native download management is not wired |
| Language / support | English UI and local launcher diagnostics export; no diagnostics upload |

This is not complete native/browser feature parity. Native-save conversion,
voice and legacy server roles remain unimplemented. The new controller, mod and
trainer paths have fixture and transform evidence; actual game effects, external
DLC compatibility and physical controller feel still need play tests. No
placeholder row is counted as a working feature.

## Controller behavior

The iPhone already maps `GCExtendedGamepad` buttons, both sticks and analog
triggers into `PGPadState`. That production mapping is unchanged. The host-side
virtual-controller test exercises its actual source and Apple framework.

The browser adapter accepts only standard-mapped controllers. Both sticks and
triggers retain proportional values in a bounded 256-byte shared pad buffer.
A seqlock and heartbeat reject partial or stale samples; blur, hidden-page,
disconnect and page exit publish neutral input. The hook runs just before the
original `rage::ioPad::UpdateDebug()` boundary, after normal input clearing,
and merges only primary pad 0. Inactive samples leave normal engine input alone.
The engine handles on-foot/vehicle actions without a manual context switch.
Keyboard/mouse input keeps its original block, text queue, wheel and fly aliases.
The gamepad does not synthesize WASD or mouse events. The in-game trainer panel
releases and suspends game input while its fields are being edited.

The extension changes only function 10454's body and appends one typed table
slot plus aliases for existing functions/TLS. All original function and type
indices and every other function body remain identical. The original start is
deferred until the callback is installed; existing LAN startup remains deferred
until its network/profile callbacks are installed too. Native iPhone controller
and all Icons/Xbox/PlayStation touch styles are unchanged.

## Mods and trainer

Mods are local private copies under `app/Build/BrowserMods-20261017`, with a
0700 root, 0600 catalog/archive files and atomic catalog replacement. Import
limits are 128 MiB per RPF / 256 MiB total / 16 packs. Open Legacy RPF7 packs or
ZIP bundles are supported; encrypted/Enhanced archives, scripts/plugins and
loose-file replacements are explicitly rejected. Archive structure, decoded
metadata, paths, resource versions and duplicate pack/model names are checked.
No imported code is executed and the original mirror is never edited.

Play creates an immutable offline snapshot at a random `/session/<id>` URL.
It preserves existing manifest indices and appends selected DLC entries.
GET/range/batch reads share the same overlay. Active mod configurations use
separate full-fingerprint game-data cache directories, so disabling a pack
returns to the unchanged original mode cache. A running snapshot survives
catalog toggles/removal. Up to four snapshots are retained until their tabs
release them or the local server ends. Story/Free Roam user saves remain mode
specific; a saved game can still reference a mod, so normal in-game save and
missing-model behavior apply. LAN always uses the original shared assets.

Trainer actions are visible before Play but cannot run there. The in-game
panel requires a loaded offline world and observed engine hook. It has 29
English cheat sequences and vehicle presets/custom model names. Requests run
on the engine's own controller thread, borrowing and restoring the active
script TLS for the asynchronous spawner. A delivered sequence does not prove
that the game accepted the effect. LAN rejects trainer commands in both UI and
the pinned engine host, including a forged offline context. No cheat is queued
at startup. See `BROWSER_TRAINER.md` for the exact protocol and source limits.

## Save boundaries

Story uses `zema-browser-story-userdata-v1`; Free Roam uses
`zema-browser-sandbox-userdata-v1`. Neither reads or migrates `gta5-userdata` or
`zema-engine-lan-userdata-v1`. Existing phone and browser saves are preserved.
No actual GTA save is invented. A new Story skips auto-load and does not delete
existing files. Saving new progress inside the game follows its normal rules.

The manager accepts only bounded `/userdata/Documents/` paths, excluding
`settings.xml`; refuses traversal, controls, duplicates and checksum mismatches;
and limits a backup to 256 files / 16 MiB. Restore validates all input first,
then reads originals, stores a safety copy and writes replacements in one
IndexedDB transaction. A write failure aborts the entire transaction. There is
no deletion button or automatic safety-backup pruning. Sixteen safety copies
are the limit; further restores are refused without changing data. The latest
nonempty safety copy can be exported and reimported. Save management refuses
to run while the lab game lease is held.

## Current verification and limits

- Existing regression suite: 80 tests passed in 108.763 seconds.
- New feature wrapper: four tests passed, including compilation/validation of
  both full engines without GTA instantiation, exact unchanged-body/index
  checks, ten typed-hook/shared-pad checks and fifteen trainer checks.
- Five real-mirror/v6-stage HTTP integration tests passed, using tiny synthetic
  DLC and disposable local storage/listeners. No external DLC/game was run.
- Targeted launcher and HTTP tests passed again after the final compatibility
  guard. An old v5 stage is refused explicitly by this launcher; it is preserved.
- The live local menu was checked at desktop and narrow sizes. Mods, trainer,
  controller preferences and all three game choices are present; the game
  remains stopped until Play. Physical controller feel, cheat effects, real
  third-party DLC loading, phone profile startup, frame rate and paired
  multiplayer remain unverified. These checks do not close those gaps.
- The 46 previously recorded IPA/shader/stage hashes and build 28's IPA hash
  were rechecked unchanged. No native source/app packaging was needed.

Earlier launcher baseline evidence (retained, not repeated as new proof):

- Full engine-LAN Python suite: 64 tests passed in 104.265 seconds. This includes
  the first three launcher tests. After adding the runtime-gate test, all four
  targeted launcher tests passed (65 distinct Python tests across the runs).
- Actual browser IndexedDB fixture passed: export/restore/checksums, atomic
  original backup, latest-backup export, injected-write rollback, active-game
  refusal, mode isolation and unsafe-path rejection. It uses random disposable
  names on a separate localhost origin and deletes only its own test databases.
- Native production controller mapping passed with an Apple virtual controller:
  face/shoulder/menu/D-pad buttons, optional thumb/options buttons, both sticks,
  analog triggers and merge behavior. The fixture must set the virtual D-pad
  through its axis setter; setting its individual child button is ignored on
  this Mac. This was a fixture correction, not a production mapping change.
- Desktop and narrow menu layouts were visually checked. Graphics selection
  updates the launch summary; root page remains stopped until Play. Actual GTA
  frame rate, physical controllers and paired multiplayer remain unverified.
- All 46 previously recorded IPA/shader/browser-stage input hashes matched.
  The older English checkout retains exactly its pre-existing Info.plist edit.

Build 28 was packaged before these browser edits from native source
`0895da37d3ad3fa30c7e87595dae993e4f11be46`. Its clarified artifact filename is
`Package-ProfileStartup-20261017/zema-EngineLAN-Build28-ProfileFix-Intel-TrollStore.ipa`.
IPA SHA-256: `c7ebf0525e30524ac9ae400691ecec202877f57973e5b7e7e3856421fc276b35`.
The filename change does not change IPA bytes. Strict ad-hoc signature and ZIP
CRC checks passed. It is not installed or device-verified. The human reported
the same profile error on build 27; build 28's bounded diagnostic is the next
phone evidence, without deleting app data. The browser launcher does not itself
fix or prove the phone profile startup.

No original Intel tools, generated C, shaders, mirror files or previous IPA were
changed. The browser uses its existing WebGPU mirror assets; the native IPA
reuses the pinned Intel Metal/reflection and compiled UI caches. No paid service,
hosted workflow, installation, account, port forwarding or global setting was
added. No UPM work, merge or device operation was performed for this update.

## Current local launch

Run from this GTA checkout (the menu is already served during this session):

```sh
python3 -B native-port/engine-lan/serve_browser.py \
  --mirror "$HOME/Library/Application Support/ZRemote Controller/Games/playgta5-offline/mirror/playgta5.com" \
  --stage native-port/app/Build/EngineLAN-FeaturesBrowser-20261017-v12
```

Open `http://127.0.0.1:18887/` in Chrome. Keep Performance / 540p / 30 FPS
and two workers for the first play test. Test a base Free Roam launch without
mods before importing a pack. For multiplayer, close the offline game tab,
select Engine LAN, and use the same relay/room as the phone. The new browser
stage does not fix or prove the iPhone's reported profile error.

The v6 offline engine SHA is
`1f9d0e01a1d715ba1d1fcb038996033898175a5c4084e24b8d71322cfd210afe`;
its LAN engine SHA is
`f56f0b487240933d3103a0b4aba86b136e357b96f8ab7961ea2d5386b188a698`.
The original mirror and v5 stage remain intact. Generated v6 artifacts and
private imports stay under ignored Build directories; source, tests and this
contract are kept in Git. `tests/browser_features_validation.json` records the
bounded verification result, separate from the historical launcher receipt.

## Multiplayer loading investigation

Human runtime evidence: Free Roam reached the game, while Engine LAN joined the
relay and remained at First frame / 76%. This narrows the failure to multiplayer
startup; active Chrome CPU usage did not establish that it was progressing.

The original GPU worker holds the HTML title cover until it sees a frame with
more than 300 draw calls and then waits for pipeline settling. That heuristic
is not an authoritative character-creation/menu readiness signal. The v7
follow-up screenshots show character creation rendering. Its first trace had
a prolonged CreateSamplerState wait, but later observations advanced to native
loading inactive and 411 draws/frame. A permanent sampler deadlock was not
established. Green/blue character skin remains a separate renderer defect.

The v7 stage additionally pins `CLoadingScreens::AreActive()` / function 34946,
whose 13-byte body reads the 32-bit native state at 19473636. Its SHA-256 is
`e26ef5d2ee14a038c89052fd37041a9098b62a653a9a8270064a7ce4430042dc`.
The existing controller callback only reads that state into unused shared pad
words. It never writes the engine's flag or calls shutdown. In LAN only, the
HTML cover can also finish after a presented frame, an observed active native
loading screen followed by 1.5 seconds inactive, and fresh engine observations.
Stale or missing observations, a still-active native cover, GPU loss or a
reported engine error cannot release it. A frontend-ready event is separate
from world-ready and is not evidence of a playable multiplayer session.

LAN now enables worker logs to the page and batches selected diagnostic text
only to the same loopback server. That server retains at most 1024 lines of
512 characters in memory; requests require the custom same-origin header and
are bounded to 24 lines / 64 KiB. No log file, credentials, memory dump, save
archive or external upload is made. Diagnostics include first callback names,
MainTransition patch matches/mismatches and native loading state/tick counts.
`/zema-lab/diagnostics` is read-only under the existing Host/Origin restrictions.
Restarting the local server discards the log buffer. A bounded private trace
was retained before activation. Repeated headblend/stall warnings are counted
per five seconds to avoid flooding the local queue. The actual Chrome game is
not exposed through the available browser automation; screenshots establish
character creation, not paired gameplay or correct skin output.

Both v7 WASM files are byte-identical to v6. Only reviewed helpers/metadata and
read-only observations changed. v5, v6, all IPAs and original Intel inputs remain
preserved. The prior fixtures and their receipts remain historical evidence.

## Browser renderer parity stage v8

See `BROWSER_RENDERER_PARITY.md` and `tests/browser_parity_audit.md` for the
source comparison, included changes and remaining gaps. v8 applies the exact
UNORM16 format when WebGPU texture-formats-tier1 is available; its absence is
reported explicitly and the old half-float fallback is not called faithful.
All modes receive the same staged GPU worker and boot in English. The two
small UI XML overlays are served in memory with unchanged lengths. No game
mirror, IPA or original Intel folder is edited.
