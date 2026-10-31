# Private remote multiplayer through Tailscale

This compatibility update prepares the same engine multiplayer protocol for
explicit LAN or Tailscale IPv4 endpoints. It does not prove actual paired
gameplay or an actual VPN connection. No Tailscale installation, account,
access policy, route, firewall, router or system setting is changed.

Use the existing Mac as the host with free personal-use Tailscale. No paid
hosting service is required. The Mac must remain awake, running the relay and
connected to the private VPN. Current pricing permits six users on the free
Personal plan for non-commercial use; review [Tailscale pricing](https://tailscale.com/pricing)
before inviting more players. Do not upgrade or purchase a plan automatically.

## Implemented compatibility

- Native and browser endpoints accept the exact `100.64.0.0/10` IPv4 range
  alongside the existing loopback, RFC1918 and link-local ranges. See
  [Tailscale's address documentation](https://tailscale.com/docs/concepts/tailscale-ip-addresses).
- Use the actual numeric address assigned to the Mac. MagicDNS names, IPv6,
  public IPs, URL credentials, alternate paths, query strings, fragments and
  ambiguous numeric aliases are rejected. Validation does not start a connection.
- The relay requires both `--tailscale` and an explicit address in that range
  for VPN binding. Ordinary LAN operation is unchanged. Wildcard/public binding
  is refused in either mode; `--tailscale` does not accept a Wi-Fi address.
- Room isolation, frame bounds, resume identity, immutable running-game backend
  selection and saved profiles remain unchanged. This adds no second save store
  or new network protocol and enables none of the legacy wallet/voice handlers.
- The browser page remains served on the Mac's existing separate loopback lab
  origin. Browser Origin restrictions are unchanged; remote asset serving is not
  enabled. Keep Chrome on the Mac at `http://127.0.0.1:18887/`.

An address in the shared CGNAT range is not evidence that Tailscale owns that
address or that a connection traversed an encrypted VPN. Before a real trial,
verify the selected address in the installed Tailscale client and ensure only
the intended players can reach the Mac relay through the existing tailnet
policy. Use trusted players: the existing room name is not an authentication
secret. Do not expose the relay through Funnel, public port forwarding or a
wildcard listener. No separate Internet-facing WebSocket endpoint is enabled.

## Paired trial when the human is home

First verify normal same-Wi-Fi gameplay using the existing
[paired procedure](EXPERIMENTAL_GAME.md). Fix connection, character entry,
visibility/movement and saved-character/reconnect failures before adding extras.
Then, with Tailscale already configured and connected on both devices, use the
Mac's actual Tailscale IPv4 in this command instead of the example placeholder:

```sh
python3 -B native-port/engine-lan/relay.py \
  --tailscale --bind YOUR_MAC_TAILSCALE_IPV4 --port 47540 --duration 1800
```

Run only one selected relay for the trial. Serve the newly prepared browser
stage `EngineLAN-FeaturesBrowser-20261017-v12` on the existing loopback origin using
the same `serve_browser.py` command as the LAN procedure. Enter
`ws://YOUR_MAC_TAILSCALE_IPV4:47540/engine-lan` and the same room on both the
Mac browser and the separate compatibility IPA. The relay binds that single
VPN address, so the clients must use it instead of the loopback/Wi-Fi address.
To demonstrate remote VPN play, later repeat with the iPhone on mobile data
and Tailscale connected. Do not claim a same-Wi-Fi trial proves remote play.

Do not change the relay address, room or backend underneath a running game.
Close/restart the lab clients when switching between LAN and VPN trials;
preserve saved characters. A short disconnect can use the existing same-session
reconnect; the 20-second reservation and relay-epoch checks still apply.

## Priority, validation and rollback

Priority: reliable paired gameplay, Tailscale remote play, voice, then shared
wallets/purchases/inventory/roles at the end. Story, Free Roam and all three
control appearances remain required. Browser microphone permission and secure
context requirements remain separate from VPN transport compatibility.

`tests/test_tailscale.py` executes the production native/browser endpoint
validators against shared range-boundary and hostile-URL vectors. It exercises
all 256 second octets of `100.x.1.2`. Relay CLI tests use a mocked server and
prove rejected modes/addresses cannot start serving. Existing native/browser
transport and resume fixtures use only disposable loopback sockets. These tests
are not a real Tailscale or GTA gameplay result.

The compatibility package is a new build 26 output named
`Package-Tailscale-20261016`; all previous IPAs and browser stages are preserved.
For the current trial, use the separate build 27 connection-audit correction
in `Package-ConnectionAudit-20261017` with the v5 browser stage above; see
[the audit](BUILD26_AUDIT.md). Build 26 remains unchanged as historical evidence.
It reuses the staged Intel Metal/UI caches without shader compilation. Nothing
is installed on the phone. Rollback is to stop only the experimental servers,
close the lab browser and continue using the preserved IPA/browser stage.
No VPN/system setting needs restoring because this preparation changes none.
