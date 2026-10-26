"""Real native URLSession clients against the Python relay; disposable loopback only."""
import asyncio
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import relay


class ReservationTests(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop(); asyncio.set_event_loop(self.loop)
    def tearDown(self):
        self.loop.close(); asyncio.set_event_loop(None)
    def test_exact_address_only_no_takeover_or_stale_epoch(self):
        r = relay.Relay()
        base = dict(type='join', protocol=relay.PROTOCOL, build=relay.BUILD, room='RECOVERY', name='SameCharacter')
        class Writer:
            def close(self): raise AssertionError('Recovery must not evict another player')
        writer = Writer()
        request = dict(base, rejoin={'vip':relay.NET|2, 'epoch':r.epoch})
        a, generation = r.admit(request, writer)
        self.assertEqual(a.vip, relay.NET|2)
        with self.assertRaises(relay.AddressUnavailable): r.admit(request, writer)
        r.depart(a,generation)
        with self.assertRaises(relay.AddressUnavailable): r.admit(request, writer)
        for bad in [True, 1.0, relay.NET|33, relay.NET|0, '172818434']:
            with self.assertRaises(ValueError): r.admit(dict(base,rejoin={'vip':bad,'epoch':r.epoch}),writer)
        with self.assertRaises(ValueError): r.admit(dict(base,rejoin={'vip':relay.NET|1,'epoch':'0'*16}),writer)
        with self.assertRaises(ValueError): r.admit(dict(request,resume='x'*32),writer)
        self.assertEqual(len(r.rooms['RECOVERY']),1)


class SessionRejoin(unittest.IsolatedAsyncioTestCase):
    real_backend = False
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='zgta-native-rejoin-')
        p = Path(cls.tmp.name); cls.binary = p/'fixture'
        args=['/usr/bin/swiftc','-warnings-as-errors','-module-cache-path',str(p/'cache'),str(ROOT/'EngineLanSession.swift'),str(ROOT/'tests/session_rejoin.swift')]
        if cls.real_backend:
            tool=ROOT.parents[2]/'gta-intel-toolchain-20261016'
            env=dict(os.environ,CARGO_HOME=str(tool/'cargo'),RUSTUP_HOME=str(tool/'rustup'),CARGO_NET_OFFLINE='true',RUSTUP_AUTO_INSTALL='0')
            build=subprocess.run([str(tool/'cargo/bin/cargo'),'build','--offline','--locked','--manifest-path',str(ROOT/'Cargo.toml'),'--target-dir',str(p/'rust')],env=env,capture_output=True,text=True,timeout=90)
            if build.returncode:raise AssertionError(build.stderr)
            args+=['-D','REAL_BACKEND','-I',str(ROOT),str(ROOT/'EngineLanBindings.swift'),str(p/'rust/debug/libzema_engine_lan.a')]
        args+=['-o',str(cls.binary)]
        r = subprocess.run(args,capture_output=True,text=True,timeout=90)
        if r.returncode: raise AssertionError(r.stderr)
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    async def check(self, mode):
        relays=[relay.Relay()]; active=[relays[0]]; tasks=set(); joins=[]
        base=dict(type='join',protocol=relay.PROTOCOL,build=relay.BUILD,room='RECOVERY',name='Other')
        class Writer:
            def close(self): pass
        async def client(reader,writer):
            tasks.add(asyncio.current_task())
            chosen=active[0]
            original=chosen.admit
            def admit(message, writer):
                joins.append(message.copy()); return original(message,writer)
            # Each relay has a single real native client, with synthetic peers
            # added directly only to test a conflicting reservation.
            chosen.admit=admit
            try: await chosen.client(reader,writer)
            finally: tasks.discard(asyncio.current_task())
        server=await asyncio.start_server(client,'127.0.0.1',0)
        port=server.sockets[0].getsockname()[1]
        process=await asyncio.create_subprocess_exec(str(self.binary),f'ws://127.0.0.1:{port}/engine-lan',mode,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        async def control():
            while not active[0].rooms: await asyncio.sleep(.01)
            first=active[0]; peer=next(iter(first.rooms['RECOVERY'].values()))
            await asyncio.sleep(.15)
            if mode=='expired':
                peer.resume='z'*32  # invalidate only the old reservation token
                peer.writer.close(); del first.rooms['RECOVERY'][peer.vip]
            else:
                second=relay.Relay(); relays.append(second); active[0]=second
                if mode=='occupied': second.admit(base,Writer())
                if mode=='unsolicited':
                    # Force a server to claim old-token success in a new epoch;
                    # the native client must reject it without negotiation.
                    p,g=second.admit(base,Writer());p.resume=peer.resume;p.writer=None;p.expires=second.clock()+20
                await first.close()
            if mode not in ('occupied','unsolicited'):
                r=active[0]
                while not any(p.writer is not None for p in r.rooms.get('RECOVERY',{}).values()):await asyncio.sleep(.01)
                other,g=r.admit(base,Writer())
                while True:
                    p=next((p for p in r.rooms['RECOVERY'].values() if p.vip==relay.NET|1),None)
                    if p and p.writer:
                        # Route a response through the actual bounded send queue.
                        data=b'G5\x01\x03'+struct.pack('>IHIH',other.vip,258,p.vip,258)+b'c'
                        r.route(other,g,data);return
                    await asyncio.sleep(.01)
        controller=asyncio.create_task(control())
        try:
            out,err=await asyncio.wait_for(process.communicate(),16)
            self.assertEqual(process.returncode,0,(out,err))
            marker=b'OCCUPIED_ADDRESS_PRESERVED' if mode=='occupied' else b'UNNEGOTIATED_EPOCH_REFUSED' if mode=='unsolicited' else b'REJOIN_SAME_ADDRESS_DATA'
            self.assertIn(marker,out)
            self.assertEqual(joins[0]['name'],'SameCharacter')
            if mode not in ('unsolicited',):
                request=next(j for j in joins if 'rejoin' in j)
                self.assertEqual(request['rejoin']['vip'],relay.NET|1)
                self.assertEqual(request['name'],'SameCharacter');self.assertNotIn('resume',request)
        finally:
            controller.cancel();await asyncio.gather(controller,return_exceptions=True)
            if process.returncode is None:process.kill();await process.wait()
            server.close();await server.wait_closed()
            for r in relays:await r.close()
            for task in list(tasks):task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
    async def test_host_restart_rejoins_without_process_restart(self): await self.check('restart')
    async def test_expired_reservation_reclaims_free_original_address(self): await self.check('expired')
    async def test_occupied_address_does_not_change_identity(self): await self.check('occupied')
    async def test_unsolicited_new_epoch_is_refused(self): await self.check('unsolicited')

class SessionRejoinRealBackend(SessionRejoin):
    real_backend = True

if __name__=='__main__':unittest.main()
