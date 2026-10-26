# ZGTA V 2.0 beta — by zema

Solo Story, Free Roam, and Private Multiplayer, with saves, compatible mods, and controller support. **Bring your own matching prepared game files.** No commercial game data is included.

## Choose your download

| Device | Download | What it is | Current test status |
|---|---|---|---|
| iPhone / iPad with compatible TrollStore | [iOS TrollStore `.ipa`](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.1/ZGTA-V-Build91-Archive-Access-TrollStore.ipa) | Native iOS app, version 2.0 / Build 91 | Installation and launcher previously confirmed; repaired archive workflow owner-confirmed on the tested iPhone. Broader gameplay acceptance pending. |
| Compatible jailbroken iPhone / iPad using Sileo | Add [Zema's Repo](https://zemabinks.github.io/repo/), install **ZGTA V (TrollStore installer)** | A small installer that passes the pinned IPA to your existing TrollStore / TrollStore Lite | Existing RootHide route tested. It does not install TrollStore for you. |
| Windows x64 | [Windows x64 ZIP](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.1/ZGTA-V-Build92-Windows-x64.zip) | Portable local browser host, including Python's actual `python.exe` | Alpha / community test. Package and HTTP checks on Mac; Windows execution and gameplay pending. |
| Mac / Linux | [Browser Mac Linux ZIP](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.1/ZGTA-V-Build92-Browser-Mac-Linux.zip) | Local browser host using your installed Python 3.9+ | Beta host. macOS startup/HTTP checks; Linux and current gameplay pending. |
| Android | [Android Termux ZIP](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.1/ZGTA-V-Build92-Android-Termux.zip) | Experimental local browser host starter | Alpha / compatibility testing. **No APK**, no physical Android validation; many GPUs lack required features. |

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
4. If you already have extracted matching files, select their folder and recheck. Wait for the folder to be marked ready.
5. For Solo Story or Free Roam, choose **On my own → Story mode / Free roam**, then **Play**. For Private Multiplayer, follow [Playing with friends](#playing-with-friends).

### Sideloadly, AltStore Classic, and SideStore

**Can I use the same IPA?** These tools accept IPA files, but this exact Build 91 release has not been verified with them. The download is the TrollStore build; there is no separately tested standard-sideloading IPA in this release.

The project's TrollStore signing configuration requests **Increased Memory Limit** and **Extended Virtual Addressing**. Re-signing may change which permissions the app receives. A successful installation alone does not establish that game startup, available memory, or gameplay will work. A paid developer account alone is not proof of compatibility either.

If you want to test the existing IPA:

1. Back up any existing ZGTA V saves first. Keep a working TrollStore installation intact; changing signing methods is not a verified in-place update.
2. Download the `.ipa` linked above, not the `.tipa` alias.
3. Choose one installer:
   - **[Sideloadly](https://sideloadly.io/):** install it on your Mac or PC, connect and trust your iPhone, select the device and IPA, sign in with your Apple account, then start installation.
   - **[AltStore Classic](https://faq.altstore.io/):** complete its official setup with AltServer, then import the IPA from **My Apps** using **+**. This refers to Classic.
   - **[SideStore](https://sidestore.io/):** complete its official setup, including its pairing/network requirements, then import the IPA through its app-install action.
4. Follow the installer's instructions for trusting your developer profile and enabling Developer Mode when required by your iOS version.
5. If installation succeeds, open ZGTA V and follow the game-file steps above. Start with low graphics settings. Report signing errors or crashes with your device, iOS version, installer, and account type.
6. With a free Apple account, refresh the app before its seven-day signature expires. Keep the same Apple account and signing identity when updating, and back up saves first. See the [Sideloadly FAQ](https://sideloadly.io/faq) and [AltStore refresh guide](https://faq.altstore.io/altstore-classic/your-altstore).

Until this build has been tested through those installers, TrollStore remains the documented tested route.

### Install / update with Sileo

1. In Sileo → Sources, add `https://zemabinks.github.io/repo/` and refresh.
2. Install **ZGTA V (TrollStore installer)**, wrapper **0.91-1**, with existing compatible TrollStore / TrollStore Lite. 
3. Open ZGTA V and follow the game-file steps above. Removing the small Sileo installer wrapper does not remove your app or its game data.

If Sileo says Reinstall, cannot find the package, or reports **Install Identifier Mismatch**, clear that queued attempt, refresh Sources and reopen the package. This resolved the owner's earlier stale selection. Do not remove the app or saves to fix the queue.

The separate **AppSync installer** is an **untested experimental rootful ARM64 route** with a specific supported firmware/dependency range. It is not a RootHide/rootless conversion and is not a fallback for every unsupported phone. Fresh dependency-server availability remains unverified. Do not install both wrappers or assume AppSync alone satisfies this app's runtime entitlement requirements.

## 3. Windows x64

1. Install a current Chrome or Edge browser with graphics acceleration available.
2. Extract the **whole** Windows ZIP. Open the `ZGTA-V` folder and double-click **Start ZGTA V.cmd**. Do not run files from inside the ZIP.
3. Select the matching prepared game folder when asked. Python 3.13.16 is bundled; no separate Python install is required.
4. Keep the launcher window open. It opens `http://127.0.0.1:18887/`. If it does not open, visit that address manually.
5. In Settings → Graphics choose **Check this GPU**. The runtime requires WebGPU, WebAssembly memory64, shared memory and BC texture compression. Unsupported hardware is reported; a 60 FPS cap is not a speed guarantee.
6. Select a mode and press its green Play button. Ctrl+C stops the host. **Choose game folder.cmd** changes the remembered folder while stopped.

For hosting, allow your intended private network if Windows Firewall prompts. This package changes no firewall rule and installs no Windows service. Real Windows startup, firewall, input and gameplay remain community tests.

## 4. Mac / Linux browser host

Install Python 3.9+ from [python.org](https://www.python.org/downloads/) or your OS package manager, plus a compatible Chrome/Edge browser. Extract the ZIP. In Terminal change into its `ZGTA-V` folder and run:

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

### Create a lobby

1. Open **With friends → Join or create → Create a lobby**.
2. Choose **Same Wi-Fi / LAN** for devices on the same local network, or **Remote / Tailscale** when using a configured Tailscale connection.
3. Complete the host settings, return to the launcher, and press **Host Multiplayer**.
4. Share the generated invite with your friends. Keep the host app or browser host running while you play.

For remote play, everyone must be able to reach the host through the private network. Set up Tailscale and grant the required network access first; ZGTA V does not configure it for you. An existing WireGuard connection that reaches the host's LAN can use **Same Wi-Fi / LAN** with that reachable LAN address.

### Join with an invite

1. Open **With friends → Join or create → Join a friend**.
2. Enter the host's invite/address and use the same room.
3. Return to the launcher and press **Play Multiplayer**.

Use the host's reachable LAN or Tailscale address, not `127.0.0.1` from another device.

### Join from the lobby list

1. Open **Find lobby → Online**.
2. Select an available room and use **Join**.
3. If returned to the launcher, press **Play Multiplayer** to start.

Use the heart to save a room to **Favorites**. An offline favorite cannot be joined. If a friend's room is missing, confirm that the host is running and reachable, then try their invite directly.

Each device needs its own multiplayer character identity. Two-device gameplay and recovery after connection loss are still being tested.

## Saves, mods and controls

**Update safely:** keep the same app/browser profile and address, back up saves first, then install over the existing app or replace only the extracted launcher package while stopped. Game files are separate. Browser saves are tied to the origin (`http://127.0.0.1:18887/`) and browser profile; changing either creates a different storage location. Do not clear browser site data.

**Saves:** use Settings → Saves on browser or Settings → Saves & support on iOS. Story, free roam and multiplayer profiles are separate. New backups use `.zgtasave`; legacy `.mugoatsave` imports remain supported for existing owners. Import checks structure and backs up matching existing files; it does not convert newer GTA save versions or guarantee that every save loads. Close the game before imports. Do not share one imported multiplayer identity between simultaneously playing devices.

### Importing mods

Import mods before starting a game and keep a copy of the original pack.

**iOS**

1. Open **Mods → Import Mod from file**.
2. Select the mod or archive in Files.
3. Read **Mod Import Results** and check that the mod appears in the list.
4. Select the mod to enable or disable it. Restart the app when a change is marked for the next launch.

You can also copy supported files into **Files → On My iPhone → ZGTA V → mods**, then refresh the mod list. A file appearing in the manager does not prove that its code or content is supported; arbitrary Windows DLL/ASI/ScriptHook mods are not compatible just because they can be imported.

**Browser**

1. Open **Mods → Import DLC pack**.
2. Select an open GTA V Legacy vehicle/character DLC `.rpf`, or a ZIP containing compatible DLC packs (up to 256 MiB per import).
3. Wait for validation, then enable the pack in the list.
4. Start a new game session to apply it.

Browser mods apply to Solo Story and Free Roam; private multiplayer uses the original assets. Encrypted/Enhanced packs, ASI/script plugins, loose-file replacements, and non-ZIP archives are unsupported by the browser importer.

### Graphics

1. Open **Settings → Graphics & FPS** on iOS, or **Settings → Graphics** in the browser launcher.
2. Choose a detail preset, resolution, and frame-rate cap. Start with the recommended preset on iOS; reduce detail or resolution if play is slow.
3. On iOS, resolution changes apply immediately, while preset and frame-rate changes apply the next time you start the game. Browser graphics changes apply on the next launch.

Higher resolution and detail require more memory and GPU power. A 60 FPS cap does not guarantee 60 FPS. In the browser, use **Check this GPU** if the game reports unsupported graphics.

**Controls:** browser supports keyboard/mouse and standard Gamepad API controllers; iOS retains touch and supported controller settings. Pair controllers in the OS first. Controller feel, audio, performance and two-device multiplayer need real-device beta feedback.

## Troubleshooting and reports

- **Archive cannot be opened / Operation not permitted:** reselect the containing folder for a fresh Files grant, or select the archive directly. Keep the archive and existing game. Build 91 repairs the discovered-archive access path; the owner confirms it now works.
- **Ready changed to unavailable:** reattach/reselect the external folder or provider and recheck. Empty or incomplete folders must not count as a usable install.
- **Browser won't load / port busy:** keep the existing host window open, use the same localhost URL, and close your own previous launcher before restarting. The starter does not kill another process.
- **Unsupported GPU:** report the result from Check this GPU. Do not change OS security settings or browser experimental flags based on a guess.
- **No lobbies:** confirm the host is actually running, the private route works, and the room is advertised. Add an invite explicitly; Offline is kept only in Favorites.
- **Installer helper not found:** confirm compatible TrollStore is installed, share the installer error text, or use the same IPA manually. Never send passwords or signing keys.

Use [TEST-REPORT.md](TEST-REPORT.md) for a report. Include platform, OS, GPU/device, package/version, steps and exact error. Attach the current app log or launcher diagnostics after reviewing personal paths/addresses. State whether the issue is setup, game start, saves, mods, input or multiplayer. Do not upload game data or private saves publicly.

## Test status

This is a beta. See [VERIFICATION.md](VERIFICATION.md) for tested platforms and remaining checks.
