# Browser renderer parity — isolated v8

The user’s screenshots establish a rendered LAN character editor with corrupt
green/blue skin. Free Roam separately worked. Neither observation verifies two
peers, character persistence or an in-world minimap. The editor normally hides
the gameplay radar. This update is ready for a new visual test, not a claim
that all native features now work in Chrome.

## Included

- Preserve DXGI R16G16B16A16_UNORM and R16G16_UNORM when WebGPU's enabled
  texture-formats-tier1 supports them. The original worker always substituted
  half-floats. The skin compressor outputs normalized 16-bit words, then copies
  those bytes into BC1; changing their representation corrupts the block. The
  local GPU fixture reproduced the old wrong words and verified exact normalized
  words plus the copy/sample path. Unsupported adapters explicitly log the old
  fallback; fidelity there remains open.
- Duplicate the D3D stencil plane into RG8Uint x/y instead of R8Uint x alone.
  Glue5 documents the original browser mismatch in its interior-lighting fix.
- Apply the three distinct minimap corrections from pinned glue5: radar edge
  coverage without a geometry shader; a filtered HUD mask and normalized HUD
  coordinates; separate world-space pause-map exploration. No blanket shader
  replacement, forced radar in the creator, or invented minimap overlay.
- Correct `fiDevice::MakeMemoryFileName` globally through a pinned typed callback.
  New glue5 commit `0db284d99ddc2b36291c4a29b17ad69bd93c5bb5` removes libc's `0x`
  from the hexadecimal address after `memory:$`. The original Create parser
  does not skip it. This affects dynamic file users, but its contribution to
  the observed skin defect is not yet proven.
- Return `en-US` from the exact engine boot language query in all browser modes.
  Browser and system locale settings remain unchanged. This selects existing
  English game resources rather than translating menus with an HTML overlay.
- Serve unchanged-length UI data adaptations for notification width and the
  autosave/startup-flow menu order. Existing broadcast-capacity overlay remains.
- Retain the single launcher, independent Story/Free Roam/LAN saves, mods,
  offline trainer and analog controller support. LAN continues to deny trainer
  actions. Existing native Icons/Xbox/PlayStation styles are unchanged.

## Verification boundaries

`tests/browser_renderer_parity_validation.json` separates actual local GPU
checks from offline fixtures and the still-pending Chrome gameplay comparison.
The full original and LAN modules compile without execution; the additional
hook changes only pinned function 1652 plus the existing pad boundary 10454.
No original function/type indices move. The callback handles BigInt pointers,
bounded output strings and exact signed length/flag narrowing.

The four minimap shader variants compile on this Mac's in-app Chromium GPU.
That does not prove correct in-world composition in the separate Chrome game.
Likewise, the texture fixture proves byte preservation, not every character
material, every graphics setting or all upstream runtime fixes.

The broader audit in `tests/browser_parity_audit.md` tracks still-unported
shadow/reset hooks, radio/phone input compatibility, jobs/Creator and legacy
voice/economy features. Native Metal caches and TrollStore features do not run
inside WebGPU. No full web/iOS feature-parity claim is made.

## Run / visual acceptance

Use the command in `BROWSER_LAUNCHER.md`, with isolated stage
`EngineLAN-FeaturesBrowser-20261017-v8`, and open the local launcher. Close the
old game tab before launching again. Start with Performance, 540p, 30 FPS and
two workers on this Intel Mac. Engine LAN should now use English menus.
Check the same male/female creator scenes, complete a character, then inspect
the radar in the world. Next verify save/reopen and actual iPhone/browser peers.
Keep the existing character/save data; no deletion or reset is required.

The original browser mirror, historical v5/v6/v7 stages, all IPAs and original
Intel folder are preserved. v8 is an ignored new Build output; the source,
fixtures, bounded receipts and applicability audit are reviewable in Git.

## v9 browser encoding correction

The first actual v8 Chrome attempt failed during archive mounting at 24%. The
new memory filename callback used TextEncoder.encodeInto on a shared-memory
view. Chromium rejects that destination even though Node accepted the same
typed WASM fixture. This is a startup regression, not an asset download stall.

v9 encodes into a bounded ordinary byte array, then copies only initialized
UTF-8 bytes and the terminator into shared memory. A real in-app Chromium
fixture reproduced the old exception and passed corrected output, UTF-8
truncation and memory-growth checks. Node now explicitly enforces this browser
restriction too. No WASM, renderer or other staged payload differs from v8.
Fatal worker rejections now reach the visible loading error label.

Current launch commands select v9. Historical v8 receipt and 103-test result
remain intact; the new browser regression has its own bounded receipt in
`tests/shared_encoding_regression_validation.json`. New Chrome gameplay is
still required. Neither the current IPA nor original Intel folder changed.

## v10 normalized sampling, missing prompt and pointer coordinates

The actual v9 Chrome trace exposed a second capability requirement: RG16Unorm
is renderable under texture-formats-tier1 but cannot be bound as a filterable
Float texture. Repeated invalid bind groups invalidated command buffers. The
user screenshot showed a close-up wall and no visible character. It does not
establish a camera/FOV root cause; no camera transform is forced by this patch.

Keep exact UNORM16 textures for compressor/render/copy bytes. Before a shader
samples one, v10 refreshes a separate floating proxy with an explicit
UnfilterableFloat textureLoad binding. Normal shader reads use the filterable
proxy; this Mac's float32-filterable feature preserves normalized precision in
RGBA32Float. A reported half-precision fallback remains on unsupported GPUs.
Existing writes invalidate the proxy, each mip/layer is refreshed, and source
destruction also releases the derived texture after the existing fence.

The actual GPU fixture reproduced the old rejected Float binding and verified
correct filtering through the production proxy helper. It returned RG values
0.5 and 0.6250019073486328 for the known normalized input; no game was started.

The text getter now forwards to an exact copied original first, then supplies
only 13 known missing English labels, including FACE_NEW_C: Press Accept to
start editing this character. The original input token is retained. Existing
translations win. Original text function/type indices remain stable; one
original body copy is appended and exported for forwarding. Both original and
already-remapped LAN getter bodies have exact separate pins. Missing strings
are bounded/cached and allocated in the supplied engine memory.

Locked mouse movement now updates the clamped menu cursor as the original web
input did; relative look sensitivity/inversion stays separate. A regression
checks lock, unlock and edge clamping. This is not evidence that pointer input
caused the wall scene.

Current commands select isolated v10. Confirm a fresh character view, the
restored edit prompt, character persistence and in-world radar before calling
the browser rendering or paired multiplayer accepted. Historical v8/v9
receipts and artifacts remain intact; current IPA and Intel inputs are not
edited.

### 2026-10-20 menu follow-up

The bounded fallback now has 34 keys in one browser/native catalog, including the base Public Session heading verified in actual Chrome gameplay. Native preparation installs the original-first text hook as well. Two small UI XML files refresh outside the old OPFS block cache; game archives and saves remain cached. The native reader receives the existing GameStream width correction too. These native changes are source-only until the next IPA; see [scope and evidence](docs/menu-labels-and-notifications-20261020.md).
