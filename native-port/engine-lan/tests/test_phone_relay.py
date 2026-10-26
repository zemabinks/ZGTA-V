"""Actual native listener and URLSession clients; no game/device or Mac relay used."""
import asyncio,json,os,select,socket,struct,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PhoneRelay(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(prefix='zgta-phone-host-');cls.root=Path(cls.tmp.name).resolve();cls.binary=cls.root/'phone-host'
  r=subprocess.run(['/usr/bin/swiftc','-warnings-as-errors','-module-cache-path',str(cls.root/'cache'),str(ROOT/'PhoneRelayProtocol.swift'),str(ROOT/'LobbyAnnouncement.swift'),str(ROOT/'PhoneRelayServer.swift'),str(ROOT/'EngineLanSession.swift'),str(ROOT/'tests/phone_relay.swift'),'-o',str(cls.binary)],capture_output=True,text=True,timeout=90)
  if r.returncode:raise RuntimeError(r.stderr)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def port(self):
  with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
 def test_core_boundaries_and_identity(self):
  r=subprocess.run([str(self.binary),'core'],capture_output=True,text=True,timeout=5);self.assertEqual(r.returncode,0,r.stderr);self.assertIn('WIRE_PASS',r.stdout)
 def test_actual_listener_error_reaches_completion(self):
  with socket.socket() as occupied:
   occupied.bind(('127.0.0.1',0));occupied.listen()
   r=subprocess.run([str(self.binary),'failure',str(occupied.getsockname()[1])],capture_output=True,text=True,timeout=22)
   self.assertEqual(r.returncode,0,r.stdout+r.stderr)
   self.assertIn('127.0.0.1:',r.stdout);self.assertIn('Address already in use',r.stdout)
   self.assertIn('ACTUAL_LISTENER_FAILURE',r.stdout)
 def test_two_real_native_clients_exchange_data(self):
  r=subprocess.run([str(self.binary),'sessions',str(self.port())],capture_output=True,text=True,timeout=15);self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertIn('TWO_CLIENTS',r.stdout)
 def test_two_private_listeners_share_port_and_forward_local_clients(self):
  port=self.port();p=subprocess.Popen([str(self.binary),'dual-serve',str(port)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   self.assertTrue(select.select([p.stdout],[],[],8)[0],'Dual listener readiness timeout')
   line=p.stdout.readline().strip()
   if line=='SKIP_NO_PRIVATE_INTERFACE':self.skipTest('No private interface available for native dual-listener regression')
   self.assertEqual(line,'PHONE_RELAY_READY');asyncio.run(self.exchange(port))
  finally:p.terminate();p.communicate(timeout=5)
 def test_http_handshake_forwarding_resume_and_hostile_frames(self):
  port=self.port();p=subprocess.Popen([str(self.binary),'serve',str(port)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   self.assertTrue(select.select([p.stdout],[],[],8)[0],'Listener readiness timeout');self.assertEqual(p.stdout.readline().strip(),'PHONE_RELAY_READY')
   asyncio.run(self.exchange(port))
  finally:
   p.terminate();p.communicate(timeout=5)
 async def exchange(self,port):
  async def read(r):
   a,n=await asyncio.wait_for(r.readexactly(2),3)
   if n==126:n=struct.unpack('>H',await r.readexactly(2))[0]
   return a&15,await r.readexactly(n)
  def send(w,body,op=1):
   mask=b'1234';n=len(body);header=bytes([0x80|op,0x80|n]) if n<126 else bytes([0x80|op,0xfe])+struct.pack('>H',n)
   w.write(header+mask+bytes(v^mask[i%4] for i,v in enumerate(body)))
  async def join(name,resume=None):
   r,w=await asyncio.open_connection('127.0.0.1',port);w.write(b'GET /engine-lan HTTP/1.1\r\nHost: test\r\nOrigin: http://127.0.0.1:18887\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: MDEyMzQ1Njc4OWFiY2RlZg==\r\n\r\n');await w.drain();self.assertIn(b'101',await r.readuntil(b'\r\n\r\n'))
   msg=dict(type='join',protocol='zema-engine-lan/1',build='8b0b5899ed',room='PHONE-TEST',name=name)
   if resume:msg['resume']=resume
   send(w,json.dumps(msg).encode());await w.drain();_,body=await read(r);return r,w,json.loads(body)
  a=await join('A');b=await join('B')
  try:
   self.assertEqual(a[2]['epoch'],b[2]['epoch']);self.assertNotEqual(a[2]['vip'],b[2]['vip'])
   data=b'G5\x01\x03'+struct.pack('>IHIH',a[2]['vip'],123,b[2]['vip'],123)+b'phone-host-data'
   send(a[1],data,2);await a[1].drain();self.assertEqual(await read(b[0]),(2,data))
   send(a[1],b'{"type":"ping"}');await a[1].drain();self.assertEqual(json.loads((await read(a[0]))[1]),{'type':'pong'})
   c=await join('A',a[2]['resume'])
   try:
    self.assertEqual(c[2],a[2]);self.assertEqual(await asyncio.wait_for(a[0].read(),3),b'')
    send(c[1],data,2);await c[1].drain();self.assertEqual(await read(b[0]),(2,data))
    r,w=await asyncio.open_connection('127.0.0.1',port);w.write(b'GET /health HTTP/1.1\r\nHost: test\r\n\r\n');await w.drain();health=json.loads((await r.read()).split(b'\r\n\r\n',1)[1]);self.assertEqual(health['peers'],2);self.assertEqual(health['lobbies'][0]['player_names'],['A','B']);self.assertNotIn(a[2]['resume'],json.dumps(health));w.close();await w.wait_closed()
    for vip,expected in [(0x0a4d0007,'joined'),(b[2]['vip'],'rejoin-unavailable')]:
     recovery=await join('Recovery','x'*32)
     try:
      self.assertEqual(recovery[2]['type'],'resume-unavailable')
      self.assertEqual(recovery[2]['recovery'],'same-address-v1')
      request=dict(type='join',protocol='zema-engine-lan/1',build='8b0b5899ed',room='PHONE-TEST',name='Recovery',rejoin=dict(vip=vip,epoch=recovery[2]['epoch']))
      send(recovery[1],json.dumps(request).encode());await recovery[1].drain();response=json.loads((await read(recovery[0]))[1])
      self.assertEqual(response['type'],expected)
      if expected=='joined':self.assertEqual(response['vip'],vip)
     finally:recovery[1].close();await recovery[1].wait_closed()
    # A spoofed DATA source closes only its sender; the room/other peer survives.
    spoof=b'G5\x01\x03'+struct.pack('>IHIH',b[2]['vip'],123,a[2]['vip'],123)
    send(c[1],spoof,2);await c[1].drain();self.assertEqual(await asyncio.wait_for(c[0].read(),3),b'')
    send(b[1],b'{"type":"ping"}');await b[1].drain();self.assertEqual(json.loads((await read(b[0]))[1]),{'type':'pong'})
   finally:c[1].close();await c[1].wait_closed()
  finally:
   for _,w,_ in [a,b]:w.close();await w.wait_closed()
if __name__=='__main__':unittest.main()
