"""Actual Swift/C <-> WebSocket relay <-> JavaScript/CODEC compatibility."""
import asyncio
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import relay

class WireVoice(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='voice108-socket-');p=Path(cls.temp.name);cls.binary=p/'voice'
        library=Path(os.environ['ZEMA_TEST_LAN_LIBRARY'])
        subprocess.run(['/usr/bin/clang','-std=c11','-O2','-c',str(ROOT/'ZemaVoice.c'),'-o',str(p/'voice.o')],check=True,capture_output=True)
        r=subprocess.run(['/usr/bin/swiftc','-warnings-as-errors','-I',str(ROOT),'-module-cache-path',str(p/'cache'),str(ROOT/'EngineLanSession.swift'),str(ROOT/'EngineLanBindings.swift'),str(ROOT/'tests/voice_transport.swift'),str(p/'voice.o'),str(library),'-o',str(cls.binary)],capture_output=True,text=True)
        if r.returncode:raise AssertionError(r.stderr)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    async def test_native_browser_audio_on_unchanged_room_scoped_relay(self):
        r=relay.Relay();server=await asyncio.start_server(r.client,'127.0.0.1',0);endpoint=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}/engine-lan';processes=[]
        try:
            for args in [[str(self.binary),endpoint],['node',str(ROOT/'tests/voice_socket_peer.cjs'),endpoint]]:
                processes.append(await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE))
            results=await asyncio.wait_for(asyncio.gather(*(p.communicate() for p in processes)),15)
            for p,(out,err) in zip(processes,results):self.assertEqual(p.returncode,0,(out.decode(),err.decode()))
            self.assertIn(b'NATIVE_VOICE_WEBSOCKET_PASS',results[0][0]);self.assertIn(b'BROWSER_VOICE_WEBSOCKET_PASS',results[1][0]);print(results[0][0].decode()+results[1][0].decode())
        finally:
            for p in processes:
                if p.returncode is None:p.kill();await p.wait()
            server.close();await server.wait_closed();await r.close()

if __name__=='__main__':unittest.main()
