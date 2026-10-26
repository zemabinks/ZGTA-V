"""Private read-only directory: real HTTP, deadlines, schemas, no redirects/DNS."""
import json,socket,threading,time,unittest,sys
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import lobby_directory as directory,relay

class Directory(unittest.TestCase):
 def setUp(self):
  self.data={'service':'zgta-engine-lan','protocol':relay.PROTOCOL,'build':relay.BUILD,'instance':'a'*32,'peers':2,'rooms':1,'catalog_version':1,'room_policy':'hosted','lobbies':[{'room':'LOS-SANTOS','players':2,'slots':3,'capacity':8}]}
  owner=self
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_GET(self):
    owner.paths.append(self.path);body=json.dumps(owner.data).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
  self.paths=[];self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.daemon_threads=True;self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.address='ws://127.0.0.1:%d/engine-lan'%self.server.server_port
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join()
 def test_real_catalog_reports_reserved_slots_separately(self):
  result=directory.read_health(self.address);self.assertEqual(result['state'],'online');self.assertEqual(result['players'],2);self.assertEqual(result['lobbies'][0]['slots'],3);self.assertEqual(result['room_policy'],'hosted');self.assertGreaterEqual(result['latency_ms'],0);self.assertEqual(self.paths,['/health'])
 def test_older_host_is_online_without_fabricated_room_counts(self):
  for k in ['catalog_version','lobbies','room_policy']:self.data.pop(k)
  result=directory.read_health(self.address);self.assertEqual(result['state'],'online');self.assertFalse(result['catalog']);self.assertEqual(result['lobbies'],[]);self.assertEqual(result['players'],2)
 def test_protocol_mismatch_is_not_online_compatibility(self):
  self.data['build']='other';self.assertEqual(directory.read_health(self.address)['state'],'incompatible')
 def test_rejects_host_counts_and_room_payloads(self):
  original=json.loads(json.dumps(self.data))
  for bad in [True,-1,2.5,'2',1000000]:
   self.data=dict(original,peers=bad)
   with self.assertRaises(ValueError):directory.read_health(self.address)
  for invalid in [{'room':'','players':0,'slots':0,'capacity':8},{'room':'a\n','players':0,'slots':0,'capacity':8},{'room':'A','players':2,'slots':1,'capacity':8},{'room':'A','players':True,'slots':1,'capacity':8}]:
   self.data=dict(original,lobbies=[invalid])
   with self.assertRaises(ValueError):directory.read_health(self.address)
 def test_private_literal_targets_only(self):
  for bad in ['https://example.com/','ws://example.com/engine-lan','ws://8.8.8.8:80/engine-lan','ws://127.0.0.1:18887/zema-lab/host/stop','ws://user@127.0.0.1/engine-lan','ws://127.0.0.1/engine-lan?x=1','ws://127.0.0.1:65536/engine-lan','ws://127.00.0.1/engine-lan',True]:
   with self.assertRaises(ValueError):directory.endpoint(bad)
  self.assertEqual(directory.endpoint('ws://100.111.120.25:47540/engine-lan'),('100.111.120.25',47540))
 def test_bounded_batches_cache_and_offline_state(self):
  d=directory.LobbyDirectory()
  try:
   for bad in [None,{},[self.address]*13,['ws://8.8.8.8/engine-lan']]:
    with self.assertRaises(ValueError):d.probe(bad)
   self.assertEqual(len(d.probe([self.address,self.address])['hosts']),1);d.probe([self.address]);self.assertEqual(self.paths,['/health'])
   self.assertEqual(d.probe([])['hosts'],[])
  finally:d.close()
 def test_total_response_deadline(self):
  with socket.socket() as server:
   server.bind(('127.0.0.1',0));server.listen();port=server.getsockname()[1]
   def slow():
    connection,_=server.accept()
    with connection:
     connection.recv(4096)
     try:
      for value in b'HTTP/1.1 200 OK\r\n':connection.sendall(bytes([value]));time.sleep(.025)
     except OSError:pass
   thread=threading.Thread(target=slow,daemon=True);thread.start();start=time.monotonic()
   with self.assertRaises((OSError,ValueError)):directory.read_health('ws://127.0.0.1:%d/engine-lan'%port,timeout=.09)
   self.assertLess(time.monotonic()-start,.25);thread.join(timeout=1)

if __name__=='__main__':unittest.main()
