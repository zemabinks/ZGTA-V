# ZGTA V 2.0 beta — by zema

A GTA V port with a Pure Black launcher, solo play, private multiplayer, local saves, compatible mods and controller settings. **Bring your own matching prepared game files.** No commercial game data is included.

## Choose your download

| Device | Download | What it is | Current test status |
|---|---|---|---|
| iPhone / iPad with compatible TrollStore | iOS TrollStore `.ipa` | Native iOS app, version 2.0 / Build91 | Installation and launcher previously confirmed; repaired archive workflow owner-confirmed on the tested iPhone. Broader gameplay acceptance pending. |
| Compatible jailbroken iPhone / iPad using Sileo | Add [Zema's Repo](https://zemabinks.github.io/repo/), install **ZGTA V (TrollStore installer)** | A small installer that passes the pinned IPA to your existing TrollStore / TrollStore Lite | Existing RootHide route tested. It does not install TrollStore for you. |
| Windows x64 | Windows x64 ZIP | Portable local browser host, including Python's actual `python.exe` | Alpha / community test. Package and HTTP checks on Mac; Windows execution and gameplay pending. |
| Mac / Linux | Browser Mac Linux ZIP | Local browser host using your installed Python3.9+ | Beta host. macOS startup/HTTP checks; Linux and current gameplay pending. |
| Android | Android Termux ZIP | Experimental local browser host starter | Alpha / compatibility testing. **No APK**, no physical Android validation; many GPUs lack required features. |

The native iOS app and browser launcher share features but use different renderers and save storage. A Windows game `.exe` and native Android app are not provided. ZPlay is the wider games website; this port is **by zema (zemabinks)**.

## 1. Check your game files first

This release expects the existing **prepared mirror format**, not an ordinary Steam/Epic/Rockstar installation folder:

```text
prepared-game-folder/
  index.html
  data/
    manifest.json
    common/...
  b/
    8b0b5899ed/
      game.wasm
      game.js
      loader.js
      io_worker.js
      ...
```

The launcher validates the matching pinned build. A folder with only `GTA5.exe`, or a different mirror version, is insufficient. A compatible archive such as your own `mirror.rar` may contain a wrapping folder; iOS searches beneath the selected directory. No download of commercial game files or conversion of arbitrary retail installs is supplied. Keep an original copy of your archive and saves. Large archives need enough free storage for the extracted content as well as the archive while it is retained.

## 2. iPhone / iPad

### Existing compatible TrollStore (recommended tested route)

1. Check that your device already supports and runs [official TrollStore](https://github.com/opa334/TrollStore). This app cannot make an unsupported iOS version compatible.
2. Download the iOS `.ipa` from this release and open it in TrollStore. Existing users should update the same app **without deleting it**. The bundle identifier remains `com.zemabinks.gtamp.enginelanlab`.
3. Open **ZGTA V**. Tap **Game files** at the top right. Choose the containing folder in Files, allow access, then select the discovered archive and **Unpack**. Or use **Choose an archive…** to select the archive directly.
4. If you already have extracted matching files, select their folder and recheck. Only a validated usable folder is marked ready. External archives are retained; consuming app-owned archives is an explicit separate choice.
5. Choose **On my own → Story mode / Free roam**, then press the green Play button. Or use **With friends**, configure a lobby, then press the green **Play Multiplayer / Host Multiplayer** button.

A `.tipa`, if supplied, contains the exact same ZIP/IPA bytes under a TrollStore file extension; it is not a different build. The owner-confirmed archive test used the Build91 update; no separate `.tipa` installation test is claimed.

### Install / update with Sileo

1. In Sileo → Sources, add `https://zemabinks.github.io/repo/` and refresh.
2. Install **ZGTA V (TrollStore installer)**, wrapper **0.91-1**, with existing compatible TrollStore / TrollStore Lite. It verifies the IPA byte count and SHA-256 before calling the native helper.
3. Open ZGTA V and follow the game-file steps above. Removing the small Sileo installer wrapper does not remove your app or its game data.

If Sileo says Reinstall, cannot find the package, or reports **Install Identifier Mismatch**, clear that queued attempt, refresh Sources and reopen the package. This resolved the owner's earlier stale selection. Do not remove the app or saves to fix the queue.

The separate **AppSync installer** is an **untested experimental rootful ARM64 route** with a specific supported firmware/dependency range. It is not a RootHide/rootless conversion and is not a fallback for every unsupported phone. Fresh dependency-server availability remains unverified. Do not install both wrappers or assume AppSync alone satisfies this app's runtime entitlement requirements.

## 3. Windows x64

1. Install a current Chrome or Edge browser with graphics acceleration available.
2. Extract the **whole** Windows ZIP. Open the `ZGTA-V` folder and double-click **Start ZGTA V.cmd**. Do not run files from inside the ZIP.
3. Select the matching prepared game folder when asked. Python3.13.16 is bundled; no separate Python install is required.
4. Keep the launcher window open. It opens `http://127.0.0.1:18887/`. If it does not open, visit that address manually.
5. In Settings → Graphics choose **Check this GPU**. The runtime requires WebGPU, WebAssembly memory64, shared memory and BC texture compression. Unsupported hardware is reported; a 60 FPS cap is not a speed guarantee.
6. Select a mode and press its green Play button. Ctrl+C stops the host. **Choose game folder.cmd** changes the remembered folder while stopped.

For hosting, allow your intended private network if Windows Firewall prompts. This package changes no firewall rule and installs no Windows service. Real Windows startup, firewall, input and gameplay remain community tests.

## 4. Mac / Linux browser host

Install Python3.9+ from [python.org](https://www.python.org/downloads/) or your OS package manager, plus a compatible Chrome/Edge browser. Extract the ZIP. In Terminal change into its `ZGTA-V` folder and run:

```sh
sh "Start ZGTA V.command"
```

Paste the full prepared-folder path when prompted, without wrapping a pasted path in quotes. Spaces are accepted. Or supply it explicitly:

```sh
sh "Start ZGTA V.command" --mirror "/full/path/to/prepared game folder"
```

Keep Terminal open; visit `http://127.0.0.1:18887/`. Use `--choose-folder` to select a different folder while stopped. No service or system dependency is silently installed. These ZIPs are browser hosts, not native Mac/Linux game binaries.

## 5. Android / Termux alpha

This is for compatibility testers. The renderer's BC texture compression / memory64 requirements exclude many phones even when Chrome offers WebGPU.

1. Follow [official Termux installation instructions](https://github.com/termux/termux-app#installation). Keep Termux plugins from the same source.
2. Run `termux-setup-storage` once and approve its storage prompt.
3. Extract the Android ZIP so its folder is `Downloads/ZGTA-V`. Put your matching prepared game files in `Downloads/ZGTA-V/Game` with `index.html`, `data` and `b` directly inside it.
4. In Termux run:

```sh
bash ~/storage/downloads/ZGTA-V/Start-Android.sh
```

It asks before installing Termux Python if missing. Open `http://127.0.0.1:18887/` in Chrome if needed and use **Check this GPU**. Keep Termux and Chrome active. Android may suspend background hosts; unattended hosting is not promised. No APK, Play Store build or Android gameplay certification is included.

## Playing with friends

- **Join or create** opens Join a friend / Create a lobby. Configuring an address or role does not start the game. The last step is always the green **Play Multiplayer** or **Host Multiplayer** button.
- Same Wi-Fi / LAN uses the host's reachable private LAN address. The host must keep the app or local host running. Share the generated invite and use the same room.
- The current **Remote / Tailscale** option uses a reachable Tailscale address. If an existing FritzBox/WireGuard connection routes you onto the host LAN, use that reachable LAN address under **Same Wi-Fi / LAN**. This release does not configure WireGuard, Tailscale, router forwarding or a public matchmaking service.
- **Find lobby → Online** lists fresh compatible advertised rooms. A recent address or responding relay is not proof that a room exists.
- Tap the heart or add an invite to **Favorites**. Saved offline rooms stay there, with Join disabled. Saving a favorite does not grant network access.
- Each device needs its own multiplayer character identity. A network reconnection is not a promise of seamless game-world recovery. No GTA menu automation is used.

## Saves, mods and controls

**Update safely:** keep the same app/browser profile and address, back up saves first, then install over the existing app or replace only the extracted launcher package while stopped. Game files are separate. Browser saves are tied to the origin (`http://127.0.0.1:18887/`) and browser profile; changing either creates a different storage location. Do not clear browser site data.

**Saves:** use Settings → Saves on browser or Settings → Saves & support on iOS. Story, free roam and multiplayer profiles are separate. New backups use `.zgtasave`; legacy `.mugoatsave` imports remain supported for existing owners. Import checks structure and backs up matching existing files; it does not convert newer GTA save versions or guarantee that every save loads. Close the game before imports. Do not share one imported multiplayer identity between simultaneously playing devices.

**Mods:** open Mods, import a compatible pack and inspect the validation result. Only formats supported by the current mod manager are accepted; this is not support for arbitrary Windows `.asi`/DLL/ScriptHook mods. Changes requiring restart are queued. Keep original packs; a pack's success on desktop GTA does not prove compatibility here.

**Controls:** browser supports keyboard/mouse and standard Gamepad API controllers; iOS retains touch and supported controller settings. Pair controllers in the OS first. Controller feel, audio, performance and two-device multiplayer need real-device beta feedback.

## Troubleshooting and reports

- **Archive cannot be opened / Operation not permitted:** reselect the containing folder for a fresh Files grant, or select the archive directly. Keep the archive and existing game. Build91 repairs the discovered-archive access path; the owner confirms it now works.
- **Ready changed to unavailable:** reattach/reselect the external folder or provider and recheck. Empty or incomplete folders must not count as a usable install.
- **Browser won't load / port busy:** keep the existing host window open, use the same localhost URL, and close your own previous launcher before restarting. The starter does not kill another process.
- **Unsupported GPU:** report the result from Check this GPU. Do not change OS security settings or browser experimental flags based on a guess.
- **No lobbies:** confirm the host is actually running, the private route works, and the room is advertised. Add an invite explicitly; Offline is kept only in Favorites.
- **Installer helper not found:** confirm compatible TrollStore is installed, share the installer error text, or use the same IPA manually. Never send passwords or signing keys.

Use [TEST-REPORT.md](TEST-REPORT.md) for a report. Include platform, OS, GPU/device, package/version, steps and exact error. Attach the current app log or launcher diagnostics after reviewing personal paths/addresses. State whether the issue is setup, game start, saves, mods, input or multiplayer. Do not upload game data or private saves publicly.

## Verification scope

This is a public **beta**, not full platform certification. iOS version2.0 / Build91 is the unchanged, byte-verified archive-access candidate now owner-confirmed for that workflow. Browser source/packages use revision92 and preserve the existing engine/renderer byte set. Windows/Android/Linux hardware gameplay, full upgrade/save retention, two-device multiplayer, performance comparisons and reboot persistence are still open. See [VERIFICATION.md](VERIFICATION.md). No paid GitHub Actions are used.
