"""Browser cancellation/liveness and real native silent-peer regression tests.

The browser runs a deterministic clock with fake sockets. Native traffic uses
only a disposable ephemeral loopback fixture; no game, VPN, device or live save.
"""
import asyncio
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import relay


class BrowserLifecycle(unittest.TestCase):
    def check(self, mode, marker):
        result = subprocess.run(['node', str(ROOT / 'tests/connection_lifecycle.cjs'), mode],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(marker, result.stdout)

    def test_cancelled_admission_settles_and_ignores_old_socket(self):
        self.check('cancel', 'BROWSER_CANCELLED_JOIN_SETTLED_AND_STALE_CLOSE_IGNORED_PASS')

    def test_silent_relay_disconnects_and_resumes_same_identity(self):
        self.check('silent', 'BROWSER_SILENT_RELAY_DETECTED_AND_SAME_IDENTITY_RESUME_PASS')

    def test_responsive_relay_stays_connected(self):
        self.check('healthy', 'BROWSER_RESPONSIVE_RELAY_KEEPS_SESSION_PASS')

    def test_failed_resume_explains_expiry_without_new_identity(self):
        self.check('resume-failure', 'BROWSER_FAILED_RESUME_REASON_PRESERVED_WITHOUT_NEW_IDENTITY_PASS')

    def test_valid_traffic_keeps_session_alive_and_malformed_frame_is_refused(self):
        self.check('traffic', 'BROWSER_VALID_TRAFFIC_LIVENESS_AND_MALFORMED_FRAME_REFUSED_PASS')

    def test_join_send_exception_is_immediately_reported(self):
        self.check('join-send-failure', 'BROWSER_JOIN_SEND_THROW_SETTLES_IMMEDIATELY_PASS')

    def test_initial_failure_does_not_claim_resume(self):
        self.check('initial-error', 'BROWSER_INITIAL_FAILURE_DOES_NOT_CLAIM_RESUME_PASS')

    def test_active_connection_error_is_not_labeled_failed_resume(self):
        self.check('active-error', 'BROWSER_ACTIVE_CONNECTION_ERROR_IS_NOT_FAILED_RESUME_PASS')

    def test_resume_timeout_preserves_identity_and_explains_recovery(self):
        self.check('resume-timeout', 'BROWSER_RESUME_TIMEOUT_RETAINS_IDENTITY_AND_RECOVERY_REASON_PASS')


class NativeLiveness(unittest.IsolatedAsyncioTestCase):
    async def test_silent_native_peer_is_reported_without_game_or_device(self):
        with tempfile.TemporaryDirectory(prefix='zema-native-liveness-') as temporary:
            directory = Path(temporary).resolve()
            binary = directory / 'fixture'
            result = subprocess.run(['/usr/bin/swiftc', '-warnings-as-errors', '-module-cache-path',
                str(directory / 'cache'), str(ROOT / 'EngineLanSession.swift'),
                str(ROOT / 'tests/session_liveness.swift'), '-o', str(binary)],
                capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            tasks = set()
            joins = []

            async def client(reader, writer):
                task = asyncio.current_task(); tasks.add(task)
                try:
                    header = (await reader.readuntil(b'\r\n\r\n')).decode()
                    key = next(line.split(':', 1)[1].strip() for line in header.split('\r\n')
                               if line.lower().startswith('sec-websocket-key:'))
                    accept = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
                    writer.write(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ' + accept + b'\r\n\r\n')
                    await writer.drain()
                    _, payload = await relay.frame(reader); joins.append(json.loads(payload))
                    joined = {'type': 'joined', 'protocol': relay.PROTOCOL, 'build': relay.BUILD,
                              'vip': relay.NET | 1, 'epoch': '0000000000000009', 'resume': 'a' * 32}
                    writer.write(relay.encode_frame(json.dumps(joined).encode(), 1)); await writer.drain()
                    # Deliberately accept all outbound traffic without answering.
                    await reader.read()
                finally:
                    writer.close(); await writer.wait_closed(); tasks.discard(task)

            server = await asyncio.start_server(client, '127.0.0.1', 0)
            port = server.sockets[0].getsockname()[1]
            process = await asyncio.create_subprocess_exec(str(binary), 'ws://127.0.0.1:%d/engine-lan' % port,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            try:
                output, error = await asyncio.wait_for(process.communicate(), 40)
                self.assertEqual(process.returncode, 0, (output, error))
                self.assertIn(b'NATIVE_SILENT_RELAY_DISCONNECTED_PASS', output)
                self.assertEqual(len(joins), 1)
            finally:
                if process.returncode is None:
                    process.kill(); await process.wait()
                server.close(); await server.wait_closed()
                for task in list(tasks): task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == '__main__':
    unittest.main()
