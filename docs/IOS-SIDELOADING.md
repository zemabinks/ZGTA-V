# iOS installation options

**Minimum: iOS / iPadOS 15.0.** This is the app's OS requirement; it does not establish device performance or compatibility with an installer.

## Which file do I use?

Use the same [ZGTA V IPA](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.4/ZGTA-V-Build109-VoiceDistance-TrollStore.ipa) for TrollStore or an experimental sideloading attempt. The filename mentions TrollStore because that is the tested installation route. Other tools must re-sign it. Use `.ipa`, not the TrollStore `.tipa` alias or the Sileo `.deb`.

| Method | ZGTA V status |
|---|---|
| Compatible TrollStore / TrollStore Lite | Tested installation route; follow [installation steps](START-HERE.md#trollstore--trollstore-lite). |
| Sideloadly | Experimental; this IPA has not been installed or gameplay-tested through it. |
| AltStore Classic | Experimental; this IPA has not been installed or gameplay-tested through it. |
| SideStore | Experimental; this IPA has not been installed or gameplay-tested through it. |
| Other IPA signing tools | Untested; follow the tool's official instructions and report the result. |
| Sileo with AppSync | Experimental; restricted to the compatible rootful setup below. |

Back up saves before an update, especially when changing tools or signing accounts. Do not delete an existing working installation to test another method.

## Sideloadly — experimental

1. Install [official Sideloadly](https://sideloadly.io/). Follow its [setup instructions](https://sideloadly.io/faq), including the Windows Apple components if needed.
2. Connect and unlock your iPhone/iPad, and trust the computer when prompted.
3. Drag the downloaded ZGTA V `.ipa` into Sideloadly, choose your device and sign in with your Apple account in the tool. Start installation.
4. If prompted, trust your developer profile in **Settings → General → VPN & Device Management**. On iOS 16+, enable Developer Mode as described in the official guide.
5. Open ZGTA V and follow the [game-file setup](START-HERE.md#iphone--ipad--ios-150).

Free-account installs need refreshing within seven days. Updates should use the same signing account and resulting bundle ID. See the [official FAQ](https://sideloadly.io/faq).

## AltStore Classic — experimental

1. Set up AltServer and **AltStore Classic** using the official [Windows](https://faq.altstore.io/altstore-classic/how-to-install-altstore-windows) or [Mac](https://faq.altstore.io/altstore-classic/how-to-install-altstore-macos) guide.
2. Save the ZGTA V `.ipa` in Files. Keep AltServer reachable by USB or the same Wi-Fi.
3. In **AltStore Classic → My Apps**, use **+** to select the downloaded IPA. Complete any signing, trust and Developer Mode prompts from the setup guide.
4. Open ZGTA V and follow the [game-file setup](START-HERE.md#iphone--ipad--ios-150).

Free-account apps expire after seven days; keep them refreshed through AltStore/AltServer. [Official refresh guide](https://faq.altstore.io/altstore-classic/your-altstore).

This is the Classic IPA-import route. **ZGTA V has no AltStore PAL release**; PAL distributes notarized apps, rather than this downloadable IPA. [Official comparison](https://github.com/altstoreio/FAQ/blob/main/altstore-pal-v.-altstore-classic.md).

## SideStore — experimental

Use the same `.ipa`. Follow [SideStore's official setup guide](https://sidestore.io/), including its device-pairing and network requirements, then import the IPA using its app-install action. ZGTA V installation and gameplay through SideStore have not been tested.

## Why an installed IPA might still fail to play

ZGTA V requests a higher memory limit and extended virtual address space. A signing tool/profile may not preserve or authorize those requests, and device memory limits still apply. Apple documents [increased memory limits](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.kernel.increased-memory-limit) and [extended virtual addressing](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.kernel.extended-virtual-addressing).

The native engine is compiled ahead of time; this build does not require a separate JIT activation step. Its smaller memory-reservation fallback does **not** prove ordinary sideloading works. These are findings from the source and signing profile, not a successful Sideloadly or AltStore device test.

If installation is rejected, report the exact signing error. If the app opens but the game fails, export **Settings → Saves & support → Share log** and include the device, iOS version and signing method in a [report](TEST-REPORT.md). A launcher opening alone is not a gameplay test.

## Sileo / AppSync — experimental rootful route

For compatible **ARM64 rootful jailbreaks on iOS 15.0–18.2** without TrollStore. This package is not for RootHide or rootless.

1. Add `https://cydia.akemi.ai/` and `https://zemabinks.github.io/repo/` in Sileo.
2. Select **ZGTA V (AppSync installer - experimental)**.
3. Review the required dependencies: **AppSync Unified 116.0+**, **appinst 2.1.1+**, curl and coreutils. Let Sileo resolve them.
4. Install, then test the app with the compatible jailbreak active. Do not install both ZGTA V installer packages.

This route has not been tested on a device. If the official dependency server cannot be reached, installation cannot proceed. AppSync installation does not prove sufficient game memory, working gameplay or reboot persistence. [Installer details](https://github.com/zemabinks/repo/blob/main/docs/zgta-v-installation.md).
