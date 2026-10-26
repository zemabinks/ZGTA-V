"""Isolated service lifecycle, private-address and real HTTP boundary checks."""
import asyncio
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import plistlib
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'relay-service'))
import relay
import relay_control as control
import service_runner as runner

class RelayServiceCLI(unittest.TestCase):
    def test_only_explicit_service_removes_timer(self):
        with patch.object(relay,'serve',AsyncMock()) as serve:
            relay.main(['--bind','192.168.1.2','--service'])
            serve.assert_awaited_once_with('192.168.1.2',47540,None)
        with patch.object(relay,'serve',AsyncMock()) as serve:
            relay.main([]);serve.assert_awaited_once_with('127.0.0.1',47540,1800)
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            relay.main(['--service','--duration','3600'])

    def test_address_selection_never_binds_public_wildcard_or_vpn(self):
        def run_with(address):
            def run(args,**kw):
                return SimpleNamespace(returncode=0,stdout=' interface: en0\n' if args[0]=='/sbin/route' else address)
            return run
        for address in ['8.8.8.8','0.0.0.0','127.0.0.1','100.77.1.2','::1','192.168.1.2\nextra']:
            self.assertIsNone(runner.lan_ip(run_with(address)))
        self.assertEqual(runner.lan_ip(run_with('192.168.1.33')),'192.168.1.33')

class ServiceControl(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='zgta-relay-control-');base=Path(self.tmp.name).resolve()
        self.root=base/'runtime';self.agent=base/'agents'/('com.zema.zgtav.engine-lan-relay.plist');self.source=base/'source';self.source.mkdir(mode=0o700)
        for name in ('relay.py','service_runner.py'):(self.source/name).write_text('# fixture\n');(self.source/name).chmod(0o600)
        (self.source/'payload-sha256.json').write_text(json.dumps({n:hashlib.sha256((self.source/n).read_bytes()).hexdigest() for n in ('relay.py','service_runner.py')}));(self.source/'payload-sha256.json').chmod(0o600)
        self.stack=contextlib.ExitStack()
        for name,value in [('ROOT',self.root),('AGENT',self.agent),('RUNNER',self.root/'service_runner.py'),('SOURCE',self.source)]:self.stack.enter_context(patch.object(control,name,value))
    def tearDown(self):self.stack.close();self.tmp.cleanup()

    def test_start_installs_exact_payload_and_persistent_job(self):
        def cmd(args,*_):return SimpleNamespace(returncode=1 if args[0]=='/usr/sbin/lsof' else 0,stderr='',stdout='')
        with patch.object(control,'loaded',return_value=False),patch.object(control,'command',side_effect=cmd),patch.object(control,'status',return_value={'running':True}):
            self.assertIn('No one-hour',control.start())
        with self.agent.open('rb') as f:data=plistlib.load(f)
        self.assertTrue(data['RunAtLoad']);self.assertIs(data['KeepAlive'],True)
        self.assertEqual(data['ProgramArguments'],['/usr/bin/python3','-B','-u',str(self.root/'service_runner.py')])
        for path in [self.agent,self.root/'relay.py',self.root/'service_runner.py']:
            self.assertEqual(path.stat().st_mode&0o777,0o600)
        self.assertEqual(self.root.stat().st_mode&0o777,0o700)
        def bootout(args,*_):
            self.assertFalse(self.agent.exists(),'OFF must persist before the running job is stopped')
            self.assertEqual(args,['/bin/launchctl','bootout',control.target()]);return SimpleNamespace(returncode=0,stderr='')
        with patch.object(control,'loaded',side_effect=[True,False]),patch.object(control,'command',side_effect=bootout):self.assertIn('Relay off',control.stop())
        self.assertFalse(self.agent.exists());self.assertTrue((self.root/'relay.py').exists())

    def test_start_during_shutdown_does_not_claim_to_enable(self):
        with patch.object(control,'loaded',return_value=True):
            with self.assertRaisesRegex(RuntimeError,'still stopping'):control.start()
        self.assertFalse(self.agent.exists())

    def test_unknown_listener_and_modified_package_are_refused(self):
        with patch.object(control,'loaded',return_value=False),patch.object(control,'command',return_value=SimpleNamespace(returncode=0)):
            with self.assertRaisesRegex(RuntimeError,'occupied'):control.start()
        self.assertFalse(self.agent.exists())
        (self.source/'relay.py').write_text('changed')
        with patch.object(control,'loaded',return_value=False),patch.object(control,'command',return_value=SimpleNamespace(returncode=1)):
            with self.assertRaisesRegex(RuntimeError,'checksum'):control.start()
        self.assertFalse(self.agent.exists())

    def test_unknown_agent_and_symlinks_are_preserved(self):
        self.agent.parent.mkdir();self.agent.write_bytes(plistlib.dumps({'Label':'someone.else'}));self.agent.chmod(0o600)
        before=self.agent.read_bytes()
        with self.assertRaisesRegex(RuntimeError,'differs'):control.stop()
        self.assertEqual(self.agent.read_bytes(),before)
        self.agent.unlink();other=self.agent.parent/'other';other.write_text('preserved');self.agent.symlink_to(other)
        with self.assertRaisesRegex(RuntimeError,'Symlink'):control.stop()
        self.assertEqual(other.read_text(),'preserved')

    def test_status_does_not_install_or_start(self):
        with patch.object(control,'loaded',return_value=False),patch.object(control,'lan_ip',return_value=None):
            data=control.status()
        self.assertFalse(data['enabled']);self.assertFalse(data['running']);self.assertFalse(self.root.exists())

    def test_status_uses_owned_bind_record_but_requires_live_health(self):
        self.root.mkdir(mode=0o700);runner.publish_address(self.root,'192.168.1.2')
        path=self.root/'relay-bind.json';self.assertEqual(path.stat().st_mode&0o777,0o600)
        health={'service':'zgta-engine-lan','protocol':'zema-engine-lan/1','build':'8b0b5899ed','peers':2,'rooms':1}
        opener=Mock();opener.open.side_effect=lambda *args,**kwargs:io.BytesIO(json.dumps(health).encode())
        with patch.object(control,'loaded',return_value=True),patch.object(control,'lan_ip',side_effect=AssertionError('Live bind record must not depend on a fresh address probe')),patch.object(control.urllib.request,'build_opener',return_value=opener):
            result=control.status()
            self.assertTrue(result['running']);self.assertEqual((result['peers'],result['rooms']),(2,1))
            self.assertEqual(result['address'],'ws://192.168.1.2:47540/engine-lan')
            opener.open.side_effect=OSError('unreachable')
            self.assertFalse(control.status()['running'],'A cached address alone is not online proof')
        path.write_text('{"address":"8.8.8.8"}')
        with self.assertRaisesRegex(RuntimeError,'private relay bind'):control.published_address()
        path.unlink();path.symlink_to(self.source/'relay.py')
        with self.assertRaisesRegex(RuntimeError,'Symlink'):control.published_address()

class LobbyCatalog(unittest.IsolatedAsyncioTestCase):
    async def test_names_only_include_connected_players_and_never_resume_tokens(self):
        engine=relay.Relay(clock=lambda:1)
        def join(name):return engine.admit(dict(type='join',protocol=relay.PROTOCOL,build=relay.BUILD,room='ROOM',name=name),object())
        p,g=join('Mac');q,h=join('iPhone');engine.depart(q,h)
        row=engine.health()['lobbies'][0]
        self.assertEqual(row['player_names'],['Mac']);self.assertEqual((row['players'],row['slots']),(1,2))
        self.assertNotIn(p.resume,json.dumps(engine.health()));self.assertNotIn(q.resume,json.dumps(engine.health()))
        self.assertEqual(control.checked_catalog(engine.health())[0]['player_names'],['Mac'])

    async def test_maximum_rooms_keep_health_within_existing_client_limit(self):
        engine=relay.Relay(clock=lambda:1)
        for number in range(32):
            for peer in range(32):engine.admit(dict(type='join',protocol=relay.PROTOCOL,build=relay.BUILD,room=str(number)+'é'*30,name='\\'*48),object())
        health=engine.health();self.assertEqual(health['peers'],1024)
        self.assertLess(len(json.dumps(health).encode()),16384)
        self.assertIsNotNone(control.checked_catalog(health))

    def test_invalid_catalog_cannot_become_a_roster(self):
        base={'catalog_version':1,'lobbies':[{'room':'ROOM','players':1,'slots':2,'capacity':8,'player_names':['Mac']}]}
        self.assertEqual(control.checked_catalog(base)[0]['slots'],2)
        for names in [[],['Mac','Other'],['Bad\nName'],[True]]:
            base['lobbies'][0]['player_names']=names;self.assertIsNone(control.checked_catalog(base))
        self.assertIsNone(control.checked_catalog({'peers':2,'rooms':1}))

    def test_browser_host_is_independent_and_read_only(self):
        info={'running':True,'owned':True,'join':'ws://127.0.0.1:47541/engine-lan','remote':'ws://100.75.192.42:47541/engine-lan'}
        opener=Mock();opener.open.return_value=io.BytesIO(json.dumps(info).encode())
        with patch.object(control.urllib.request,'build_opener',return_value=opener),patch.object(control,'health_at',return_value={'peers':2,'rooms':1}) as health:
            result=control.browser_host_status();self.assertEqual(result['peers'],2);self.assertEqual(result['address'],info['remote']);health.assert_called_once_with('127.0.0.1',47541)
        info['join']='ws://8.8.8.8:47541/engine-lan';opener.open.return_value=io.BytesIO(json.dumps(info).encode())
        with patch.object(control.urllib.request,'build_opener',return_value=opener),patch.object(control,'health_at') as health:
            self.assertIsNone(control.browser_host_status());health.assert_not_called()

class RelayAddressContinuity(unittest.TestCase):
    def supervisor(self):
        self.spawn=Mock(side_effect=lambda address:SimpleNamespace(poll=Mock(return_value=None),address=address))
        self.stop=Mock()
        return runner.RelaySupervisor(Path('/unused'),Mock(),spawn=self.spawn,stop=self.stop)

    def test_missing_probes_preserve_live_child_and_sessions(self):
        s=self.supervisor();s.update('192.168.1.2');original=s.child
        for address in [None,None,'192.168.1.2',None,None,None,'192.168.1.2']:s.update(address)
        self.assertIs(s.child,original);self.spawn.assert_called_once();self.stop.assert_not_called()

    def test_only_consecutive_positive_address_change_rebinds(self):
        s=self.supervisor();s.update('192.168.1.2');original=s.child
        for address in ['192.168.1.3',None,'192.168.1.3','192.168.1.2','192.168.1.3']:s.update(address)
        self.assertIs(s.child,original);self.stop.assert_not_called()
        s.update('192.168.1.3')
        self.assertIsNot(s.child,original);self.assertEqual(s.address,'192.168.1.3');self.stop.assert_called_once_with(original)
        self.assertEqual(self.spawn.call_count,2)

    def test_dead_child_recovers_without_guessing_an_address(self):
        s=self.supervisor();s.update('192.168.1.2');s.child.poll.return_value=9
        s.update(None);self.assertIsNone(s.child);self.assertEqual(self.spawn.call_count,1)
        s.update('192.168.1.2');self.assertIsNotNone(s.child);self.assertEqual(self.spawn.call_count,2)

    def test_explicit_off_still_stops_only_owned_child(self):
        s=self.supervisor();s.update('192.168.1.2');original=s.child
        s.update(None);s.close();self.stop.assert_called_once_with(original);self.assertIsNone(s.child)

class HealthBoundary(unittest.IsolatedAsyncioTestCase):
    async def test_websocket_and_count_survive_missing_address_probes(self):
        import struct
        r=relay.Relay();server=await asyncio.start_server(r.client,'127.0.0.1',0)
        reader,writer=await asyncio.open_connection('127.0.0.1',server.sockets[0].getsockname()[1])
        def send(data):
            mask=b'1234';length=len(data)
            header=bytes([0x81,0x80|length]) if length<126 else b'\x81\xfe'+struct.pack('>H',length)
            writer.write(header+mask+bytes(b^mask[i%4] for i,b in enumerate(data)))
        async def receive():
            first,length=await asyncio.wait_for(reader.readexactly(2),2)
            if length==126:length=struct.unpack('>H',await reader.readexactly(2))[0]
            return json.loads(await reader.readexactly(length))
        child=SimpleNamespace(poll=lambda:None)
        stop=Mock(side_effect=lambda _:writer.close())
        s=runner.RelaySupervisor(Path('/unused'),Mock(),spawn=Mock(return_value=child),stop=stop)
        try:
            writer.write(b'GET /engine-lan HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: MDEyMzQ1Njc4OWFiY2RlZg==\r\n\r\n')
            await writer.drain();self.assertIn(b'101',await reader.readuntil(b'\r\n\r\n'))
            send(json.dumps({'type':'join','protocol':relay.PROTOCOL,'build':relay.BUILD,'room':'TEST','name':'Fixture'}).encode());await writer.drain()
            joined=await receive();epoch=r.epoch
            s.update('192.168.1.2')
            for address in [None,None,None,'192.168.1.2',None]:s.update(address)
            stop.assert_not_called();self.assertIs(s.child,child)
            send(b'{"type":"ping"}');await writer.drain();self.assertEqual(await receive(),{'type':'pong'})
            self.assertEqual(r.epoch,epoch);self.assertEqual(joined['epoch'],epoch)
            self.assertEqual(sum(p.writer is not None for room in r.rooms.values() for p in room.values()),1)
            health_reader,health_writer=await asyncio.open_connection('127.0.0.1',server.sockets[0].getsockname()[1])
            health_writer.write(b'GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n');await health_writer.drain()
            health=json.loads((await health_reader.read()).split(b'\r\n\r\n',1)[1])
            self.assertEqual((health['peers'],health['rooms']),(1,1))
            health_writer.close();await health_writer.wait_closed()
        finally:
            s.close();writer.close();await writer.wait_closed();server.close();await server.wait_closed();await r.close()

    async def test_health_identity_and_wrong_origin(self):
        r=relay.Relay();server=await asyncio.start_server(r.client,'127.0.0.1',0)
        port=server.sockets[0].getsockname()[1]
        try:
            reader,writer=await asyncio.open_connection('127.0.0.1',port)
            writer.write(b'GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n');await writer.drain();data=await reader.read();writer.close();await writer.wait_closed()
            headers,body=data.split(b'\r\n\r\n',1);self.assertIn(b'200 OK',headers);self.assertIn(b'no-store',headers)
            self.assertEqual(json.loads(body),{'service':'zgta-engine-lan','protocol':relay.PROTOCOL,'build':relay.BUILD,'instance':r.health_id,'peers':0,'rooms':0,'catalog_version':1,'lobbies':[],'room_policy':'open'})
            reader,writer=await asyncio.open_connection('127.0.0.1',port)
            writer.write(b'GET /health HTTP/1.1\r\nOrigin: https://example.com\r\n\r\n');await writer.drain();self.assertEqual(await reader.read(),b'');writer.close();await writer.wait_closed()
            self.assertEqual(r.rooms,{})
        finally:server.close();await server.wait_closed();await r.close()

    async def test_service_wait_has_no_timeout_and_closes_on_stop(self):
        actual=asyncio.get_running_loop();closed=[]
        fake=SimpleNamespace(sockets=[SimpleNamespace(getsockname=lambda:('127.0.0.1',12345))],close=lambda:closed.append(True),wait_closed=AsyncMock())
        loop=SimpleNamespace(add_signal_handler=lambda _sig,fn:actual.call_soon(fn))
        with patch.object(relay.asyncio,'start_server',AsyncMock(return_value=fake)),patch.object(relay.asyncio,'get_running_loop',return_value=loop),patch.object(relay.asyncio,'wait_for',side_effect=AssertionError('Service used a timeout')):
            await relay.serve('127.0.0.1',12345,None)
        self.assertEqual(closed,[True]);fake.wait_closed.assert_awaited_once()

if __name__=='__main__':unittest.main()
