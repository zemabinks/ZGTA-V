# Remote play with Tailscale

Use this guide to host or join a private ZGTA V lobby from different networks. Every player needs ZGTA V and their own matching prepared game files.

## 1. Download Tailscale on both devices

Install it on the device hosting the lobby and on every device joining.

| Device | Download | Setup help |
|---|---|---|
| iPhone / iPad | [Tailscale on the App Store](https://apps.apple.com/app/tailscale/id1470499037) | [iOS setup](https://tailscale.com/docs/install/ios) |
| Windows PC | [Download for Windows](https://tailscale.com/download/windows) | [Windows setup](https://tailscale.com/docs/install/windows) |
| Mac | [Download for Mac](https://tailscale.com/download/mac) | [Mac setup](https://tailscale.com/docs/install/mac) |
| Android | [Download for Android](https://tailscale.com/download/android) | [Android setup](https://tailscale.com/docs/install/android) |
| Linux | [Download for Linux](https://tailscale.com/download/linux) | [Linux setup](https://tailscale.com/docs/install/linux) |

**iOS version check:** ZGTA V requires iOS 15.0+, but the current Tailscale [App Store listing](https://apps.apple.com/app/tailscale/id1470499037) requires **iOS / iPadOS 16.6+** as checked on 26 October 2026. Tailscale's older iOS guide still says 15.0; check the store requirement for the version you can actually install. An older compatible Tailscale installation is not tested here. You can still use LAN, or an existing working WireGuard route to the host's LAN, without Tailscale.

Current Tailscale desktop requirements are listed in its guides: Windows 10+ and macOS 12+. These are separate from ZGTA V's requirements. Android game/GPU support remains experimental even if Tailscale installs.

## 2. Connect Tailscale

1. Open Tailscale and sign in. On phones and Mac, complete its VPN-configuration prompt.
2. Turn the connection on and leave Tailscale connected while playing. On Windows, use its system-tray menu; on Mac, use its menu-bar app.
3. For two devices you personally own, use your own account on both. A friend should use their own account and the sharing or invitation steps below.

[Tailscale quickstart](https://tailscale.com/kb/1017/install/) has the platform setup details.

## 3. Give your friend access to the host

### Share just the hosting device

This is useful when a friend only needs to join your game host.

1. The host opens the [Tailscale Machines page](https://login.tailscale.com/admin/machines).
2. Find the device that will run the ZGTA V lobby, select **Share**, and send a share invitation to the friend.
3. The friend accepts it using their own Tailscale account and connects Tailscale on their playing device.
4. Confirm the host device appears for that friend. Access policies must permit the connection.

This shares the selected machine rather than inviting the friend into the whole network. Use the [official machine-sharing guide](https://tailscale.com/docs/features/sharing) if your console presents different sharing options. Check your [plan's current limits](https://tailscale.com/pricing); this guide does not promise unlimited users or devices.

### Already using the same Tailscale network?

Skip device sharing if both players already have permitted access to the host. To invite a friend as a network member instead, the administrator uses **[Users](https://login.tailscale.com/admin/users) → Invite external users**, selects **Member**, then sends the invitation. The friend accepts with their own account, selects that network and connects their device. Approve the user/device if the network requires it. This can grant broader access under your network policy; [inviting versus sharing](https://tailscale.com/docs/reference/inviting-vs-sharing) explains the difference. [Official invitation steps](https://tailscale.com/docs/features/sharing/how-to/invite-any-user).

There are **two separate invites**: the Tailscale invitation grants network access; the ZGTA V invite below identifies the game lobby. A game invite alone does not grant Tailscale access.

## 4. Host creates the lobby

1. While Tailscale is connected, find the hosting device in Tailscale and copy its **100.x IPv4 address**. Use the host's address, not the joining player's. ZGTA V's current Remote fields expect that IPv4 address; use it rather than a MagicDNS hostname.
2. Open ZGTA V. On a computer, start its local launcher/desktop app too.
3. Choose **With friends → Join or create → Create a lobby → Remote** (or **Remote / Tailscale** in the browser).
4. Enter the room name and your player name. On iPhone/iPad, also enter that phone's own Tailscale address when asked.
5. Confirm **Create lobby** on iOS or **Use this setup** in the browser, then press **Host Multiplayer**.
6. Open the hosting controls and use **Copy invite**. Send the complete game invite to your friend; it contains the address, port and room.

Keep the computer awake and its launcher running. On **iPhone/iPad, hosting stops when ZGTA V leaves the foreground**. After switching to Messages to send an invite, return to ZGTA V and start hosting again if it stopped. Arrange Tailscale access before starting the phone lobby.

## 5. Friend joins

1. Keep Tailscale connected and confirm you have access to the host.
2. Open ZGTA V and choose **With friends → Join or create → Join a friend → Remote**.
3. Paste the complete ZGTA V invite and enter your player name. If entering details manually, use the host's **100.x address**, the displayed port and the exact same room name.
4. Press **Connect** on iOS or **Use this setup** in the browser, then **Play Multiplayer**.

A manual address looks like `ws://100.101.102.103:47540/engine-lan` — this is only an example; replace it with the host's actual address and port. The browser may choose ports 47541–47543 if 47540 is busy. Prefer the copied invite.

### Use Find lobby

Open **With friends → Find lobby → Remote → Online** and refresh. Select an available room, confirm your player/connection details, then **Play Multiplayer**. Remote browsing does not list every Tailscale user's game. If the host is missing, use their invite directly or **Add invite**, then save it with the heart under **Favorites**. Offline favorites cannot be joined.

## If it will not connect

- Check Tailscale is connected on **both playing devices**, the share/member invitation was accepted, and the host is online.
- Check the host actually started a lobby; a running localhost web page alone is not a hosted multiplayer room.
- Recopy the invite after the host changes network/address or restarts on a different port. Use the host's Tailscale address, not a home LAN address under Remote, your public internet IP, or `127.0.0.1`.
- Check the host firewall and Tailscale access policy permit the invite's **TCP port** from the permitted players. iOS normally hosts on 47540; the browser can use 47540–47543. Keep access limited to the intended private players/network.
- Each player's `http://127.0.0.1:18887/` is their **own** local browser launcher. Do not give that localhost URL to your friend as the lobby address.
- For an existing FritzBox/WireGuard route to the host LAN, use **LAN / Same Wi-Fi** and the reachable LAN address instead. Tailscale is optional for that route.

This setup uses the private Tailscale connection; it does not require publishing your game server through a router port-forward or Tailscale Funnel. Two-device gameplay and remote recovery still need beta testing. [Report a connection problem](TEST-REPORT.md) with both device versions and the exact error; keep private invites and addresses out of public logs.
