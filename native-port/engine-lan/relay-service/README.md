# ZGTA V LAN relay controls

In ZRemote Controller, choose **Packages → Choose Package**, select this folder
or its ZIP, confirm the import, then open its **Generic Tools** actions.
Importing does not run any action.

- **Relay On** enables the engine relay, login auto-start and crash recovery.
- **Relay Off** stops only this relay and removes its login auto-start.
- **Check Status** shows the actual health, current Mac address and player count.
- **Show Logs** shows bounded local service logs.

The relay has no one-hour shutdown in service mode. It runs independently of
Codex, Chrome and the ZRemote app. The Mac must be awake and its owner logged
in. No sleep, firewall, VPN, router, cloud, billing or system-wide settings are
changed. Hosting on this Mac is free. Sleep/power loss cannot host a game.

The keeper chooses a private Ethernet/Wi-Fi IPv4 on an `en` interface, waits
when the network is unavailable and restarts its child when the address changes.
Use the address from Check Status and room `LOS-SANTOS`. No wildcard or public
address is bound. This package does not configure Tailscale. A process restart
or changed address ends its old room reservations; reopen the game to rejoin.

Version 1.1 advertises the ready listener through Bonjour on its actual private
Ethernet/Wi-Fi interface. iPhone and browser Find Lobby resolve the advertised
port rather than scanning ports or assuming 47540. The managed service still
uses 47540; independently hosted browser/phone lobbies may use other ports.
The explicitly hosted `LOS-SANTOS` room remains listed with zero players before
the first join and after the last reconnect reservation expires. Other room
names remain usable. Listings still require a compatible live `/health` reply.
Stopping the owned service withdraws its announcement. A transient LAN address
probe failure preserves the live relay and announcement. Tailscale invites are
unchanged; Bonjour is local-network discovery, not a worldwide server directory.

The Mac's built-in `/usr/bin/dns-sd` publishes only on the verified LAN interface.
No new Python dependency, router setting, VPN configuration or public service is
installed. If local multicast is blocked, joining with an address/invite remains
available. Existing ZRemote installations need the updated bundled relay helper;
changing only the iPhone app does not update an old host's announcement behavior.

Runtime scripts and logs are under
`~/Library/Application Support/ZRemote Controller/Games/ZGTAEngineLAN`.
The user agent label is `com.zema.zgtav.engine-lan-relay` and its plist is under
`~/Library/LaunchAgents`. Only that job is controlled. An unrelated process on
port 47540 is never killed. All working game/IPA/save/Intel files stay separate.

The existing ZRemote Build125 binary, its older signaling lobby and Ra1nbox
services are unchanged. These controls manage the actual engine LAN relay on
47540, not the older lobby on 47521. No Project Memory publication is performed.
