"""Disposable local launcher hosting; never controls the managed Mac relay."""
import asyncio,http.client,json,socket,sys,threading,unittest,subprocess,selectors
from pathlib import Path
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import Mock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import browser_lobby_host as host
from serve_browser import Handler

class BrowserHost(unittest.TestCase):
 def setUp(self):
  self.socket=socket.socket();self.socket.bind(('127.0.0.1',0));self.socket.listen();self.busy=self.socket.getsockname()[1]
  with socket.socket() as s:s.bind(('127.0.0.1',0));free=s.getsockname()[1]
  self.host=host.BrowserLobbyHost(discover=lambda:{'lan':'127.0.0.1','remote':None},ports=(self.busy,free))
 def tearDown(self):self.host.close();self.socket.close()
 def test_explicit_host_falls_back_without_stopping_existing_listener(self):
  self.assertFalse(self.host.status()['running']);state=self.host.start('ROOM','LAN');self.assertTrue(state['running']);
  from lobby_directory import read_health
  self.assertEqual(read_health(state['join'])['rooms'],1,'An empty hosted lobby is still one advertised room')
  self.assertNotIn(':%d/'%self.busy,state['join'])
  self.assertEqual(self.host.start('ROOM','LAN')['id'],state['id'])
  with self.assertRaises(ValueError):self.host.stop('wrong-owner')
  self.assertTrue(self.host.status()['running'])
  with self.assertRaises(ValueError):self.host.start('OTHER','LAN')
  self.assertFalse(self.host.stop(state['id'])['running'])
  self.assertEqual(self.socket.getsockname()[1],self.busy)
 def test_restart_keeps_address_owner_room_and_port_but_changes_epoch(self):
  first=self.host.start('ROOM','LAN');epoch=self.host.engine.epoch
  stopped=self.host.stop(first['id']);self.assertTrue(stopped['can_restart']);self.assertEqual(stopped['join'],first['join'])
  self.assertEqual(self.host.stop(first['id']),stopped)
  with self.assertRaises(ValueError):self.host.restart('other-owner')
  second=self.host.restart(first['id'])
  for key in ['id','room','connection','join','lan','remote']:self.assertEqual(second[key],first[key])
  self.assertNotEqual(self.host.engine.epoch,epoch)
  epoch2=self.host.engine.epoch;self.assertEqual(self.host.restart(first['id'])['id'],first['id']);self.assertEqual(self.host.engine.epoch,epoch2)
 def test_restart_refuses_occupied_port_and_changed_network_then_retries(self):
  first=self.host.start('ROOM','LAN');port=self.host.last_port;self.host.stop(first['id'])
  self.socket.close() # Even though the original first-choice port is now free.
  with socket.socket() as occupant:
   occupant.bind(('127.0.0.1',port));occupant.listen()
   with self.assertRaisesRegex(ValueError,'previous lobby port is busy'):self.host.restart(first['id'])
   self.assertFalse(self.host.status()['running']);self.assertTrue(self.host.status()['can_restart'])
   self.assertEqual(occupant.getsockname()[1],port)
  self.host.discover=lambda:{'lan':'192.168.1.254','remote':None}
  with self.assertRaisesRegex(ValueError,'network changed'):self.host.restart(first['id'])
  self.host.discover=lambda:{'lan':'127.0.0.1','remote':None}
  self.assertEqual(self.host.restart(first['id'])['join'],first['join'])

 def test_real_browser_clients_rejoin_the_restarted_host(self):
  state=self.host.start('ROOM','LAN')
  process=subprocess.Popen(['node',str(ROOT/'tests/browser_host_rejoin.cjs'),state['join']],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   with selectors.DefaultSelector() as selector:
    selector.register(process.stdout,selectors.EVENT_READ)
    self.assertTrue(selector.select(timeout=10),'Browser admission timed out')
   self.assertEqual(process.stdout.readline().strip(),'HOST_CLIENTS_READY')
   self.assertEqual(self.host.status()['peers'],2)
   from lobby_directory import read_health
   health=read_health(state['join']);self.assertEqual(health['players'],2);self.assertEqual(health['lobbies'],[{'room':'ROOM','players':2,'slots':2,'capacity':8}]);self.assertEqual(self.host.status()['peers'],2,'Read-only checks must not consume a player slot')
   self.host.stop(state['id']);self.assertEqual(self.host.restart(state['id'])['join'],state['join'])
   out,err=process.communicate('restarted\n',timeout=10)
   self.assertEqual(process.returncode,0,(out,err))
   self.assertIn('BROWSER_HOST_RESTART_TWO_CLIENTS_SAME_BUFFERS_HANDLES_AND_DATA_PASS',out)
  finally:
   if process.poll() is None:process.kill();process.communicate()

 def test_phone_capacity_and_recovery_cannot_bypass_eight_slots(self):
  async def check():
   relay=host.RoomRelay('ROOM');writer=Mock()
   message=dict(type='join',protocol=host.relay.PROTOCOL,build=host.relay.BUILD,room='ROOM',name='Test')
   for i in range(8):relay.admit(message,writer)
   with self.assertRaises(ValueError):relay.admit(message,writer)
   relay=host.RoomRelay('ROOM')
   with self.assertRaisesRegex(ValueError,'eight slots'):relay.admit(dict(message,rejoin=dict(vip=host.relay.NET|9,epoch=relay.epoch)),writer)
   self.assertEqual(relay.catalog()[0]['slots'],0)
  asyncio.run(check())

 def test_lan_does_not_bind_an_unavailable_vpn_interface(self):
  self.host.discover=lambda:{'lan':'127.0.0.1','remote':'100.127.255.254'}
  state=self.host.start('LAN-ONLY','LAN');self.assertTrue(state['running']);self.assertEqual(state['remote'],'')
  self.assertFalse(self.host.stop(state['id'])['running'])

 def test_remote_requires_existing_vpn_and_public_binding_is_refused(self):
  with self.assertRaisesRegex(ValueError,'Tailscale'):self.host.start('ROOM','Remote')
  self.assertFalse(self.host.status()['running'])
  for room in ['', '  ','bad\nroom',True,'x'*65]:
   with self.assertRaises(ValueError):self.host.start(room,'LAN')
  self.host.discover=lambda:{'lan':'8.8.8.8','remote':None}
  with self.assertRaises(ValueError):self.host.start('ROOM','LAN')
 def test_same_origin_api_and_owned_stop(self):
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.content=SimpleNamespace(lobby_host=self.host);server.daemon_threads=True
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();port=server.server_port
  def request(action,body,origin=None,lab=True):
   c=http.client.HTTPConnection('127.0.0.1',port,timeout=4);headers={'Content-Type':'application/json'}
   if origin:headers['Origin']=origin
   if lab:headers['X-Zema-Lab']='1'
   c.request('POST','/zema-lab/host/'+action,json.dumps(body),headers);r=c.getresponse();raw=r.read();c.close();return r.status,raw
  try:
   self.assertEqual(request('start',{'room':'ROOM','connection':'LAN'},'https://hostile.example')[0],403)
   self.assertEqual(request('start',{'room':'ROOM','connection':'LAN'},lab=False)[0],403)
   self.assertFalse(self.host.status()['running'])
   code,raw=request('start',{'room':'ROOM','connection':'LAN'});self.assertEqual(code,200,raw);state=json.loads(raw)
   self.assertEqual(request('stop',{'id':'other'})[0],400);self.assertTrue(self.host.status()['running'])
   self.assertEqual(request('stop',{'id':state['id']})[0],200);self.assertFalse(self.host.status()['running'])
   self.assertEqual(request('restart',{'id':state['id']},'https://hostile.example')[0],403)
   self.assertEqual(request('restart',{'id':state['id']},lab=False)[0],403)
   self.assertEqual(request('restart',{'id':state['id'],'room':'OTHER'})[0],400)
   self.assertEqual(request('restart',{'id':'other'})[0],400)
   self.assertFalse(self.host.status()['running'])
   code,raw=request('restart',{'id':state['id']});self.assertEqual(code,200,raw);self.assertEqual(json.loads(raw)['join'],state['join'])
  finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':unittest.main()
