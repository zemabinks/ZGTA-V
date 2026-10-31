"""Discovery candidates must be bounded/private, and all sockets close on errors."""
import hashlib,json,sys,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import lobby_discovery_portable as discovery

class PortableDiscovery(unittest.TestCase):
 def test_vendored_sources_match_upstream_receipt(self):
  manifest=json.loads((discovery.VENDOR/'provenance.json').read_text())
  self.assertEqual([r['version'] for r in manifest['dependencies']],['0.147.2','0.2.0'])
  for row in manifest['dependencies']:
   self.assertTrue(row['source'].startswith('https://files.pythonhosted.org/'))
   for name,digest in row['files'].items():self.assertEqual(hashlib.sha256((discovery.VENDOR/name).read_bytes()).hexdigest(),digest,name)
 def test_private_lan_excludes_loopback_public_vpn_and_hostnames(self):
  for value in ['192.168.1.33','10.2.3.4','172.16.0.1']:self.assertTrue(discovery.private_lan(value))
  for value in ['127.0.0.1','8.8.8.8','100.70.1.9','::1','host.local','192.168.1.33:22',None]:self.assertFalse(discovery.private_lan(value))
 def dependencies(self,fail=False):
  owner=self
  class ZC:
   def __init__(self,**kw):owner.options=kw;owner.closed=False
   def get_service_info(self,kind,name,timeout):
    owner.lookups.append((kind,name,timeout))
    if fail:raise OSError('fixture denied')
    return SimpleNamespace(port=47542,parsed_addresses=lambda version:['127.0.0.1','8.8.8.8','100.70.1.1','192.168.2.4','192.168.2.4'])
   def close(self):owner.closed=True
  class Browser:
   def __init__(self,zc,kind,listener):
    self.cancelled=False;owner.browser=self
    for i in range(50):listener.add_service(zc,kind,'host%d.'%i+kind)
   def cancel(self):self.cancelled=True
  owner.lookups=[]
  adapter=SimpleNamespace(get_adapters=lambda:[SimpleNamespace(ips=[SimpleNamespace(ip='192.168.2.3',is_IPv4=True),SimpleNamespace(ip='100.70.1.2',is_IPv4=True)])])
  return ZC,Browser,None,SimpleNamespace(V4Only='v4'),adapter
 def test_bounded_results_and_resources_close(self):
  with patch.object(discovery,'dependencies',return_value=self.dependencies()):result=discovery.discover(timeout=.1)
  self.assertTrue(result['available']);self.assertEqual(result['addresses'],['ws://192.168.2.4:47542/engine-lan'])
  self.assertTrue(self.closed and self.browser.cancelled);self.assertLessEqual(len({x[1] for x in self.lookups}),8)
  self.assertEqual(self.options,{'interfaces':['192.168.2.3'],'ip_version':'v4'})
 def test_permission_error_is_visible_and_closes_resources(self):
  with patch.object(discovery,'dependencies',return_value=self.dependencies(fail=True)):result=discovery.discover(timeout=.1)
  self.assertFalse(result['available']);self.assertIn('firewall',result['message']);self.assertTrue(self.closed and self.browser.cancelled)
 def test_no_network_and_invalid_advertisement_do_not_open_sockets(self):
  deps=self.dependencies();deps=deps[:-1]+(SimpleNamespace(get_adapters=lambda:[]),)
  with patch.object(discovery,'dependencies',return_value=deps):self.assertFalse(discovery.discover()['available'])
  announcement=discovery.Announcement();announcement.start('ROOM',47542,'8.8.8.8')
  self.assertIsNone(announcement.thread);self.assertEqual(announcement.status()['state'],'unavailable');announcement.stop()
if __name__=='__main__':unittest.main()
