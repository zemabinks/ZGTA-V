# ZGTA V 2.0 beta

### By zema · zemabinks

Play Story or Free roam, or host/join a private multiplayer lobby. The Pure Black launcher keeps game files, saves, mods and controls together. **Your own matching prepared game files are required; no commercial game content is included.**

**[Download 2.0 beta](https://github.com/zemabinks/ZGTA-V/releases/tag/v2.0.0-beta.1)** · **[Start here: installation guide](docs/START-HERE.md)** · **[Add Zema's Sileo Repo](https://zemabinks.github.io/repo/)**

![Actual browser launcher](docs/images/Home-final.png)

## Pick your platform

| Platform | Package | Status |
|---|---|---|
| iOS with compatible TrollStore / TrollStore Lite | [Native IPA](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.1/ZGTA-V-Build91-Archive-Access-TrollStore.ipa); Sileo installer also available | Beta; tested owner installation/launcher/archive workflow on RootHide iPhone |
| Windows x64 | [Windows ZIP](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.1/ZGTA-V-Build92-Windows-x64.zip) with real bundled Python.exe | Alpha; hardware execution/gameplay need community testing |
| Mac / Linux | [Mac/Linux ZIP](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.1/ZGTA-V-Build92-Browser-Mac-Linux.zip) using Python 3.9+ | Beta host; macOS package/HTTP checks, Linux/gameplay pending |
| Android | [Termux ZIP](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.1/ZGTA-V-Build92-Android-Termux.zip) | Experimental alpha, not an APK; GPU compatibility often limited |

**[Full installation instructions](docs/START-HERE.md)** explain game-folder layout, first launch, updates, local networking, saves, mods, controls and troubleshooting. An ordinary retail GTA install folder alone does not satisfy the prepared mirror format. This release does not provide a retail-game converter, native Windows game.exe or Android APK.

## What's included

- Pure Black launcher and settings, green Z branding, iOS V+Z icon and by zema credit.
- Solo Story / Free roam and private multiplayer; configure Join/Create, then use the contextual green Play/Host button.
- Fresh advertised online rooms and explicitly saved Favorites; offline favorites cannot join.
- Read-only external archive handling, folder recheck, retained source archives and clear permission errors on iOS.
- Separate Story, Free roam and multiplayer saves, optional checked backups/transfers, compatible mod management and existing input/settings controls.
- Checksums, source manifests, installation guides and an honest platform test matrix. No paid Actions build is used.

## Test status

iOS package: version2.0 / Build 91, unchanged from the owner-confirmed archive-access update. Browser packages: revision92, with launcher/packaging changes and the preserved checked engine bytes. Local tests and UI screenshots are documented in **[verification](docs/VERIFICATION.md)**. Windows/Android/Linux hardware gameplay, current two-device multiplayer, real save-upgrade retention, controlled performance and reboot persistence remain open beta tests.

Found a problem? **[Use the test-report template](docs/TEST-REPORT.md)**. Review logs for private paths/addresses before posting. Do not upload game data, private saves, passwords or signing keys.

## Source and credits

This is the first public 2.0 source snapshot. It contains the current native app, browser host, multiplayer and bridge source plus their local build/test tools; earlier private history and phone logs are excluded. Production iOS source units and all packaged browser helpers are compared by SHA-256 to the preserved build manifests. Fixture paths in tests use `ZGTA_GAME_MIRROR`; example LAN endpoints are generic. See [public source audit](docs/SOURCE-AUDIT.json).

A fresh-machine native build additionally needs the pinned matching engine, generated wasm2c inputs, Intel shader cache and toolchain used by the native build scripts. Those local generated inputs are not bundled in this source snapshot. The existing native build reused checked inputs; a complete fresh-source native build has **not** been validated. Browser downloads include a checked Runtime directory and can run with your matching prepared files without rebuilding native iOS.

Upstream authorship and licenses remain in [LICENSE](LICENSE), [native-port/LICENSE](native-port/LICENSE), the bundled Licenses resources and [third-party notices](native-port/engine-lan/THIRD_PARTY_NOTICES.md). ZPlay is the wider games website; this port is by zema.
