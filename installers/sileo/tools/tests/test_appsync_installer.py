import hashlib,json,os,shlex,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PAYLOAD=b'known IPA fixture\n'
class AppSyncInstaller(unittest.TestCase):
 def run_installer(self,case='good'):
  with tempfile.TemporaryDirectory(prefix='zema-asu-test-') as tmp:
   root=Path(tmp);commands=root/'bin';commands.mkdir();log=root/'called.json'
   text=(ROOT/'package-sources/appsync-installer/postinst.in').read_text()
   for k,v in {'APP_NAME':'Fixture','IPA_URL':'https://example.invalid/fixture.ipa','SHA256':hashlib.sha256(PAYLOAD).hexdigest(),'BYTES':str(len(PAYLOAD))}.items():text=text.replace('@'+k+'@',shlex.quote(v))
   text=text.replace('PATH=/usr/sbin:/usr/bin:/sbin:/bin','PATH='+str(commands)+':/usr/bin:/bin').replace('/private/var/containers/Bundle/Application',str(root/'private-apps')).replace('/var/containers/Bundle/Application',str(root/'apps')).replace('/Applications/TrollStoreLite.app',str(root/'lite')).replace('/usr/bin/appinst',str(commands/'appinst')).replace('/var/tmp/zema-appsync.',str(root/'download.'))
   def exe(name,body):
    p=commands/name;p.write_text(body);p.chmod(0o755)
   exe('id','#!/bin/sh\necho "${MOCK_UID:-0}"\n')
   exe('uname','#!/bin/sh\nif [ "$1" = -s ]; then echo Darwin; elif [ "$MOCK_CASE" = wrong-cpu ]; then echo armv7; else echo arm64; fi\n')
   exe('stat','#!/bin/sh\nif [ "$MOCK_CASE" = untrusted ]; then echo 501; else echo 0; fi\n')
   exe('dpkg','''#!/usr/bin/env python3
import os,sys
if sys.argv[1]=='--print-architecture':print('iphoneos-arm64' if os.environ['MOCK_CASE']=='rootless' else 'iphoneos-arm');sys.exit(0)
a,b=sys.argv[2],sys.argv[4]
def version(s):return tuple(map(int,s.split('.')))
sys.exit(0 if (version(a)>=version(b) if sys.argv[3]=='ge' else version(a)<=version(b)) else 1)
''')
   exe('dpkg-query','''#!/usr/bin/env python3
import os,sys
case=os.environ['MOCK_CASE'];p=sys.argv[-1]
if case=='missing-dependency' and p=='ai.akemi.appinst':sys.exit(1)
if sys.argv[2]=="-f=${db:Status-Status}":print('unpacked' if case=='unconfigured' else 'installed');sys.exit(0)
print(('18.3' if case=='unsupported-ios' else '17.0') if p=='firmware' else ('115.0' if case=='old-dependency' else '116.0') if p=='ai.akemi.appsyncunified' else '2.1.1')
''')
   exe('curl','''#!/usr/bin/env python3
import os,sys
from pathlib import Path
if os.environ['MOCK_CASE']=='download-fails':sys.exit(22)
a=sys.argv[1:];p=Path(a[a.index('--output')+1]);data=bytes.fromhex(os.environ['MOCK_PAYLOAD'])
if os.environ['MOCK_CASE']=='wrong-size':data+=b'x'
if os.environ['MOCK_CASE']=='wrong-hash':data=bytes([data[0]^1])+data[1:]
p.write_bytes(data)
''')
   exe('sha256sum','''#!/usr/bin/env python3
import hashlib,sys
from pathlib import Path
print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest()+'  '+sys.argv[1])
''')
   exe('appinst','''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
Path(os.environ['MOCK_LOG']).write_text(json.dumps({'args':sys.argv[1:],'payload':Path(sys.argv[1]).read_bytes().hex()}))
sys.exit(6 if os.environ['MOCK_CASE']=='appinst-fails' else 0)
''')
   if case=='trollstore-present':
    app=root/'apps/0/TrollStore.app';app.mkdir(parents=True);(app/'trollstorehelper').write_text('fixture')
   if case=='trollstore-managed':
    app=root/'apps/0/PlayGTA5Native.app';app.mkdir(parents=True);(app.parent/'_TrollStore').touch()
   script=root/'postinst';script.write_text(text)
   env=dict(os.environ,MOCK_CASE=case,MOCK_LOG=str(log),MOCK_PAYLOAD=PAYLOAD.hex(),MOCK_UID='501' if case=='nonroot' else '0')
   result=subprocess.run(['/bin/sh',str(script),'configure'],env=env,capture_output=True,text=True,timeout=10)
   return result,json.loads(log.read_text()) if log.exists() else None,list(root.glob('download.*'))
 def test_official_appinst_receives_exact_verified_payload(self):
  r,call,left=self.run_installer();self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(len(call['args']),1);self.assertEqual(call['payload'],PAYLOAD.hex());self.assertEqual(left,[])
 def test_incompatible_or_missing_dependencies_stop_before_install(self):
  for case in ['nonroot','wrong-cpu','rootless','unsupported-ios','missing-dependency','unconfigured','old-dependency','untrusted','trollstore-present','trollstore-managed']:
   with self.subTest(case=case):
    r,call,left=self.run_installer(case);self.assertNotEqual(r.returncode,0,r.stdout);self.assertIsNone(call);self.assertEqual(left,[])
 def test_bad_download_cannot_install(self):
  for case in ['download-fails','wrong-size','wrong-hash']:
   with self.subTest(case=case):
    r,call,left=self.run_installer(case);self.assertNotEqual(r.returncode,0,r.stdout);self.assertIsNone(call);self.assertEqual(left,[])
 def test_appinst_error_is_not_success(self):
  r,call,left=self.run_installer('appinst-fails');self.assertNotEqual(r.returncode,0);self.assertIsNotNone(call);self.assertIn('returned 6',r.stderr);self.assertNotIn('installation complete',r.stdout);self.assertEqual(left,[])
if __name__=='__main__':unittest.main()
