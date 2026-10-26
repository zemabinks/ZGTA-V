"""Audit regressions with private files and optional ephemeral loopback servers."""
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT.parent/'app'
sys.path.insert(0,str(ROOT))
import relay
LIB=Path(os.environ.get('ZEMA_TEST_LAN_LIBRARY',str(APP/'Build/EngineLAN/RustHost/debug/libzema_engine_lan.a')))

def run(args,**kwargs):
    p=subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=90,**kwargs)
    if p.returncode:raise AssertionError(p.stdout[-2000:]+'\n'+p.stderr[-4000:])
    return p.stdout

class Audit(unittest.TestCase):
    def test_xbox_preference_and_action_labels_keep_layout(self):
        with tempfile.TemporaryDirectory(prefix='zema-appearance-audit-') as temp:
            d=Path(temp).resolve();exe=d/'test'
            run(['/usr/bin/swiftc','-warnings-as-errors','-module-cache-path',d/'cache',APP/'App/ControlAppearance.swift',APP/'Tests/control_appearance.swift','-o',exe]);self.assertIn('original-layout preservation',run([exe]))
    def test_appearance_does_not_change_touch_input_actions(self):
        name='native-port/app/App/TouchControlsView.swift'
        old=subprocess.check_output(['git','show','c6fd51cb8e8a96956cb284a07537a12fec449ec0:'+name],cwd=ROOT.parents[1],text=True)
        new=(APP/'App/TouchControlsView.swift').read_text();marker='    override func touchesBegan('
        self.assertIn(marker,old);self.assertEqual(old[old.index(marker):],new[new.index(marker):])
    def test_socket_create_restores_flags_in_current_memory(self):
        with tempfile.TemporaryDirectory(prefix='zema-memory-audit-') as temp:
            d=Path(temp).resolve();exe=d/'test'
            run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-I',ROOT,ROOT/'tests/memory_relocation.c',LIB,'-o',exe]);self.assertIn('SOCKET_MEMORY_RELOCATION_SAFE_PASS',run([exe]))
    def test_save_refuses_failed_directory_sync_and_retries(self):
        with tempfile.TemporaryDirectory(prefix='zema-directory-sync-') as temp:
            d=Path(temp).resolve();exe=d/'test'
            run(['/usr/bin/swiftc','-warnings-as-errors','-I',ROOT,'-module-cache-path',d/'cache',ROOT/'EngineLanProfileFile.swift',ROOT/'tests/profile_sync.swift',LIB,'-o',exe])
            self.assertIn('DIRECTORY_SYNC_FAILURE_REFUSED_AND_SAME_BYTES_RETRY_PASS',run([exe,d/'zema-engine-lan-sync']))

class SessionRecovery(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='zema-session-recovery-');cls.path=Path(cls.temp.name).resolve();cls.binary=cls.path/'test'
        run(['/usr/bin/swiftc','-warnings-as-errors','-I',ROOT,'-I',ROOT/'tests','-module-cache-path',cls.path/'cache',ROOT/'EngineLanSession.swift',ROOT/'EngineLanBindings.swift',ROOT/'tests/session_recovery.swift',LIB,'-o',cls.binary])
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    async def check_session(self,mode):
        joins=[];failures=[];clients=set()
        async def client(reader,writer):
            task=asyncio.current_task();clients.add(task)
            try:
                header=(await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),3)).decode();key=next(x.split(':',1)[1].strip() for x in header.split('\r\n') if x.lower().startswith('sec-websocket-key:'))
                accept=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
                writer.write(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\n\r\n');await writer.drain()
                _,payload=await asyncio.wait_for(relay.frame(reader),3);joins.append(json.loads(payload))
                if mode=='invalid':writer.write(relay.encode_frame(b'{invalid-json',1))
                else:
                    message={'type':'joined','protocol':relay.PROTOCOL,'build':relay.BUILD,'vip':relay.NET|1,'epoch':'0000000000000009','resume':'a'*32}
                    writer.write(relay.encode_frame(json.dumps(message).encode(),1))
                await writer.drain();await asyncio.sleep(0.1)
                if mode=='resume' and len(joins)>=2:await reader.read()
            except Exception as e:failures.append(repr(e))
            finally:writer.close();await writer.wait_closed();clients.discard(task)
        server=await asyncio.start_server(client,'127.0.0.1',0);port=server.sockets[0].getsockname()[1]
        process=await asyncio.create_subprocess_exec(str(self.binary),'ws://127.0.0.1:'+str(port)+'/engine-lan',mode,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:
            out,err=await asyncio.wait_for(process.communicate(),18);self.assertEqual(process.returncode,0,(out,err,failures))
            self.assertIn(b'NATIVE_SAME_SESSION_RESUME_PASS' if mode=='resume' else b'NATIVE_INVALID_MESSAGE_REPORTED_PASS',out)
            if mode=='resume':self.assertEqual(len(joins),2);self.assertNotIn('resume',joins[0]);self.assertEqual(joins[1]['resume'],'a'*32)
        finally:
            if process.returncode is None:process.kill();await process.wait()
            server.close();await server.wait_closed()
            for task in list(clients):task.cancel()
            await asyncio.gather(*clients,return_exceptions=True)
    async def test_native_resume_keeps_reservation(self):await self.check_session('resume')
    async def test_invalid_native_message_reports_failure(self):await self.check_session('invalid')

if __name__=='__main__':unittest.main()
