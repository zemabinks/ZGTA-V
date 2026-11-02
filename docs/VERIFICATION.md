# ZGTA 5 1.2 verification

## Current browser / Mac scope — 1 November 2026

- **Owner Intel Mac:** exact 1.2 DMG installed into Applications; design/navigation and game startup with existing data confirmed. The public DMG retains those exact bytes.
- **Browser UI:** all eight integrated views inspected in actual Chrome from the packaged launcher. Fourteen existing controls retained their placement within one pixel; the monochrome map and native-style surfaces were visually checked.
- **Local checks:** 27 focused UI, desktop-identity and portable test methods passed, plus JavaScript syntax checks. All three portable source/runtime manifests, archive CRCs and extracted HTTP verification passed on Mac. Windows Python headers and full archive bytes matched their pinned input; Windows was not executed.
- **Mac package:** disk-image validation, deep strict ad-hoc signatures, all 3,521 mounted member hashes, relocated Intel Python and actual production AppKit layout passed. The DMG includes an Applications shortcut.
- **iOS / Sileo:** unchanged 1.1 beta 1 / Build 109; no replacement IPA or DEB. Existing iPhone/Mac voice and native Simulator layout results remain below.

[RELEASE-1.2-MANIFEST.json](RELEASE-1.2-MANIFEST.json) identifies the exact four packages and the owner's publication choice. [SOURCE-AUDIT.json](SOURCE-AUDIT.json) maps the public source to its frozen inputs.

Apple Silicon, Windows, Linux and Android execution remain untested. The Mac app is ad-hoc signed, not notarized. Android remains the experimental Termux/browser starter, not an APK. No new renderer, voice, memory-policy, FPS, thermal or physical 3 GB-device improvement is claimed.

## Historical 1.1 beta 1 evidence

# Beta4 verification

## Current scope — 1 November 2026

- **Owner iPhone and Intel Mac/Chrome:**  exact Build 109 installation with existing data, speech in both directions, clear smooth distance reduction, out-of-range silence, nearby return and iPhone microphone mute passed. The human distance estimates were not instrumented measurements.
- **Native/browser audio:** 14 compiled mixer/transport methods pass. PCM levels, smoothing and native/browser parity were measured at 44.1, 48 and 96 kHz. A real Chrome 96 kHz AudioWorklet test also passed with synthetic audio; that does not establish every physical audio route.
- **iOS controls:** current production views were inspected in iPhone 15 Pro and SE 2020 Simulator layouts on iOS 26.3 using an engine-free fixture. This checks layout, not physical 3 GB performance.
- **Mac 109.1:** exact owner-tested browser 109 payload; unchanged 107.1 launcher sources and Python runtime pins; disk-image, strict mounted signature/hash, relocated Intel Python and production native-layout checks pass. The new 109.1 drag-install was not repeated.
- **Portable packages:** Windows/Android archive CRC, complete manifest hashes and static entry-point checks pass. Their hardware execution remains untested.
- **Sileo:** public1.1~beta1 uses the tested109 IPA with public URL/version/description changes. Existing installation methods, package/app identities and old package versions are preserved. The public wrapper was not separately installed; AppSync remains untested.

## Current limits

Bluetooth/interruption handling, simultaneous speakerphone echo, Windows/Android/Linux and Apple Silicon execution are unverified. No new physical 3 GB/A13 performance, thermal or long-session bound is claimed. The Mac app is ad-hoc signed and not Apple-notarized. LAN discovery still needs a compatible advertised host and reachable private networking; no worldwide directory is added.

[BETA4-MANIFEST.json](BETA4-MANIFEST.json) records package sizes/hashes and the final publication approval. Older results below retain their original version and meaning.

## Historical beta3 and earlier evidence

# Beta 3 verification

## Current scope — 31 October 2026

The owner approved publication of iOS 107, Mac DMG 107.1, browser 107 and relay controls 1.1 after the following checks. Exact package sizes and SHA-256 values are in [BETA3-MANIFEST.json](BETA3-MANIFEST.json).

- **Physical iPhone 15 Pro:** Build107 gameplay and graphical report supplied; the previously flickering buildings remained stable through the troublesome camera angles. A 180-second run while driving through new areas averaged 31.2 presented FPS with serious thermal state and an approximately 30 FPS active guard. This is not a matched speedup benchmark. The saved 60 FPS choice remained intact. Memory grew as new areas loaded; a long-session plateau is not established.
- **Mac/browser:** the owner installed/launched DMG107.1 and confirmed connection with the iPhone. Both clients listed the empty managed LOS-SANTOS room without entering an address after the relay1.1 update. Earlier reconnect visibility was also owner-confirmed; no new universal loss/recovery guarantee is inferred.
- **iOS layouts:** production UIKit views were inspected in iPhone15Pro and compact SE2020 Simulator sizes. Simulator layout checks do not establish physical SE2020 memory, heat or GPU behavior.
- **Local validation:** native build, strict signature, icons and IPA archive checks; portable CRC/source/runtime checks; memory policy/resource lifetime checks; relay catalog/advertisement lifecycle, bounded directory and arbitrary announced-port discovery checks pass. Production Swift discovery and Python Bonjour resolved a disposable non-default port. Public source fixture checks are recorded with the release.
- **Sileo:** metadata installer0.107-2 pins the unchanged Build107 IPA. Existing installer methods, app data and older packages remain preserved. Scripted installer tests do not establish AppSync phone compatibility.

## Remaining limits

- No physical 3 GB/A13 Reduced-mode benchmark, cold matched thermal comparison, universal 60 FPS or guaranteed long-session memory bound.
- Windows, Android and Linux gameplay/execution, and Apple Silicon execution remain untested. Android is Termux/browser, not an APK.
- Mac app is ad-hoc signed, not Apple-notarized. Requires Chrome and compatible prepared game files.
- AppSync and other sideloading methods remain experimental. Reboot persistence, physical controller/audio matrix and save migration across every installation method are not established.
- LAN discovery requires compatible advertisements, local-network permission and reachable multicast. Tailscale remains a private invite/address route, without a worldwide directory.
- Fresh-machine native compilation still requires the matching generated engine/shader/toolchain inputs; the checked build reused pinned inputs.

## Historical evidence

The records below describe their original versions. Their pending results are not claims about current Build107 acceptance.


## Historical Build 96 candidate / Sileo 0.96-1

[Build 96](https://github.com/zemabinks/ZGTA-V/releases/tag/host-capacity-candidate-96) applies the revised bounded multiplayer host-broadcast fix to iOS and browser. The historical Sileo source pinned that exact IPA through installer **0.96-1**; signed indexes, both package archives and all 23 isolated installer/catalog/index test methods pass. Physical Build96 installation, paired gameplay and small-job reproduction remain pending. Prior Build91 evidence below is historical and does not establish Build96 device acceptance.

## Native iOS — historical Build 91

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

The owner's physical Build 90 log proved a permission failure opening a discovered
mirror.rar, after successful scan. After the Build 91 update the owner reports:
“Yes it works now, next step now”. This establishes owner-confirmed archive
workflow success, not independent current app inventory, save-upgrade, gameplay,
performance or reboot acceptance. Raw phone logs remain private.

The Sileo native helper interface was physically exercised on the same RootHide
setup in earlier successful updates. The historical0.91-1 wrappers pin the same91 IPA
and pass local scripted tests; independent current helper output was not supplied.
AppSync remains an untested rootful experimental route.

## Browser revision 92 (initial public beta)

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

Windows packages contain the pinned official Python 3.13.16 x64 embeddable runtime.
Mac verification can inspect PE headers and exact archive contents; it cannot
execute Windows Python. Android uses Termux Python and is not an APK. The generic
Mac/Linux host uses installed Python 3.9+ and an explicit folder path prompt.

All three package/source manifest, CRC, extracted HTTP route and bundled-runtime checks pass on macOS. Windows Python PE headers and archive bytes match its pinned official input. The actual Mac shell starter passes check mode with private disposable state. A test-only /var alias was correctly rejected by the no-symlink mod-store policy; the canonical path passes. These results are recorded in the release verification JSON. The sanitized public source itself also passes the same 59 targeted regression methods. Current Windows,
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

## Browser revision 93 — desktop launchers

Changes are limited to desktop entry installation, preferred Chrome opening on macOS, packaging and documentation. Engine, game assets, saves and multiplayer code are unchanged.

Nine desktop-focused tests pass: exact iOS icon provenance; Mac bundle creation and executable syntax; private installed-copy survival after removing the temporary original download; repeat launches; update recovery; preservation of unrelated apps and symlink targets; Windows shortcut argument contracts; and graceful behavior when Desktop access fails. Windows COM execution and real Finder double-click remain separate device/UI acceptance checks. No Windows environment is attached to this Mac.

The first successful Mac/Windows setup installs a desktop entry. It starts the existing local server in a visible Terminal/console window. The URL is available only while that process is running; no login item or service is installed. Repeated startup reuses an existing ZGTA 5 server. Existing browser profile/origin and game-folder selection are retained.

Package integrity and real localhost HTTP/startup results for revision 93 are recorded in the release verification asset. These checks do not establish full game compatibility or reboot persistence.

Actual revision 93 Mac workflow: a real disposable server was started from the extracted package, an app bundle was installed to a private test Desktop, and a second process loaded the installed private copy and reused that live server. The actual installed shell entrypoint passed check mode using its remembered folder. The owned test process stopped cleanly; read-only mirror hashes were unchanged. A screenshot was captured from the actual packaged HTTP launcher. This did not invoke Finder or launch the game. All three extracted packages passed integrity/source mapping and HTTP checks on macOS. Windows Python was checked against the pinned official archive but not executed on Windows.
