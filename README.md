# ZGTA V 2.0 beta 3

### By zema · zemabinks

**Solo Story · Free Roam · Private Multiplayer — Join or Create.**

Your own matching prepared game files are required. No commercial game content is included.

**[Download beta 3](https://github.com/zemabinks/ZGTA-V/releases/tag/v2.0.0-beta.3)** · **[Install and update](docs/START-HERE.md)** · **[What's new](docs/RELEASE-NOTES-beta3.md)** · **[Play guide](docs/PLAY-GUIDE.md)**

## Downloads

| Platform | Package | Status |
|---|---|---|
| iPhone / iPad — iOS / iPadOS 15.0+ | [Build 107 IPA](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.3/ZGTA-V-Build107-Memory-UI-Audit-TrollStore.ipa) | Owner-tested on iPhone 15 Pro with TrollStore. Other installation routes remain experimental. |
| Mac | [Build 107.1 DMG](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.3/ZGTA-V-Build107.1-Mac.dmg) | Drag into Applications. Intel tested; Apple Silicon execution untested. Ad-hoc signed, not Apple-notarized. |
| Mac / Linux browser | [Build 107 ZIP](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.3/ZGTA-V-Build107-Browser-Mac-Linux.zip) | Requires installed Python 3.9+ and a compatible browser. Linux gameplay untested. |
| Windows x64 | [Build 107 ZIP](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.3/ZGTA-V-Build107-Windows-x64.zip) | Bundled Python; Windows execution untested. |
| Android | [Build 107 Termux ZIP](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.3/ZGTA-V-Build107-Android-Termux.zip) | Experimental browser version; no APK. Android execution untested. |

Read the **[installation guide](docs/START-HERE.md)** before downloading. The Mac launcher requires Chrome and compatible prepared game files; it is not a native Mac game engine. Sileo users can add **[Zema's Repo](https://zemabinks.github.io/repo/)**. TrollStore installer **0.107-3** delivers the same Build107 IPA with cleaner successful install output; AppSync remains 0.107-2. See the [installer update notes](https://github.com/zemabinks/ZGTA-V/releases/tag/sileo-installer-0.107-3). Previous releases remain available.

## What's improved

- Buildings remain stable at the previously affected camera angles.
- Automatic, Standard and Reduced memory management are separate from graphics presets, resolution and FPS.
- Heat safeguards preserve saved settings; reports identify the active session settings.
- Nearby LAN browsing uses announced ports, and updated managed hosts appear before the first player joins.
- Browser Graphics, Controls, Mods, Saves and Support share the main navigation.
- Mac installation now supports dragging the app from the DMG into Applications.

## Browser preview

The Mac launcher opens this browser interface. Story mode, Graphics, Controls,
Mods, Saves and Support share the main navigation.

![ZGTA V browser Story mode and main navigation](docs/images/browser/Story-mode-107.jpg)

[See browser layouts and iOS previews](docs/INTERFACE-PREVIEWS.md).

## Guides

- [Install and update](docs/START-HERE.md)
- [Mods, vehicle previews and graphics](docs/PLAY-GUIDE.md)
- [Host or join a lobby](docs/PLAY-GUIDE.md#private-multiplayer)
- [Remote play with Tailscale](docs/REMOTE-PLAY.md)
- [Back up saves](docs/PLAY-GUIDE.md#back-up-saves)
- [Report a problem](docs/TEST-REPORT.md)

This remains a beta. Reduced-memory behavior has not been benchmarked on a physical 3 GB iPhone SE2020; stable 60 FPS is not promised. Private LAN/Tailscale play is supported, with no worldwide server directory. See [verification and remaining limits](docs/VERIFICATION.md).

## Optional hosting tools

Normal hosting uses **Multiplayer → Create a lobby** in ZGTA V and needs no extra download.

[Mac relay controls 1.1](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.3/ZGTA-V-Relay-Controls-1.1.zip) are for a Mac that should keep a standalone multiplayer relay available while GTA is closed, including managed ZRemote setups. The relay forwards multiplayer traffic; the game runs on the players' devices. The Mac must stay awake and logged in. See [optional relay setup](docs/PLAY-GUIDE.md#optional-standalone-mac-relay).

## Source and credits

[Build information](docs/DEVELOPMENT.md) · [Source audit](docs/SOURCE-AUDIT.json) · [License](LICENSE) · [Native source license](native-port/LICENSE) · [Third-party notices](native-port/engine-lan/THIRD_PARTY_NOTICES.md)
