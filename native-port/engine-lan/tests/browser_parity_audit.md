# Browser/native parity audit — 2026-10-17

This is source and public-upstream research, not a gameplay pass. The human's
new screenshots show a rendered multiplayer character creator with corrupt
green/blue skin. They establish progress beyond the earlier loading image;
they do not establish a joined peer, correct character saves, or a working HUD.
The creator normally has no gameplay radar, so the reported missing minimap
also needs an in-world comparison after the renderer fixes.

## Sources and freshness

- Local Glue 5 reference: `a62e56a5b6423071c2f32c9c3446bca74734d9c3`.
- Public GitHub API checked read-only during this audit: Glue 5 main was
  `b5b05d6b04d91b6b6f6162902c21cbfd744c07bc`, eleven commits ahead.
  [Exact comparison](https://github.com/mempage4k/glue5/compare/a62e56a5b6423071c2f32c9c3446bca74734d9c3...b5b05d6b04d91b6b6f6162902c21cbfd744c07bc).
  No checkout was fetched or updated. There were no additional GPU/minimap
  renderer commits among those eleven; the older pinned renderer already
  contains several fixes that this browser's original worker does not.
- Mugoat pinned upstream is `6f061d12c58c23dbf99da7d4225996a6d586ab89`.
  The public `iOSVNNews/mugoat` commits API returned HTTP 404 during this
  audit. The public web page was readable through a cached primary-source
  response, but its live main revision could not be established. Do not
  describe the local Mugoat tree as verified latest.
- Local Mugoat source and the existing IPA-retention receipt are stronger
  inputs for porting source logic than guessing code from the submitted
  Mach-O packages. No new IPA extraction or execution was performed here.
  `native-port/app/Tests/trollstore_feature_validation.json:1` explicitly
  separates source retention from device runtime proof.

## Applicability matrix

The status below describes the baseline inspected for this audit. Parallel
implementation work may add a separately tested adaptation afterwards.

| Area | Source evidence | Browser applicability and remaining work |
| --- | --- | --- |
| Minimap geometry-stage coverage | Glue 5 `376afde`, `crates/glue5-gpu/src/shader.rs:333`, `:865` | Direct WebGPU translation candidate: radar pixel input location 5 is supplied by an unsupported geometry stage; zero values make it transparent. Apply only to exact radar shader/signature, not all shaders. |
| HUD radar mask vs pause-map exploration | Glue 5 `2272c55`, `shader.rs:482`, `:885`, `minimap_mask.wgsl`, `draw.rs:884` | Direct candidate requiring both mask coordinates and draw-state classification; a blanket fullscreen/blit replacement would break the pause map. Shader/pipeline fixture and actual HUD view remain separate requirements. |
| Dark interiors | Glue 5 [`df89ccd`](https://github.com/mempage4k/glue5/commit/df89ccd510ffc96abc544d89354fdf52d96c698b), `crates/glue5-gpu/src/ops.rs:147` | Confirmed semantic mismatch in original browser worker: stencil proxy is `r8uint`, whereas the D3D view's stencil is read from green. Use `rg8uint` and duplicate stencil into x/y. This explains lost interior lighting, not by itself the neon skin. |
| Corrupt dynamic textures / memory-file names | New Glue 5 [`0db284d`](https://github.com/mempage4k/glue5/commit/0db284d99ddc2b36291c4a29b17ad69bd93c5bb5), `crates/glue5-runtime/src/files.rs` | High-priority source candidate. `MakeMemoryFileName` emits `%p` with `0x`, but the engine parser reads raw hex, so files can resolve to address zero. Upstream lists texture stores among affected users. Browser already adapts grow-buffer names but lacks this new global memory-file hook. Relevance to headblend skin is plausible, unproven until exact signature/body and rendered output are checked. |
| Character/headblend rendering | Screenshot evidence; original browser shader/worker and native generated source | Root cause still requires tracing. Do not add skin recoloring or force a skin tone as a workaround; compare missing render passes, memory-file naming, and bindings. A successful character menu is not correct texture output. |
| Shadow flicker / stationary cloud shadow | Glue 5 `0eac477`, `8e601af`, `crates/glue5-runtime/src/shadow_reveal.rs` | Engine hooks bridge globals to older effect-local variables. Portable in principle, but requires exact exported original functions, addresses, variable-name guards and typed callbacks. Not a drop-in JavaScript/Rust file copy. |
| Depth output without attachment / M1 Metal compiler | Glue 5 `1214ce5`, `shader.rs`, `pipeline.rs` | Depth-output removal is relevant to WebGPU pipeline validation. Opaque per-sample input rewrite specifically addresses Apple's M1 native Metal compiler; this Intel Mac is not evidence for that issue. Port only with a matching failing shader and variant tests. |
| Resize: stale depth/SSAO bindings | Glue 5 `6c0c66b`, `a8f0816`, `crates/glue5-runtime/src/device_reset.rs:1` | Exact guarded engine hooks can prevent stale texture/readback use. Browser's fixed render size reduces exposure but does not prove resize/reset safe. Needs full original-function ABI and resource-lifetime tests. |
| Notifications stretched above radar | Glue 5 `d56e47b`, `crates/glue5-runtime/src/overlay.rs:64` | Small source-defined data overlay: GameStream width `0.19890859375` to `0.15000000000`, equal length. Apply to immutable served copy; preserve the original mirror and exact manifest lengths. |
| Autosave pause-menu control | Glue 5 `e920339`, `overlay.rs:44` | Small exact-length menu-item reorder; fixes the older data's greyed Startup Flow stealing left/right navigation. Independent of graphics. |
| Online ambient/shop script broadcast capacity | Glue 5 `6574053`, `online.rs:375` | Exact-length `gameconfig.xml` overlay; PlayerBroadcastData counts 3600→3, 2500→4, 150→12, 80→12, 40→16. Existing online milestone explicitly left the initial configuration integration open; verify current served bytes before changing. |
| Pause-menu Load/New Game hangs offline | Glue 5 `4b60519`, `crates/glue5-runtime/src/gamelog.rs` | Hook netLog flush to avoid waiting for omitted network spool thread only offline. Requires typed engine adaptation. Do not disable network flush during LAN. |
| Radio wheel analog/mouse | Glue 5 `fec3de4`, `input.rs:133` | Alias radio input to selection-wheel axes because old data maps the newer radio axes nowhere. Browser currently feeds analog pad data; that alone does not establish radio wheel compatibility. |
| In-game phone-browser link clicks | Glue 5 `d7c359a`, `input.rs:149` | Exact `SET_INPUT_EVENT` conversion mouse1001→accept16, gated to the matching Scaleform method. Applies to the game's phone app, not Chrome navigation. |
| New Online jobs / Creator / shared races | New Glue 5 `90e0536`, `551ccf2` | Substantial later integration: local UGC metadata, jobs files, transition sessions, sharing on virtual port47900, and missing text labels. Current LAN callbacks deliberately report UGC unavailable. Not included merely by copying the socket transport. Prioritize stable freemode/character save first. |
| New touch UI/aim assist; Android/Linux/Vulkan packaging | Remaining commits since pinned Glue 5 | Native platform or touch work; browser user explicitly excludes touch and gyro. No need to replace retained Icons/Xbox/PlayStation controls or alter Intel build inputs. |

## Feature boundaries already present

`native-port/engine-lan/BROWSER_LAUNCHER.md:26` records browser Story/Free Roam,
six graphics presets, bounded resolution/FPS, keyboard/mouse, standard analog
gamepads, assisted targeting, save manager, isolated DLC and offline trainer.
Fixtures establish input/storage/transform behavior; they do not establish
physical-controller feel, every cheat effect, arbitrary DLC gameplay, or paired
multiplayer. The human has separately reported Free Roam working.

Mugoat's voice, roles, economy, native UDP protocol and gameplay entities live
in `src/mp.rs` and related native host code. Engine LAN instead carries the
game engine's datagrams and local character/stat callbacks. There is no shared
wire protocol making these automatically the same feature. Voice, legacy roles,
wallet/inventory and native backup interchange remain explicit separate work;
the human previously prioritized core gameplay ahead of economy.

Native Metal binaries, TrollStore memory entitlements, iOS display pacing and
Apple controller APIs cannot be copied into Chrome. Chrome uses WGSL/WebGPU,
its own memory sandbox and Gamepad API. Intel Metal caches remain reusable for
native packaging and preserved unchanged; they are not browser shader blobs.

## Recommended order and acceptance

1. Repair bounded renderer/data compatibility first: memory-file naming,
   headblend evidence, radar mask/coverage and interior stencil semantics.
2. Test the exact creator scene again, then finish creation and observe an
   in-world minimap. Save/reopen the same isolated character before declaring
   character persistence. Then verify two actual peers and movement.
3. Port the small exact data overlays and proven input/resize/save fixes with
   original-byte guards. Preserve historical receipts and current IPA.
4. Treat jobs/Creator, voice and legacy RPG parity as separate later features.

The follow-on bounded memory-filename adaptation is separately prepared in
`memory_filename.py`, `memory_filename.js` and its synthetic fixture. Original
function 1652 has six parameters `[i64,i32,i64,i64,i32,i64]`, no return, and
63-byte body SHA-256
`3bf0f7632417fac9a02fa60cfb1e5fdee80c87d8955ee8124c61fdab1f3c9da6`.
The three focused tests passed in 7.873 seconds: exact original engine pin,
unreviewed-engine rejection and a typed auxiliary-WASM callback fixture. This
does not prove corrected skin or a running game; production slot/worker
integration and a rendered comparison remain separate.

No current IPA, original Intel folder, browser mirror, game save, listener,
relay, stage, credential or setting was changed by this audit/helper work.

## Follow-up: character view and missing edit instruction

The later browser image reportedly showed the wall without the character,
whereas iOS showed a full character. The saved trace `132437.json` contains
WebGPU bind-group validation failures for an RG16Unorm texture treated as
filterable float. Failed rendering must be repaired before diagnosing this as
a camera-position problem. No camera/FOV override was found in the LAN
callbacks. Native `EngineLanLaunchChoice.engineMode` and browser LAN-to-Story
query both select start mode 1, and their explicit LAN engine arguments match.
Different viewport aspect alone does not establish the reported wall view.

One bounded input discrepancy is real: `controller.js` updates relative DX/DY
while pointer-locked but omits absolute MX/MY; the original browser updates
both. A regression fix should update MX/MY by the actual relative motion,
clamp them to the render dimensions, retain configured sensitivity/inversion
for DX/DY, and test locked versus unlocked behavior. This is not proven to be
the character-camera cause.

`FACE_NEW_C` is not the heading "New Character". The public extracted original
label dataset at
<https://gist.github.com/FrazzIe/d90f3c0025a7933f2a5b04faab92c645> maps it to
"Press ~INPUT_FRONTEND_ACCEPT~ to start editing this character."
Thus the missing instruction may hide the required accept action before
editing. Latest Glue 5 `551ccf2` covers twelve job labels and does not contain
this label. The separately prepared `text_fallback.js` retains the original
getter's existing result; only absent exact labels get a bounded cached
English fallback. Its original getter pin is function 77480, `[i32] -> [i64]`,
1114-byte body SHA-256
`fd017869f336468fcfc1e7aff84596ed412b4f694dceeca6ec95dfb819b9c182`.
Neither the fallback nor the input discrepancy proves a camera repair.

## Implemented follow-up in isolated v8

The baseline matrix above is preserved. v8 now integrates the radar/HUD/pause
variants, interior RG stencil, normalized16 format choice, global memory-file
name hook, English boot query and two UI data overlays. Existing broadcast
capacity was already served by `serve_browser.overlay`; it was verified rather
than duplicated. `BROWSER_RENDERER_PARITY.md` and the separate renderer receipt
record exact scope and GPU checks. Shadow/reset hooks, radio/phone aliases,
Online jobs/Creator and voice/economy parity remain open. New Chrome creator,
in-world radar and paired gameplay acceptance are still pending.
