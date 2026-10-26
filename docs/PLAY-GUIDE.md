# Mods, graphics and multiplayer

[Installation](START-HERE.md) · [Downloads](https://github.com/zemabinks/ZGTA-V/releases/tag/v2.0.0-beta.2)

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

1. Open **Settings → Graphics & FPS** on iOS, or **Settings → Graphics** in the browser.
2. Start with the recommended preset. In the browser, run **Check this GPU** first.
3. For smoother play, try a lower preset or resolution. Change one setting at a time so you can compare.
4. Choose your frame-rate cap. A higher cap does not guarantee the device can reach it.

On iOS, resolution can change during play; preset and frame-rate changes require restarting the game. Browser graphics settings apply on the next launch. If iOS reports that it cannot reserve engine memory, try a lower **Game Memory** value; the minimum setting is 3 GB. This cannot raise the memory allowance granted by iOS or your signing method.

## Private Multiplayer

Every player needs matching prepared game files. The host must remain online with ZGTA V open; iOS hosting stops when the app leaves the foreground.

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

### Join from the lobby list

1. Open **With friends → Find lobby** and choose your network.
2. Refresh or search LAN, then select an available lobby under **Online**.
3. Confirm your player details and connection, then press **Play Multiplayer**.
4. Tap the heart to save a lobby under **Favorites**. Offline favorites stay saved, but cannot be joined until the host is online.

If a lobby is missing, ask the host to start it and send an invite. Check the network/VPN connection on both devices. On Windows, check that the host was allowed through the firewall on the intended private network. If changing host or room after connecting requires it, reopen ZGTA V first.

## Back up saves

Open **Settings → Saves & support** on iOS, or **Settings → Saves** in the browser, and export a backup before updating or importing saves. Story, Free Roam and multiplayer progress are separate.

Keep the same browser profile and localhost address when playing in a browser. Close the game before importing a backup. Each simultaneously playing multiplayer device needs its own character identity; do not clone one save across active players.

## Controllers

Pair your controller in the device's OS first, then open **Settings → Controls**. Browser play also supports keyboard and mouse. Device-specific controller, audio and gameplay feedback is welcome through the [report template](TEST-REPORT.md).
