# ZGTA V 2.0 beta 4 — proximity voice

**iOS 109 · Browser 109 · Mac DMG 109.1 · Sileo installer 0.109-2**

## What's new

- **Proximity voice for private multiplayer:** talk between iPhone and browser players using the existing microphone and speaker buttons.
- **Clearer distance audio:** voices are loud nearby, progressively quieter as players separate, and silent beyond 35 metres. Volume changes are smoothed while moving.
- **Separate voice controls:** switch your microphone off or mute nearby voices while game audio stays separate. No separate multiplayer bridge interface is needed.
- **Same private hosting:** voice uses your compatible Engine LAN relay over LAN or private Tailscale. No public voice service or new account is required.
- **Keep your data:** update over the existing app and retain your game files, saves and settings. Do not delete the app to update.

## Updating and limits

The owner confirmed Build 109 installation/data, actual iPhone/Mac speech both ways, smooth distance reduction, out-of-range silence/return and microphone mute. Distances in the owner listening check were estimated; automated native/browser PCM measurements check the actual curve.

The microphone starts off and requires permission. Browser capture needs a secure context, such as the local launcher address or HTTPS. Hiding the game tab pauses voice; enable it again when returning.

Mac 109.1 packages exactly the browser 109 payload tested on Mac. Its launcher sources and pinned runtimes are unchanged from 107.1; mounted hashes, signatures, bundled Intel Python and native-layout checks pass. The109.1 drag-install was not repeated. The Mac app is ad-hoc signed, not Apple-notarized.

Windows/Android/Linux and Apple Silicon execution, AppSync installation, Bluetooth/interruption handling and simultaneous speakerphone echo remain unverified. Android is a Termux/browser package, not an APK. This voice release does not claim a new physical 3 GB iPhone performance benchmark.

Stable Sileo installer 0.109-2 uses the same tested Build 109 IPA as private 0.109-1. Its version, descriptions and public download pins differ; the installation method and app identity are preserved. That public metadata wrapper was not separately phone-tested. AppSync remains experimental for compatible ARM64 rootful devices, not RootHide/rootless.

Your own compatible game files are required. No commercial game content is included. [Install/update](START-HERE.md) · [Verification scope](VERIFICATION.md).
