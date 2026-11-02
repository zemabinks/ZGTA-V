# ZGTA 5

**1.2 — browser / Mac** · iOS remains **1.1 beta 1**

### By zema · zemabinks

**Solo Story · Free Roam · Private Multiplayer — Join or Create.**

Your own matching prepared game files are required. No commercial game content is included.

**[Download 1.2](https://github.com/zemabinks/ZGTA-V/releases/tag/v1.2)** · **[Install and update](docs/START-HERE.md)** · **[What's new](docs/RELEASE-NOTES-1.2.md)** · **[Play guide](docs/PLAY-GUIDE.md)**

## Start screens

| Native iOS app | Browser / Mac 1.2 |
|---|---|
| <img src="docs/images/ios/Home-107.png" alt="Native iOS Home captured in the iPhone 15 Pro Simulator" width="400"> | <img src="docs/images/browser/Story-mode-20261101.jpg" alt="Browser 1.2 design with monochrome map and main navigation" width="400"> |

Browser images show the design included in the **1.2 downloads**. The native iOS
app remains **1.1 beta 1** with its existing layout. [See the full iOS and browser gallery](docs/INTERFACE-PREVIEWS.md).

## Downloads

| Platform | Package | Status |
|---|---|---|
| iPhone / iPad — iOS / iPadOS 15.0+ | [1.1 beta 1 IPA](https://github.com/zemabinks/ZGTA-V/releases/download/v1.1-beta.1/ZGTA-V-Build109-VoiceDistance-TrollStore.ipa) | Owner-tested on iPhone 15 Pro with TrollStore. Other installation routes remain experimental. |
| Mac | [1.2 DMG](https://github.com/zemabinks/ZGTA-V/releases/download/v1.2/ZGTA-5-1.2-Mac.dmg) | Owner-tested Intel Mac installation, design/navigation and game startup with existing data; package checks pass. Apple Silicon untested. Ad-hoc signed, not notarized. |
| Mac / Linux browser | [1.2 ZIP](https://github.com/zemabinks/ZGTA-V/releases/download/v1.2/ZGTA-5-1.2-Browser-Mac-Linux.zip) | Requires installed Python 3.9+ and a compatible browser. Linux gameplay untested. |
| Windows x64 | [1.2 ZIP](https://github.com/zemabinks/ZGTA-V/releases/download/v1.2/ZGTA-5-1.2-Windows-x64.zip) | Bundled Python; Windows execution untested. |
| Android | [1.2 Termux ZIP](https://github.com/zemabinks/ZGTA-V/releases/download/v1.2/ZGTA-5-1.2-Android-Termux.zip) | Experimental browser version; no APK. Android execution untested. |

Read the **[installation guide](docs/START-HERE.md)** before downloading. The Mac launcher includes Python and requires Chrome plus your compatible game files. Sileo users can add **[Zema’s Repo](https://zemabinks.github.io/repo/)**. Installer **1.1~beta1** delivers the unchanged owner-tested Build 109 IPA through the public download URL. AppSync is experimental. Keep your existing app, game files and saves when updating; previous releases remain available.

## What's new in 1.2

- Browser styling now matches the iOS app's black and green surfaces and monochrome Los Santos map. The colored city artwork is removed.
- Desktop layout and button positions stay familiar. Mods, Graphics, Controls, Saves and Support use the main page navigation.
- Mac launcher branding and product version show **ZGTA 5 / 1.2**.
- Matching Mac, browser/Mac/Linux, Windows and Android downloads retain your game folders, saves, mods and private LAN/Tailscale hosting.

The iOS app and Sileo installer remain **1.1 beta 1**. Proximity voice, stable building rendering and independent memory controls remain included; the renderer, voice implementation and memory policy are unchanged. No new FPS or low-RAM performance gain is claimed. See the [release notes](docs/RELEASE-NOTES-1.2.md).

## Guides

- [Install and update](docs/START-HERE.md)
- [Mods, vehicle previews and graphics](docs/PLAY-GUIDE.md)
- [Host or join a lobby](docs/PLAY-GUIDE.md#private-multiplayer)
- [Remote play with Tailscale](docs/REMOTE-PLAY.md)
- [Back up saves](docs/PLAY-GUIDE.md#back-up-saves)
- [Report a problem](docs/TEST-REPORT.md)

Reduced-memory behavior has not been benchmarked on a physical 3 GB iPhone SE2020; stable 60 FPS is not promised. Private LAN/Tailscale play is supported, with no worldwide server directory. See [verification and remaining limits](docs/VERIFICATION.md).

## Optional hosting tools

Normal hosting uses **Multiplayer → Create a lobby** in ZGTA 5 and needs no extra download.

[Mac relay controls 1.1](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.3/ZGTA-V-Relay-Controls-1.1.zip) are for a Mac that should keep a standalone multiplayer relay available while GTA is closed, including managed ZRemote setups. The relay forwards multiplayer traffic; the game runs on the players' devices. The Mac must stay awake and logged in. See [optional relay setup](docs/PLAY-GUIDE.md#optional-standalone-mac-relay).

## Source and credits

[Build information](docs/DEVELOPMENT.md) · [Source audit](docs/SOURCE-AUDIT.json) · [License](LICENSE) · [Native source license](native-port/LICENSE) · [Third-party notices](native-port/engine-lan/THIRD_PARTY_NOTICES.md)

The [versioning guide](docs/VERSIONING.md) explains the naming transition. Existing tested artifacts and their download filenames are retained.

Current browser/Mac product version is **ZGTA 5 — 1.2** (internal revision 110). The unchanged iOS app remains **1.1 beta 1** (Build 109); Sileo uses `1.1~beta1`. Existing artifact URLs, app identifiers and data paths are preserved.
