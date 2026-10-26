"""Fixtures exercise real native/Swift/WebSocket/browser WASM boundaries.

No game, device, existing app, service, save, shader or original build is run.
Network tests bind only disposable ephemeral 127.0.0.1 sockets and close them.
"""
import asyncio
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from public_test_inputs import game_file
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fixture import ROOT, engine, patcher
sys.path.insert(0, str(ROOT))
import relay


def write_fixture(path, table64=True):
    data, contract = engine(table64)
    patched, metadata = patcher.transform(data, contract)
    path.write_text(json.dumps({'wasm': base64.b64encode(patched).decode(), 'metadata': metadata}))
    return patched, metadata


class Writer:
    def __init__(self): self.closed = False
    def close(self): self.closed = True


def join(room='room', name='test', **extra):
    return {'type':'join','protocol':relay.PROTOCOL,'build':relay.BUILD,'room':room,'name':name,**extra}


def packet(source, destination, data=b'fixture', port=6672):
    return b'G5\x01\x03'+struct.pack('>IHIH', source, port, destination, port)+data


class RelayStateTests(unittest.TestCase):
    def setUp(self):
        # Python 3.9 queues bind a default loop even in pure-state fixtures.
        self.loop=asyncio.new_event_loop();asyncio.set_event_loop(self.loop)
    def tearDown(self):
        self.loop.close();asyncio.set_event_loop(None)
    def test_room_and_unicast_isolation_no_sender_echo(self):
        r=relay.Relay();a,ag=r.admit(join(),Writer());b,bg=r.admit(join(),Writer());c,cg=r.admit(join('other'),Writer())
        data=packet(a.vip,b.vip);r.route(a,ag,data)
        self.assertEqual(b.queue.get_nowait(),(data,2));self.assertTrue(a.queue.empty());self.assertTrue(c.queue.empty())
        r.route(a,ag,packet(a.vip,0xffffffff));self.assertFalse(b.queue.empty());self.assertTrue(c.queue.empty())

    def test_spoofed_sender_build_bad_data_and_repeated_generation_refused(self):
        r=relay.Relay();a,ag=r.admit(join(),Writer())
        with self.assertRaises(ValueError):r.route(a,ag,packet(relay.NET|2,a.vip))
        for bad in [b'',b'G5\x02\x03'+bytes(12),packet(a.vip,0),packet(a.vip,a.vip,bytes(2048))]:
            with self.assertRaises(ValueError):r.route(a,ag,bad)
        with self.assertRaises(ValueError):r.admit(join(build='different'),Writer())
        old=a.writer;b,bg=r.admit(join(resume=a.resume),Writer());self.assertTrue(old.closed)
        with self.assertRaises(ValueError):r.route(a,ag,packet(a.vip,a.vip))
        r.depart(a,ag);self.assertIsNotNone(b.writer) # Stale close cannot remove resumed connection.

    def test_resume_and_expiry_keep_address_or_require_restart(self):
        now=[0.0];r=relay.Relay(clock=lambda:now[0]);a,g=r.admit(join(),Writer());vip=a.vip;token=a.resume
        r.depart(a,g);now[0]=10;a,g=r.admit(join(resume=token),Writer());self.assertEqual(a.vip,vip)
        r.depart(a,g);now[0]=31
        with self.assertRaises(ValueError):r.admit(join(resume=token),Writer())

    def test_limits_close_slow_consumer_and_reject_room_growth(self):
        r=relay.Relay();a,ag=r.admit(join(),Writer());b,bg=r.admit(join(),Writer())
        for _ in range(129):r.route(a,ag,packet(a.vip,b.vip))
        self.assertTrue(b.writer.closed);self.assertEqual(b.queue.qsize(),128)
        for i in range(1,32):r.admit(join(room=str(i)),Writer())
        with self.assertRaises(ValueError):r.admit(join('excess'),Writer())
        r.closing=True
        with self.assertRaises(ValueError):r.admit(join('room'),Writer())
        with self.assertRaises(ValueError):r.route(a,ag,packet(a.vip,b.vip))

    def test_join_and_frame_validation(self):
        r=relay.Relay()
        for message in [None,[],join(room=''),join(name='\n'),join(extra=True),join(room='x'*65),join(resume='é'*32),join(resume='')]:
            with self.assertRaises(ValueError):r.admit(message,Writer())
        for n in [0,16,125,126,2048]:
            b=relay.encode_frame(bytes(n),2);self.assertEqual(b[0],0x82)
        with self.assertRaises(ValueError):relay.encode_frame(bytes(2049),2)


class BrowserPatchTests(unittest.TestCase):
    def test_loader_wiring_keeps_strict_mode_and_both_save_directions_isolated(self):
        import stage_browser
        loader="""'use strict';
\tconst m = ev.data;
fetch(B + '/game.wasm');
WebAssembly.instantiate(bytes, imports);
WebAssembly.instantiateStreaming(res, imports);
indexedDB.open('gta5-userdata', 1);
""".encode()
        io=(game_file('b/8b0b5899ed')/'io_worker.js').read_bytes()
        self.assertEqual(hashlib.sha256(io).hexdigest(),stage_browser.PINS['io_worker.js'])
        with patch.dict(stage_browser.PINS,{'loader.js':hashlib.sha256(loader).hexdigest()}):
            changed=stage_browser.patch('loader.js',loader).decode()
            self.assertTrue(changed.startswith("'use strict';"));self.assertIn('requireGameReady',changed)
            self.assertIn('self.__zemaEngineLanContext=m.engineLan',changed)
            self.assertIn('zema-engine-lan-userdata-v1',changed);self.assertNotIn("'gta5-userdata'",changed)
            self.assertNotIn("'gta5-userdata'",stage_browser.patch('io_worker.js',io).decode())
        with self.assertRaises(ValueError):stage_browser.patch('game.js',b'changed')
    def test_shared_worker_select_queue_bounds_and_client_generation(self):
        result=subprocess.run(['node',str(ROOT/'tests/browser_state.cjs')],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('BROWSER_SHARED_STATE_PASS',result.stdout)
    def test_type_indices_other_sections_and_deferred_start(self):
        data, contract=engine(True);before=data[:];patched,metadata=patcher.transform(data,contract)
        old={k:b for k,b in patcher.gate.sections(data)};new={k:b for k,b in patcher.gate.sections(patched)}
        self.assertEqual(data,before);self.assertNotIn(8,new)
        for kind in set(old)-{3,4,7,8,10}:self.assertEqual(old[kind],new[kind])
        self.assertEqual(patcher.gate.module_abi(data)[1],patcher.gate.module_abi(patched)[1][:9])
        self.assertTrue(metadata['table64']);self.assertFalse(metadata['online_startup_ready']);self.assertEqual(len(metadata['hooks']),8)
        with self.assertRaises(ValueError):patcher.transform(data+b'changed',contract)

    def test_actual_typed_wasm_browser_hooks_32_and_64_bit_tables(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'fixture.json'
            for table64 in [False,True]:
                write_fixture(path,table64)
                result=subprocess.run(['node',str(ROOT/'tests/browser_fixture.cjs'),str(path)],capture_output=True,text=True,timeout=20)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn('BROWSER_TYPED_WASM_FIXTURE_PASS',result.stdout)


class SocketTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='zema-engine-lan-fixture-')
        cls.directory=Path(cls.temp.name).resolve();cls.binary=cls.directory/'native-fixture';cls.fixture=cls.directory/'fixture.json'
        write_fixture(cls.fixture)
        library=Path(os.environ.get('ZEMA_TEST_LAN_LIBRARY',str(ROOT.parent/'app/Build/EngineLAN/RustHost/debug/libzema_engine_lan.a')))
        result=subprocess.run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-c',str(ROOT/'tests/native_fixture.c'),'-o',str(cls.directory/'fixture.o')],capture_output=True,text=True,timeout=30)
        if result.returncode:raise RuntimeError(result.stderr)
        result=subprocess.run(['/usr/bin/swiftc','-warnings-as-errors','-I',str(ROOT),'-I',str(ROOT/'tests'),
            '-module-cache-path',str(cls.directory/'swift-cache'),str(ROOT/'EngineLanSession.swift'),str(ROOT/'EngineLanBindings.swift'),
            str(ROOT/'tests/native_fixture.swift'),str(cls.directory/'fixture.o'),str(library),
            '-Xlinker','-lresolv','-Xlinker','-liconv','-o',str(cls.binary)],capture_output=True,text=True,timeout=90)
        if result.returncode:raise RuntimeError(result.stderr)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    async def asyncSetUp(self):
        self.relay=relay.Relay();self.server=await asyncio.start_server(self.relay.client,'127.0.0.1',0,limit=8192)
        self.port=self.server.sockets[0].getsockname()[1];self.children=[]

    async def asyncTearDown(self):
        for child in self.children:
            if child.returncode is None:child.terminate();await child.wait()
        self.server.close();await self.server.wait_closed();await self.relay.close();await asyncio.sleep(0.05)

    async def test_native_swift_rust_socket_callbacks_to_browser_wasm_and_back(self):
        endpoint=f'ws://127.0.0.1:{self.port}/engine-lan'
        browser=await asyncio.create_subprocess_exec('node',str(ROOT/'tests/browser_fixture.cjs'),str(self.fixture),endpoint,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE);self.children.append(browser)
        line=await asyncio.wait_for(browser.stdout.readline(),15)
        if line!=b'BROWSER_ENGINE_LAN_READY\n':
            _,error=await browser.communicate();self.fail(error.decode()[:2000])
        native=await asyncio.create_subprocess_exec(str(self.binary),endpoint,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE);self.children.append(native)
        (out,error),(browser_out,browser_error)=await asyncio.wait_for(asyncio.gather(native.communicate(),browser.communicate()),20)
        self.assertEqual(native.returncode,0,error.decode()[:2000]);self.assertIn(b'NATIVE_ENGINE_LAN_REPLY_PASS',out)
        self.assertEqual(browser.returncode,0,browser_error.decode()[:2000]);self.assertIn(b'BROWSER_ENGINE_LAN_WASM_REPLY_PASS',browser_out)

    async def test_wrong_origin_is_closed_without_admission(self):
        reader,writer=await asyncio.open_connection('127.0.0.1',self.port)
        writer.write(b'GET /engine-lan HTTP/1.1\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: AAAAAAAAAAAAAAAAAAAAAA==\r\nOrigin: https://unrelated.example\r\n\r\n');await writer.drain()
        self.assertEqual(await asyncio.wait_for(reader.read(),2),b'');self.assertFalse(self.relay.rooms)
        writer.close();await writer.wait_closed()

    async def test_mask_fragment_and_size_rules(self):
        good=b'{"type":"ping"}';mask=b'1234';encoded=bytes([0x81,0x80|len(good)])+mask+bytes(b^mask[i%4] for i,b in enumerate(good))
        reader=asyncio.StreamReader();reader.feed_data(encoded);reader.feed_eof()
        self.assertEqual(await relay.frame(reader),(1,good))
        for bad in [b'\x81\x01x',b'\x01\x80',b'\xc1\x80',b'\x83\x80',b'\x82\xfe\x08\x01',b'\x88\x81']:
            reader=asyncio.StreamReader();reader.feed_data(bad);reader.feed_eof()
            with self.assertRaises(ValueError):await relay.frame(reader)


if __name__=='__main__':unittest.main()
