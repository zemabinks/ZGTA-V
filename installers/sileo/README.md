# Zema's Repo

Add this source to Sileo: `https://zemabinks.github.io/repo/`

This is a general source for Zema's iOS tweaks, apps and ports. The first package is
RelayRace RootHide `1.2` for compatible RootHide devices. This package updates metadata and Sileo depiction while preserving the confirmed 20.1 runtime payload and installer scripts.
Original RelayRace by shalamand3r; RootHide support and port by ZEMA.

Current package size: 12,092 bytes. SHA-256: `c2d14fea1cb4919fc6b40a57c58b084a4e2703fdedebec8ad2e4d2926120b914`.

## App downloads

### ZGTA 5 — 1.1 beta 1 · Build 109

By **zema**. Solo Story, Free Roam and Private Multiplayer.

Requires **iOS / iPadOS 15.0+**, your own matching game files and a compatible installation method.

[Download IPA](https://github.com/zemabinks/repo/releases/download/zgta-v-build-109/ZGTA-V-Build109-VoiceDistance-TrollStore.ipa) · [Other platforms and update notes](https://github.com/zemabinks/ZGTA-V/releases/tag/v1.1-beta.1) · [Installation guide](https://github.com/zemabinks/ZGTA-V/blob/main/docs/START-HERE.md)

In Sileo, refresh this source and install **ZGTA 5 (TrollStore installer) 1.1~beta1** with your existing compatible TrollStore. Keep the app and its data installed when updating. Removing the small installer package leaves GTA and its data installed.

ZGTA 5 — 1.1 beta 1 is a naming-only update of the owner-tested Build 109 release. Speech in both directions, smooth distance reduction/range silence/return, microphone mute and existing data passed the owner’s iPhone/Mac checks. Those installation checks used the legacy private 0.109-1 wrapper. The new 1.1~beta1 metadata wrapper has not been separately phone-tested; installer methods and the exact tested IPA are unchanged. AppSync installation, Bluetooth/interruption handling, simultaneous speakerphone echo and Windows/Android/Linux/Apple Silicon execution remain untested. No new 3 GB device performance claim is made.

AppSync 1.1~beta1 is experimental for compatible ARM64 rootful jailbreaks on iOS15.0–18.2, not RootHide/rootless. Other sideloading routes are untested; see [installation options](docs/zgta-v-installation.md).

[Download metadata](downloads/zgta-v.json) · [Installers and checksums](https://github.com/zemabinks/repo/releases/tag/zgta-v-build-109)

## GitHub Releases

The [Releases page](https://github.com/zemabinks/repo/releases) provides a
downloadable `.deb` and `SHA256SUMS.txt` for the latest published tweak. The
current tweak release is [RelayRace 1.2](https://github.com/zemabinks/repo/releases/tag/relayrace-1.2).
Future tweaks can have their own package-specific release tags.

The previous `1.1+roothide.20.1` package remains downloadable from `pool/com.shalamand3r.relayrace_1.1+roothide.20.1_iphoneos-arm64e.deb` (12,108 bytes; SHA-256 `efbec56da598293491ae7ff07d81ecf0596108c30176a11182d122772117d965`).

The Release metadata is signed with an Ed25519 OpenPGP key. Public key:
[`repo-signing-key.asc`](repo-signing-key.asc). Fingerprint:
`369B 9D41 D3BC EA25 20B2 2C2B D9AD 1897 295C 6D05`.

This is the canonical Sileo source. Older v19/v18 packages remain in the
private recovery archive. Installation or upgrade of version 1.2 on a phone
and reboot persistence still need device testing.

### TrollStore installer0.107-3

TrollStore installer0.107-3 shows concise progress on successful installation and retains full helper output on failure. The owner confirmed clean installation, GTA relaunch and existing data on the RootHide setup. It installs the same Build107 app. AppSync remains0.107-2 and experimental. Unrelated dpkg/package warnings remain visible.
