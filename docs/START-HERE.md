# Install ZGTA V

[Downloads](https://github.com/zemabinks/ZGTA-V/releases/tag/v2.0.0-beta.2) · [Mods, graphics & multiplayer](PLAY-GUIDE.md) · [Help](#troubleshooting)

## Before you start

- **iPhone / iPad:** iOS / iPadOS **15.0 or later**. Your installation method must also support your exact device and OS version. See [iOS installation options](IOS-SIDELOADING.md).
- **Browser version:** a compatible Chrome/Edge browser and GPU. Windows, Linux and Android gameplay need community testing; Android support is especially limited.
- **Game files:** your own matching prepared game files and enough free storage to unpack them. No game files are supplied.

### Required game folder

The launcher expects this prepared format:

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

An ordinary Steam/Epic/Rockstar folder containing `GTA5.exe` is insufficient. This release does not include a tool to convert it. A compatible archive such as your own `mirror.rar` can contain the prepared folder. Keep a copy of your archive and saves. Allow room for both the archive and its extracted files.

<a id="2-iphone--ipad"></a>

## iPhone / iPad — iOS 15.0+

### TrollStore / TrollStore Lite

1. Confirm your device already has a compatible [TrollStore](https://github.com/opa334/TrollStore) or TrollStore Lite setup. **iOS 15.0 is the app minimum, not a promise that every later iOS version supports TrollStore.**
2. Download the [IPA](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.2/ZGTA-V-Build91-Archive-Access-TrollStore.ipa) and open it in TrollStore to install ZGTA V. Existing users: install over the existing app; do not delete it.
3. Open **ZGTA V → Game files → Choose a folder…** and select the folder containing your prepared files or archive.
4. If an archive is listed, tap **Unpack** and let installation finish. You can also use **Choose an archive…** to select the file directly.
5. If the game is already unpacked, select its folder and use **Check every file again**. Continue when the files are ready.

The `.tipa` download contains the same app as the `.ipa`; use `.ipa` for other sideloaders.

### Sileo

1. Open **Sileo → Sources** and add `https://zemabinks.github.io/repo/`.
2. Refresh Sources, then install **ZGTA V (TrollStore installer)**, version **0.96-1** (Build 96 candidate), with your existing compatible TrollStore / TrollStore Lite setup.
3. Open ZGTA V and follow the game-file steps above.

Sileo currently supplies the [Build 96 candidate](https://github.com/zemabinks/repo/releases/tag/zgta-v-build-96); the beta 2 manual downloads elsewhere in this guide remain the earlier release. The Sileo package does not install TrollStore for you. Removing the small installer package leaves ZGTA V and its data installed.

### Sideloadly, AltStore Classic or AppSync

Use the **same IPA**. These ZGTA V installation routes are **experimental and untested**. Follow the [separate step-by-step guide](IOS-SIDELOADING.md) for signing, refresh requirements and compatibility limits before trying them.

## Windows x64

1. Install a current Chrome or Edge browser with graphics acceleration enabled.
2. Download the [Windows ZIP](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.2/ZGTA-V-Build93-Windows-x64.zip) and extract the **whole** ZIP. Do not run it from inside the archive.
3. Open its `ZGTA-V` folder and double-click **Start ZGTA V.cmd**. Python is included.
4. Choose your prepared game folder when asked. Setup creates a **ZGTA V** shortcut on your Desktop. After this, double-click that shortcut to start the host and open the browser. Keep the launcher window open while playing.
5. If the browser does not open, visit `http://127.0.0.1:18887/`.
6. Open **Settings → Graphics → Check this GPU** before starting a game.

The browser runtime requires WebGPU, WebAssembly memory64, shared memory and BC texture compression. Unsupported GPUs cannot run it.

The desktop shortcut uses a private launcher copy, so moving the extracted download does not break it. Keep your separate game folder where you selected it. If ZGTA V is already running, the shortcut reopens the browser without restarting your game.

To stop the launcher, press Ctrl+C in its window. To choose a different game folder, stop it and run **Choose game folder.cmd**. If Windows Firewall asks while you host, allow the private network you intend to use.

## Mac / Linux

1. Install Python **3.9+** from [python.org](https://www.python.org/downloads/) or your OS package manager, and a compatible Chrome/Edge browser.
2. Extract the [Mac/Linux ZIP](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.2/ZGTA-V-Build93-Browser-Mac-Linux.zip).
3. Open Terminal in the extracted `ZGTA-V` folder and run:

```sh
sh "Start ZGTA V.command"
```

4. Paste the full path to your prepared game folder when asked. Spaces are accepted; do not add quotes around the path at that prompt.
5. Keep Terminal open. Visit `http://127.0.0.1:18887/` if the browser does not open, then choose **Settings → Graphics → Check this GPU**.

You can also pass the path directly:

```sh
sh "Start ZGTA V.command" --mirror "/full/path/to/prepared game folder"
```

On **Mac**, the first successful setup creates **ZGTA V.app** on your Desktop. Double-click it for future sessions: it starts the host in Terminal and opens Chrome if installed, or the default browser. The app uses a private launcher copy and remembers your game folder. Keep Terminal open while playing. **Linux** continues to use the command above.

The URL works only while the local host is running. Closing Terminal stops it; double-click the desktop app to start it again. Keep your game files in the folder you selected. If Desktop access is refused, the Start script still works; allow access through the normal macOS prompt/settings and run setup again.

Press Ctrl+C to stop. Run with `--choose-folder` to choose another folder while stopped. These packages run in your browser; they are not native Mac/Linux game apps.

## Android / Termux — experimental

There is **no APK**. Many Android GPUs cannot meet the browser requirements listed above.

1. Install Termux using its [official instructions](https://github.com/termux/termux-app#installation). Keep any Termux plugins from the same source.
2. In Termux, run `termux-setup-storage` and allow storage access.
3. Extract the [Android ZIP](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.2/ZGTA-V-Build93-Android-Termux.zip) into Downloads so its folder is `Downloads/ZGTA-V`.
4. Put your prepared game files in `Downloads/ZGTA-V/Game`, with `index.html`, `data` and `b` directly inside that folder.
5. Run:

```sh
bash ~/storage/downloads/ZGTA-V/Start-Android.sh
```

The script asks before installing Python if it is missing. Open `http://127.0.0.1:18887/` in Chrome if needed, then use **Check this GPU**. Keep Termux and Chrome active while playing; Android can stop background apps.

<a id="playing-with-friends"></a>
<a id="importing-mods"></a>
<a id="graphics"></a>

## Using ZGTA V

For playing from different networks, follow **[Remote play with Tailscale](REMOTE-PLAY.md)** for downloads and setup on both devices.

See the [host and join steps](PLAY-GUIDE.md#private-multiplayer), [mod imports](PLAY-GUIDE.md#import-mods) and [graphics settings](PLAY-GUIDE.md#change-graphics).

## Update without losing saves

- **iOS:** back up saves, then install the update over the existing app using the same installation method. Do not delete ZGTA V first. Switching signing accounts or installation methods can create a separate app or prevent an update; export backups before attempting a switch.
- **Browser:** back up saves and stop your launcher. Extract the new package and run its Start script once; Mac/Windows update the owned desktop launcher while keeping the earlier launcher copy for recovery. Keep your separate game folder, the same browser profile and the same address (`http://127.0.0.1:18887/`). Do not clear site data; saves belong to that browser profile and address.

See [save backups](PLAY-GUIDE.md#back-up-saves).

## Troubleshooting

| Problem | Try this |
|---|---|
| Archive cannot be opened | Select it directly with **Choose an archive…**, or select its containing folder again. If it is stored in a cloud provider, make sure it is downloaded locally. Keep the original archive and game files. |
| No complete game found | Check the folder layout above. Select a folder closer to the game files, then recheck. |
| Sileo shows Reinstall, cannot find the package or reports Install Identifier Mismatch | Clear the queued attempt, refresh Sources and reopen the package. Keep the app and saves installed. |
| TrollStore helper not found | Check that compatible TrollStore is already installed, or install the IPA manually through it. |
| Browser does not load | Keep its launcher window open and use the localhost address above. Close your previous launcher before starting another. |
| Unsupported GPU | Include **Check this GPU** results in a report. |
| No lobbies | Follow the [host and join guide](PLAY-GUIDE.md#private-multiplayer), including the network checks. |

Still stuck? [Report the exact error](TEST-REPORT.md), your device/OS and how you installed it. Review logs for personal information before posting. Do not upload game files or private saves.
