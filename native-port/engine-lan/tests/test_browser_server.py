"""Disposable loopback HTTP tests; never starts a game or production listener."""
import ctypes
import subprocess
import gzip
import hashlib
import http.client
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import serve_browser as server

HOST_FIXTURE=b'<HostBroadcastData>'+b''.join(('<Item><SizeOfData value="%d"/>\n\t\t<NumInstances value="1"/></Item>'%n).encode() for n in server.HOST_SIZES)+b'</HostBroadcastData>'
FIXTURE=HOST_FIXTURE+b'<PlayerBroadcastData>'+b''.join(('<Item><SizeOfData value="%d"/>\n\t\t<NumInstances value="1"/></Item>'%n).encode() for n in server.SIZES)+b'</PlayerBroadcastData>'

class BrowserServer(unittest.TestCase):
    def test_fixed_length_idempotent_preserves_higher_values(self):
        out=server.overlay(FIXTURE);self.assertEqual(len(out),len(FIXTURE));self.assertEqual(server.overlay(out),out)
        higher=FIXTURE.replace(b'value="1"',b'value="99"');self.assertEqual(server.overlay(higher),higher)
        with self.assertRaises(ValueError):server.overlay(FIXTURE.replace(b'value="1"',b'value="a"',1))
        with self.assertRaises(ValueError):server.overlay(FIXTURE.replace(b'</PlayerBroadcastData>',b'<Item><SizeOfData value="80"/></Item></PlayerBroadcastData>'))
    def test_native_browser_overlay_bytes_match(self):
        with tempfile.TemporaryDirectory(prefix='zema-overlay-parity-') as temp:
            library=Path(temp)/'overlay.dylib'
            result=subprocess.run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-dynamiclib',str(server.ROOT/'BroadcastOverlay.c'),'-o',str(library)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            native=ctypes.CDLL(str(library)).ZemaBroadcastPatch;native.argtypes=[ctypes.c_void_p,ctypes.c_size_t];native.restype=ctypes.c_int
            for data in [FIXTURE,server.overlay(FIXTURE),FIXTURE.replace(b'value="1"',b'value="99"')]:
                buffer=ctypes.create_string_buffer(data);self.assertEqual(native(buffer,len(data)),1);self.assertEqual(buffer.raw[:len(data)],server.overlay(data))
            malformed=FIXTURE.replace(b'value="1"',b'value="x"',1);buffer=ctypes.create_string_buffer(malformed)
            self.assertEqual(native(buffer,len(malformed)),0);self.assertEqual(buffer.raw[:len(malformed)],malformed)

    def test_changed_launcher_refused(self):
        with self.assertRaises(ValueError):server.index(b'new source')
    def test_http_ranges_batch_overlay_and_traversal(self):
        with tempfile.TemporaryDirectory(prefix='zema-browser-http-') as temp:
            root=Path(temp).resolve();mirror=root/'mirror';stage=root/'stage';mirror.mkdir();stage.mkdir();(mirror/'data').mkdir()
            asset=mirror/'data/asset.bin';asset.write_bytes(b'0123456789');(mirror/'data/link').symlink_to(root/'outside');(root/'outside').write_bytes(b'private')
            content=server.Content.__new__(server.Content);content.mirror=mirror;content.stage=stage;content.files=set();content.index=b'<html>fixture</html>';content.config=server.overlay(FIXTURE);content.assets={'launcher.html':b'fixture'};content.pages={};content.offline={'story':{},'sandbox':{}}
            before=hashlib.sha256(asset.read_bytes()).hexdigest()
            listener=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);listener.content=content;listener.daemon_threads=True;thread=threading.Thread(target=listener.serve_forever,daemon=True);thread.start()
            def request(method,path,body=None,headers=None):
                connection=http.client.HTTPConnection('127.0.0.1',listener.server_port,timeout=5);connection.request(method,path,body,headers or {});response=connection.getresponse();data=response.read();result=response.status,dict(response.getheaders()),data;connection.close();return result
            try:
                status,headers,data=request('GET','/data/asset.bin',headers={'Range':'bytes=2-5'});self.assertEqual((status,data),(206,b'2345'));self.assertEqual(headers['Cross-Origin-Embedder-Policy'],'require-corp')
                self.assertEqual(request('HEAD','/data/asset.bin')[2],b'')
                self.assertEqual(request('GET','/data/asset.bin',headers={'Range':'bytes=100-'})[0],416)
                for path in ['/data/%2e%2e/outside','/data/link','/data/']:
                    self.assertIn(request('GET',path)[0],(400,404))
                self.assertEqual(request('GET','/',headers={'Host':'evil.example'})[0],403)
                self.assertEqual(request('POST','/data/batch',body='[]',headers={'Origin':'https://evil.example'})[0],403)
                status,headers,data=request('POST','/data/batch?gz=1',body=json.dumps([['asset.bin',1,3],['common/data/gameconfig.xml',0,999999]]));self.assertEqual(status,200);self.assertEqual(gzip.decompress(data),b'123'+content.config)
                self.assertEqual(request('POST','/data/batch',body=json.dumps([['asset.bin',True,2]]))[0],400)
            finally:listener.shutdown();listener.server_close();thread.join()
            self.assertEqual(hashlib.sha256(asset.read_bytes()).hexdigest(),before)

if __name__=='__main__':unittest.main()
