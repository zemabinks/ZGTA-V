"""Offline VPN compatibility checks: no Tailscale, sockets, game or device access.

The real native and browser URL validators share the same hostile/boundary
vectors. Relay CLI tests replace serving with an async mock before invocation.
"""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import relay


def vectors():
    allowed = ['127.0.0.1', '10.0.0.1', '172.16.0.1', '172.31.255.254',
               '192.168.1.2', '169.254.1.2', '100.64.0.0', '100.127.255.255']
    denied = ['0.0.0.0', '8.8.8.8', '100.63.255.255', '100.128.0.0',
              '172.15.255.255', '172.32.0.0', '192.169.0.1', '169.255.1.2',
              '224.0.0.1', '240.0.0.1', '255.255.255.255', 'localhost',
              'mac.example.ts.net', '[::1]', '[fd7a:115c:a1e0::1]',
              '100.64.0', '100.64.0.256', '100.064.0.1', '0100.64.0.1',
              '0x64400001', '1681915905', '%31%30%30.64.0.1', '100.64.0.1.']
    rows = [{'url': 'ws://' + host + ':47540/engine-lan', 'valid': True} for host in allowed]
    rows += [{'url': 'ws://' + host + ':47540/engine-lan', 'valid': False} for host in denied]
    rows += [{'url': 'ws://100.%d.1.2:47540/engine-lan' % second,
              'valid': 64 <= second <= 127} for second in range(256)]
    rows += [{'url': value, 'valid': True} for value in
             ['ws://100.64.0.1/engine-lan', 'ws://100.64.0.1:80/engine-lan',
              'ws://100.64.0.1:1/engine-lan', 'ws://100.64.0.1:65535/engine-lan']]
    rows += [{'url': value, 'valid': False} for value in [
        'wss://100.64.0.1:47540/engine-lan', 'http://100.64.0.1:47540/engine-lan',
        'WS://100.64.0.1:47540/engine-lan', 'ws://100.64.0.1:0/engine-lan',
        'ws://100.64.0.1:65536/engine-lan', 'ws://100.64.0.1:047540/engine-lan',
        'ws://100.64.0.1:/engine-lan', 'ws://100.64.0.1:80junk/engine-lan',
        'ws://100.64.0.1:47540/ws', 'ws://100.64.0.1:47540/engine-lan/',
        'ws://100.64.0.1:47540/other/../engine-lan',
        'ws://100.64.0.1:47540/%65ngine-lan',
        'ws://user@100.64.0.1:47540/engine-lan',
        'ws://100.64.0.1@8.8.8.8:47540/engine-lan',
        'ws://100.64.0.1:47540/engine-lan?', 'ws://100.64.0.1:47540/engine-lan?x=1',
        'ws://100.64.0.1:47540/engine-lan#', 'ws://100.64.0.1:47540/engine-lan#x',
        ' ws://100.64.0.1:47540/engine-lan', 'ws://100.64.0.1:47540/engine-lan ',
        'ws://100.64.0.1:47540/engine-lan\n', 'ws://100.64.0.1:47540/engine-lan\x00',
        'ws://100.64.0.1:47540/engine-\tlan', 'ws:\\100.64.0.1:47540/engine-lan']]
    return rows


def run(args):
    result = subprocess.run([str(value) for value in args], capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise AssertionError(result.stdout + '\n' + result.stderr)
    return result.stdout


class TailscaleCompatibility(unittest.TestCase):
    def test_real_native_and_browser_validators_agree_without_connecting(self):
        with tempfile.TemporaryDirectory(prefix='zema-tailscale-endpoints-') as temporary:
            directory = Path(temporary).resolve()
            fixture = directory / 'vectors.json'
            fixture.write_text(json.dumps(vectors()))
            binary = directory / 'native-endpoints'
            run(['/usr/bin/swiftc', '-warnings-as-errors', '-module-cache-path', directory / 'cache',
                 ROOT / 'EngineLanSession.swift', ROOT / 'tests/endpoints.swift', '-o', binary])
            self.assertIn('NATIVE_LAN_TAILSCALE_ENDPOINT_BOUNDARIES_PASS', run([binary, fixture]))
            self.assertIn('BROWSER_LAN_TAILSCALE_ENDPOINT_BOUNDARIES_NO_CONNECT_PASS',
                          run(['node', ROOT / 'tests/endpoints.cjs', fixture]))

    def test_relay_requires_explicit_vpn_mode_and_exact_shared_range(self):
        for second in range(256):
            address = '100.%d.1.2' % second
            with self.subTest(address=address):
                with self.assertRaises(ValueError):
                    relay.bind_address(address)
                if 64 <= second <= 127:
                    self.assertEqual(relay.bind_address(address, tailscale=True), address)
                else:
                    with self.assertRaises(ValueError):
                        relay.bind_address(address, tailscale=True)

    def test_local_ranges_remain_supported_and_public_wildcard_aliases_refused(self):
        for address in ['127.0.0.1', '10.0.0.1', '172.16.0.1', '172.31.255.254',
                        '192.168.1.2', '169.254.1.2']:
            self.assertEqual(relay.bind_address(address), address)
            with self.assertRaises(ValueError):
                relay.bind_address(address, tailscale=True)
        for address in ['0.0.0.0', '8.8.8.8', '172.15.1.1', '172.32.1.1',
                        '224.0.0.1', '240.0.0.1', '255.255.255.255', 'localhost',
                        '::', '::1', '100.064.0.1', '0x64400001', '100.64.0.1\n']:
            for mode in (False, True):
                with self.subTest(address=address, mode=mode), self.assertRaises(ValueError):
                    relay.bind_address(address, tailscale=mode)

    def test_cli_passes_only_explicit_vpn_address_without_real_serving(self):
        serve = AsyncMock()
        with patch.object(relay, 'serve', serve):
            relay.main(['--tailscale', '--bind', '100.77.1.2', '--port', '47540', '--duration', '1800'])
        serve.assert_awaited_once_with('100.77.1.2', 47540, 1800)
        serve.reset_mock()
        with patch.object(relay, 'serve', serve):
            relay.main([])
        serve.assert_awaited_once_with('127.0.0.1', 47540, 1800)

    def test_cli_refuses_invalid_mode_or_limits_before_serving(self):
        for args in [
            ['--bind', '100.77.1.2'], ['--tailscale'],
            ['--tailscale', '--bind', '0.0.0.0'], ['--tailscale', '--bind', '8.8.8.8'],
            ['--bind', '240.0.0.1'], ['--port', '1023'], ['--port', '65536'],
            ['--duration', '59'], ['--duration', '3601'],
        ]:
            serve = AsyncMock()
            with self.subTest(args=args), patch.object(relay, 'serve', serve), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    relay.main(args)
                self.assertEqual(error.exception.code, 2)
                serve.assert_not_called()


if __name__ == '__main__':
    unittest.main()
