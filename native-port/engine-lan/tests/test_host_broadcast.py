"""Actual C/Python config parity, bounded host sizing and transactional refusal."""
import ctypes,hashlib,random,subprocess,sys,tempfile,unittest
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import serve_browser
HOST={35000:2,11000:2,7500:2,4000:4,2000:3,1500:2,1000:6,500:3,250:4,120:12}
PLAYER={3600:1,2500:2,1200:2,600:2,500:2,400:2,150:4,80:4,40:8,0:0}
TARGETS={'HostBroadcastData':{7500:3,4000:6},'PlayerBroadcastData':{3600:3,2500:4,150:12,80:12,40:16}}
def fixture(host=None,player=None,tabs=4):
 def group(name,rows):
  return '<'+name+'>\r\n'+''.join('<Item><SizeOfData value="%d"/>\r\n%s<NumInstances value="%d"/></Item>\r\n'%(s,'\t'*tabs,n)for s,n in rows.items())+'</'+name+'>\r\n'
 return ('<Settings>untouched-start\r\n'+group('HostBroadcastData',HOST if host is None else host)+'<Other value="preserve me"/>\r\n'+group('PlayerBroadcastData',PLAYER if player is None else player)+'untouched-end</Settings>').encode()
def counts(data,name):return {int(x.find('SizeOfData').get('value')):int(x.find('NumInstances').get('value'))for x in ET.fromstring(data).find('.//'+name).findall('Item')}
class HostBroadcast(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='zgta-host-broadcast-');lib=Path(cls.temp.name)/'overlay.dylib'
  subprocess.run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-dynamiclib',str(ROOT/'BroadcastOverlay.c'),'-o',str(lib)],check=True,capture_output=True,text=True)
  cls.native=ctypes.CDLL(str(lib)).ZemaBroadcastPatch;cls.native.argtypes=[ctypes.c_void_p,ctypes.c_size_t];cls.native.restype=ctypes.c_int
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def apply(self,data):
  b=ctypes.create_string_buffer(data);self.assertEqual(self.native(b,len(data)),1);out=serve_browser.overlay(data);self.assertEqual(b.raw[:len(data)],out);self.assertEqual(len(out),len(data));return out
 def reject(self,data):
  b=ctypes.create_string_buffer(data);self.assertEqual(self.native(b,len(data)),0);self.assertEqual(b.raw[:len(data)],data)
  with self.assertRaises(ValueError):serve_browser.overlay(data)
 def test_exact_pools_and_idempotence(self):
  data=fixture();out=self.apply(data)
  for name,original in [('HostBroadcastData',HOST),('PlayerBroadcastData',PLAYER)]:
   expected=dict(original);expected.update(TARGETS[name]);self.assertEqual(counts(out,name),expected)
  self.assertEqual(self.apply(out),out);self.assertIn(b'<Other value="preserve me"/>\r\n',out)
  self.assertEqual((3-2)*(7500*2+8)+(6-4)*(4000*2+8),31024)
 def test_higher_custom_counts_unchanged(self):
  data=fixture({s:99 for s in HOST},{s:99 for s in PLAYER});self.assertEqual(self.apply(data),data)
 def test_random_counts_and_unrelated_pool_preservation(self):
  rng=random.Random(20261027)
  for _ in range(100):
   host={s:rng.randrange(1,1000)for s in HOST};player={s:rng.randrange(1,1000)for s in PLAYER};out=self.apply(fixture(host,player))
   for name,original in [('HostBroadcastData',host),('PlayerBroadcastData',player)]:self.assertEqual(counts(out,name),{s:max(n,TARGETS[name].get(s,n))for s,n in original.items()})
 def test_actual_config_native_browser_parity_and_original_preserved(self):
  p=Path.home()/'Library/Application Support/ZRemote Controller/Games/playgta5-offline/mirror/playgta5.com/data/common/data/gameconfig.xml'
  if not p.is_file():self.skipTest('Optional local game mirror is unavailable')
  data=p.read_bytes();out=self.apply(data)
  for name,targets in TARGETS.items():self.assertEqual(counts(out,name),{s:max(n,targets.get(s,n))for s,n in counts(data,name).items()})
  self.assertEqual(hashlib.sha256(p.read_bytes()).digest(),hashlib.sha256(data).digest())
 def test_late_player_failure_does_not_commit_host_edits(self):self.reject(fixture().replace(b'<SizeOfData value="40"/>',b'<SizeOfData value="41"/>'))
 def test_missing_duplicate_reversed_sections_and_counts(self):
  data=fixture()
  for name in TARGETS:
   opening=('<'+name+'>').encode();closing=('</'+name+'>').encode()
   for bad in [data.replace(opening,b''),data+opening+closing,data.replace(closing,closing+closing),closing+data.replace(closing,b'')]:self.reject(bad)
  for size in [7500,4000,40]:
   tag=('<SizeOfData value="%d"/>'%size).encode();self.reject(data.replace(tag,tag+tag))
  self.reject(data.replace(b'<SizeOfData value="7500"/>\r\n\t\t\t\t<NumInstances value="2"/>',b'<SizeOfData value="7500"/>\r\n\t\t\t\t<NumInstances value="2"/><NumInstances value="3"/>',1))
 def test_bad_counts_indentation_and_nul_refuse_transactionally(self):
  data=fixture()
  for bad in [b'',b'-1',b'x',b'1234567890']:self.reject(data.replace(b'<SizeOfData value="7500"/>\r\n\t\t\t\t<NumInstances value="2"/>',b'<SizeOfData value="7500"/>\r\n\t\t\t\t<NumInstances value="'+bad+b'"/>',1))
  self.reject(fixture(tabs=0));self.reject(data+b'\0')
 def test_size_cap_refuses_before_scan(self):self.reject(b'x'*(16*1024*1024+1))
if __name__=='__main__':unittest.main()
