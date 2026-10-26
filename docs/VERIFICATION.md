# 2.0 beta verification

## Native iOS — unchanged Build91

Compiled source: `bb230c44fc008f7601be5ee66b2f0c7fb206d92b`.
IPA SHA-256: `f54b0172e6d9d348295af4ecf117c71817284eaca09cbf9e09aa130edb6f9802`.
Bytes: 90,975,818. App version2.0, build91. Existing identity/entitlements retained.

Local ARM64 Release build, strict ad hoc signature, CRC, identity, memory requests
and resource preservation passed. Actual macOS file-coordination and libarchive
tests cover held grants, returned URLs, separate-writer exclusion, cancellation,
ZIP/split-ZIP reads, pre-existing game replacement, source retention and unrelated
save fixtures. Three actual Simulator UI cases passed using production UIKit and
GameFolder with inert engine/download/install adapters and temporary files.
These tests do not substitute for an iOS provider or physical gameplay test.

The owner's physical Build90 log proved a permission failure opening a discovered
mirror.rar, after successful scan. After the Build91 update the owner reports:
“Yes it works now, next step now”. This establishes owner-confirmed archive
workflow success, not independent current app inventory, save-upgrade, gameplay,
performance or reboot acceptance. Raw phone logs remain private.

The Sileo native helper interface was physically exercised on the same RootHide
setup in earlier successful updates. Current0.91-1 wrappers pin the same91 IPA
and pass local scripted tests; independent current helper output was not supplied.
AppSync remains an untested rootful experimental route.

## Browser revision92

Changes affect the launcher and host packaging, not the existing engine/renderer
WASM or network/profile worker source. Runtime files are validated against the
preserved stage manifest before packaging. No game content or old saves change.

Targeted regression groups passed: 59 methods across browser policy/entrypoint,
launcher/controller/runtime gates, portable integrity, real localhost lobby
health and hosting, save transfer, mod transactions, browser routes and shared
Swift/JS invite formats. The initial sandbox denied localhost socket binds;
remaining networking tests passed when allowed to bind disposable test listeners.

Actual browser UI checks cover the two-card multiplayer layout, host and join
configuration returning to a contextual green button without starting a host,
empty-address errors, offline explicit favorites with Join disabled, exclusion
from Online, and Settings/Saves availability. Screenshots are actual local browser
frames; the shown lobby names are disposable fixtures, not a live gameplay test.

Windows packages contain the pinned official Python3.13.16 x64 embeddable runtime.
Mac verification can inspect PE headers and exact archive contents; it cannot
execute Windows Python. Android uses Termux Python and is not an APK. The generic
Mac/Linux host uses installed Python3.9+ and an explicit folder path prompt.

Package/source manifest, CRC, extracted HTTP route and bundled-runtime checks
are recorded separately after the frozen source is packaged. Current Windows,
Android and Linux physical execution/gameplay remain community tests.

## Still open

- Fresh native game startup, save retention across a real app-data upgrade, mods
  and physical controller/audio checks for this exact build.
- Two-device multiplayer and full world recovery after network loss.
- Windows/Android/Linux hardware setup and gameplay matrix.
- Controlled performance/thermal comparisons and reboot persistence.
- A fresh-machine native build from the public source with all pinned generated
  engine/shader/toolchain inputs; the existing local build reused checked inputs.

No FPS gain, universal device compatibility, native Android/Windows game binary,
public matchmaking or reboot persistence is claimed. No paid hosted build ran.
