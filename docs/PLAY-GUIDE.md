# Mods, graphics and multiplayer

[Installation](START-HERE.md) · [Downloads](https://github.com/zemabinks/ZGTA-V/releases/tag/v2.0.0-beta.3)

## Import mods

Import new packs before starting a game. Use compatible, unencrypted GTA V Legacy add-on/DLC `.rpf` packs. Arbitrary Windows `.asi`, DLL and ScriptHook mods do not run here.

### iOS

1. On the home screen, tap **Open Mods**.
2. Choose **Import Mod from file** and select your pack or archive in Files.
3. Read **Mod Import Results**, then check **Installed Mods**. A copied file is not necessarily a loadable pack; the manager identifies incompatible files.
4. Tap an installed mod to enable or disable it. Restart the app when changes are marked pending, then launch Solo Story or Free Roam.

You can also manage files in **Files → On My iPhone → ZGTA V → mods**. Keep a copy of the original pack.

### Browser

1. Open **Mods → Import DLC pack**.
2. Select a compatible `.rpf`, or a `.zip` containing DLC packs. The import limit is **256 MiB** per file.
3. After validation, enable the pack using its checkbox.
4. Start Solo Story or Free Roam. Changes apply on the next launch; browser Private Multiplayer uses the original assets.

If a mod causes a problem, disable it and relaunch before changing other settings.

## Change graphics

1. Open **Settings → Graphics & FPS** on iOS, or **Graphics** in the main browser navigation.
2. Start with the recommended preset. In the browser, run **Check this GPU** first.
3. For smoother play, try a lower preset or resolution. Change one setting at a time so you can compare.
4. Choose your frame-rate cap. A higher cap does not guarantee the device can reach it.

On iOS, resolution can change during play; preset and frame-rate changes require restarting the game. Browser graphics settings apply on the next launch. **Memory management** has independent Automatic, Standard and Reduced choices; selecting a graphics preset does not lock memory management to that preset. Reduced mode limits optional prefetch and releases completed idle graphics storage earlier. It can help reduce resource pressure, but a physical 3 GB device performance improvement has not been measured. If iOS reports that it cannot reserve engine memory, try a lower **Game Memory** value; the minimum setting is 3 GB. This cannot raise the memory allowance granted by iOS or your signing method.

## Private Multiplayer

Every player needs matching prepared game files. A lobby created inside ZGTA V needs the hosting app to remain open; iOS hosting stops when the app leaves the foreground. The optional standalone Mac relay below can keep the relay available while GTA is closed.

For remote setup, start with the **[Tailscale download, host and join guide](REMOTE-PLAY.md)**.

### Choose your network

- **LAN / Same Wi-Fi:** use the host's local network address. Both players must be able to reach that network.
- **Remote / Tailscale:** connect each device to the same permitted Tailscale network before opening the lobby. Use the host's Tailscale address.
- **Existing WireGuard access to the host's LAN:** use the reachable LAN address under **LAN / Same Wi-Fi**.

Use the host's LAN or Tailscale address when joining from another device; `127.0.0.1` always refers to the device you are using. The lobby list is for reachable private hosts. It is not worldwide matchmaking.

### Create a lobby

1. Open **With friends → Join or create → Create a lobby**.
2. Select LAN or Remote, enter a room name and player name, and complete the setup. On iOS, Remote hosting also asks for this device's Tailscale address.
3. Confirm with **Create lobby** on iOS or **Use this setup** in the browser, then press **Host Multiplayer** to enter the game.
4. Use **Copy invite** in the hosting controls and send the invite to your friends. Keep the host running while they play.

### Join by invite

1. Open **With friends → Join or create → Join a friend**.
2. Select the matching network type and paste the host's invite. Or enter its address and the same room name manually.
3. Enter your player name. On iOS, press **Connect**; in the browser, press **Use this setup**.
4. Press **Play Multiplayer**.

### Optional standalone Mac relay

Most players can use **Multiplayer → Create a lobby** without downloading extra tools. This optional package is for a Mac that should keep a relay available independently of the game, including managed ZRemote setups. It forwards multiplayer traffic and does not run the GTA world.

For that standalone relay, download [relay controls 1.1](https://github.com/zemabinks/ZGTA-V/releases/download/v2.0.0-beta.3/ZGTA-V-Relay-Controls-1.1.zip) and extract the ZIP. Use **Relay Off.command** from the updated package to stop your owned older relay, then **Relay On.command** to install/start the new helper. Stop only when no players are using it. The commands preserve the existing private configuration; no game files are copied. A ZRemote bundle must contain the updated helper too, or its own start action may restore an older helper.

The updated managed host advertises an empty **LOS-SANTOS** room before anyone joins. Its actual announced port is used; clients do not scan every network port. Keep the Mac awake and logged in. LAN discovery depends on local-network permission and multicast reachability. Isolated guest Wi-Fi can prevent discovery; use an invite/address when needed.

### Join from the lobby list

1. Open **With friends → Find lobby** and choose your network.
2. Refresh or search LAN, then select an available lobby under **Online**.
3. Confirm your player details and connection, then press **Play Multiplayer**.
4. Tap the heart to save a lobby under **Favorites**. Offline favorites stay saved, but cannot be joined until the host is online.

Nearby LAN hosts must advertise their ZGTA service to appear automatically. Updated managed Mac relays are discoverable with zero players. If a lobby is missing, confirm the host is using relay controls 1.1 or send an invite. Check the network/VPN connection on both devices. On Windows, check that the host was allowed through the firewall on the intended private network. If changing host or room after connecting requires it, reopen ZGTA V first.

## Back up saves

Open **Settings → Saves & support** on iOS, or **Saves** in the main browser navigation, and export a backup before updating or importing saves. Story, Free Roam and multiplayer progress are separate.

Keep the same browser profile and localhost address when playing in a browser. Close the game before importing a backup. Each simultaneously playing multiplayer device needs its own character identity; do not clone one save across active players.

## Controllers

Pair your controller in the device's OS first, then open **Settings → Controls**. Browser play also supports keyboard and mouse. Device-specific controller, audio and gameplay feedback is welcome through the [report template](TEST-REPORT.md).

## Proximity voice

In Engine LAN multiplayer, the existing **microphone** button switches your transmission on/off. The **speaker** button switches nearby voice playback on/off independently of game audio. The microphone starts off; allow access when you choose to enable it. Other players need a voice-capable build too.

Voice stays full-volume within 2 metres, becomes clearly quieter at 10 and 20 metres, and is silent at 35 metres. Movement changes are smoothed. Each listener’s build controls the distance curve they hear, so update both clients for the same behavior.

On the browser, open the local launcher address or use HTTPS for microphone access. Keep the game tab visible. Hiding it pauses voice, and you must enable voice again on return. iPhone/Mac speech and distance behavior passed owner tests; Bluetooth and interruption routes remain unverified.
