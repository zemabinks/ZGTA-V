# Managed ZGTA V relay — 18 October 2026

The earlier temporary-relay offline issue had a deterministic cause: temporary relay sessions
were limited to one hour. Explicit `--service` mode now waits until signaled;
the existing default and bounded test-duration options remain unchanged.

The owner-requested per-user LaunchAgent is enabled at
`com.zema.zgtav.engine-lan-relay`. It owns only the private relay support folder
and its child, recovers from crashes and starts at login. It detects a private
Ethernet/Wi-Fi address, waits while offline and rebinds when that address changes.
It never binds a wildcard/public address, opens router ports, configures a VPN,
or changes sleep settings. The Mac must be awake and the owner logged in.

The current native Controller integration is Build127 (0.2.120). The existing
Games > GTA V Multiplayer Server card controls the actual Engine LAN service;
no generic-package import is needed. Build126 replaced the old signaling card
and disabled the verified empty lobby on port 47521. Its native source patch is retained
under controller-integration. The earlier generic-actions package remains a
historical rollback artifact, rather than the normal UI.

Relay Off removes login auto-start before booting out only its own job and
waits for shutdown, so a rapid On cannot falsely report a still-stopping relay
enabled. Background native status polls are separate from requested actions;
they do not flash the On button's busy state or discard an action made while a
poll is in flight. The healthy enabled state shows “Server Is On.”

A subsequent real trial found another defect: one failed private-address probe
was enough to restart a healthy relay, losing its epoch and lobby connections.
The counter accurately showed zero because the game had lost its connection.
The keeper now preserves its child on missing observations; a positive different
address needs two consecutive observations before rebinding. A dead child still
recovers, and explicit Off still stops it. The private 0600 bind-address record
reflects the child's actual bind; status validates that address and still requires
live matching relay health. Cached address data alone never means ONLINE.

A relay restart or expired reservation cannot change a running engine's address
or epoch. Browser Reconnect first attempts the same session. If that fails, the
same click waits for a durable character-save status and reloads the game into a
fresh session automatically. Save failure or absence of a character file blocks
that recovery instead of discarding unsaved character setup. No manual refresh
is part of subsequent reconnects, but an already-open old tab must load the new
entry code once. A restored session may involve a game-loading screen.

Initial validation: 9 service lifecycle/address/HTTP checks, 12 native/browser transport
checks and 5 VPN/address regressions passed. A real local on/off test verified
the off state and subsequent enable. With no peers connected, both a killed
relay child and a killed keeper were automatically replaced; the resulting
endpoint passed a WebSocket 101 upgrade. This does not establish an overnight,
sleep/wake or physical DHCP-change trial. A bounded JSON health endpoint exposes
only service identity and aggregate counts; it rejects unrelated web origins.

No IPA, Intel input, save data, Ra1nbox service, Cloud deployment, global trust
setting or live Project Memory record was changed. The browser character-save file commit and user-reported
rejoin pass are recorded in BROWSER_CHARACTER_SAVE_WORKER.md. Extended stability
and real user confirmation of the latest one-click recovery remain pending.

Build127 validation: all 15 targeted service checks pass, including a real local
WebSocket and HTTP player count surviving repeated missing address probes. Native
poll/action interleaving, helper status/log/error fixtures and browser recovery
fixtures pass. Actual user Off/On/reconnect acceptance remains pending. These
checks do not establish overnight, physical DHCP-change or sleep/wake acceptance.

User trial — 19 October 2026: the user confirmed “Reconnect automatically rejoins
with my saved character” after the requested relay Off/On and single Reconnect
procedure. The one-click browser recovery and saved-character restoration trial
is passed. This answer does not independently close the idle native-button
visual check, extended-session, sleep/wake or physical network-change gaps.
