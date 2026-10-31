"""Private LAN DNS-SD for portable Python hosts (Windows/Linux/Termux/macOS).

The bundled, unmodified pure-Python zeroconf sources implement the DNS protocol.
Only our service type and locally assigned RFC1918 interfaces are used. Results
are candidates: LobbyDirectory still checks /health before displaying a room.
"""
from pathlib import Path
import ipaddress
import secrets
import sys
import threading
import time

import relay

VENDOR = Path(__file__).with_name('discovery_vendor')
TYPE = '_zgtav._tcp.local.'
MAX_SERVICES = 8


def dependencies():
    # Also works with Windows embeddable Python's deliberately isolated path.
    path = str(VENDOR)
    if path not in sys.path:
        sys.path.insert(0, path)
    from zeroconf import Zeroconf, ServiceBrowser, ServiceInfo, IPVersion
    import ifaddr
    return Zeroconf, ServiceBrowser, ServiceInfo, IPVersion, ifaddr


def private_lan(value):
    try:
        ip = ipaddress.IPv4Address(value)
        return not ip.is_loopback and ip not in relay.TAILSCALE_RANGE and any(ip in net for net in relay.LOCAL_RANGES)
    except (ValueError, TypeError):
        return False


def interfaces(ifaddr):
    return sorted({address.ip for adapter in ifaddr.get_adapters()
                   for address in adapter.ips if address.is_IPv4 and private_lan(address.ip)})[:8]


def discover(timeout=4.0):
    """One bounded browse, not a subnet/port scan or a persistent monitor."""
    zc = browser = None
    lock = threading.Lock()
    names = set()
    try:
        Zeroconf, ServiceBrowser, _, IPVersion, ifaddr = dependencies()
        selected = interfaces(ifaddr)
        if not selected:
            return {'available': False, 'addresses': [], 'message': 'Connect to a local Wi-Fi or Ethernet network to find nearby lobbies.'}
        zc = Zeroconf(interfaces=selected, ip_version=IPVersion.V4Only)

        class Listener:
            def add_service(self, client, kind, name):
                with lock:
                    if len(names) < MAX_SERVICES and kind == TYPE and name.endswith('.' + TYPE):
                        names.add(name)

            update_service = add_service

            def remove_service(self, client, kind, name):
                with lock:
                    names.discard(name)

        browser = ServiceBrowser(zc, TYPE, listener=Listener())
        deadline = time.monotonic() + max(0.1, min(timeout, 6.0))
        found = set()
        # Resolution gets another chance after delayed SRV/A records arrive.
        # All waits share one deadline, even with many announcements.
        while time.monotonic() < deadline:
            with lock:
                batch = sorted(names)
            for name in batch:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                info = zc.get_service_info(TYPE, name, timeout=min(350, max(1, int(remaining * 1000))))
                if info is None or not 1 <= info.port <= 65535:
                    continue
                # An advertisement never makes a host trusted or joinable.
                # Build compatibility and room occupancy come from /health.
                for address in info.parsed_addresses(IPVersion.V4Only):
                    if private_lan(address):
                        found.add('ws://%s:%d/engine-lan' % (address, info.port))
            if len(found) >= MAX_SERVICES:
                break
            threading.Event().wait(min(0.1, max(0, deadline - time.monotonic())))
        return {'available': True, 'addresses': sorted(found)[:MAX_SERVICES], 'backend': 'bonjour'}
    except (OSError, RuntimeError, ImportError) as error:
        return {'available': False, 'addresses': [], 'message': 'LAN discovery could not start. Check local-network/firewall access, or use an invite.', 'diagnostic': type(error).__name__}
    finally:
        if browser is not None:
            browser.cancel()
        if zc is not None:
            zc.close()


class Announcement:
    """Advertise the actual LAN listener without blocking its asyncio loop."""
    def __init__(self):
        self.thread = None
        self.cancel = None
        self.lock = threading.Lock()
        self.state = {'state': 'stopped'}

    def status(self):
        with self.lock:
            return dict(self.state)

    def _state(self, **state):
        with self.lock:
            self.state = state

    def start(self, room, port, address):
        self.stop()
        if not private_lan(address) or type(port) is not int or not 1 <= port <= 65535:
            self._state(state='unavailable', message='No local LAN listener to advertise.')
            return
        self.cancel = threading.Event()
        self._state(state='starting')
        self.thread = threading.Thread(target=self._run, args=(room, port, address, self.cancel), daemon=True, name='zgta-lan-announcement')
        self.thread.start()

    def _run(self, room, port, address, cancel):
        zc = info = None
        try:
            Zeroconf, _, ServiceInfo, IPVersion, _ = dependencies()
            zc = Zeroconf(interfaces=[address], ip_version=IPVersion.V4Only)
            label = ('ZGTA V · ' + room).encode()[:63].decode('utf8', errors='ignore')
            # Unique target, and exactly the bound LAN address: no stale VPN,
            # IPv6, loopback, or unrelated host interface can be advertised.
            info = ServiceInfo(TYPE, label + '.' + TYPE, port=port,
                               parsed_addresses=[address], server='zgta-' + secrets.token_hex(6) + '.local.',
                               properties={'protocol': relay.PROTOCOL, 'build': relay.BUILD})
            zc.register_service(info, allow_name_change=True)
            self._state(state='advertising', backend='bonjour')
            cancel.wait()
        except (OSError, RuntimeError, ImportError) as error:
            self._state(state='error', message='Nearby lobby advertising is unavailable. Share the invite to join.', diagnostic=type(error).__name__)
        finally:
            if zc is not None:
                try:
                    if info is not None:
                        zc.unregister_service(info)
                finally:
                    zc.close()

    def stop(self):
        if self.cancel is not None:
            self.cancel.set()
        if self.thread is not None:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                # Do not start a second advertiser if teardown is still busy.
                raise RuntimeError('The previous LAN advertisement is still closing. Retry shortly.')
        self.thread = self.cancel = None
        self._state(state='stopped')
