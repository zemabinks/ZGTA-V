import hashlib
import importlib.util
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import threading
import unittest

spec = importlib.util.spec_from_file_location('range_downloader', Path(__file__).resolve().parents[1]/'Scripts/download_ranges.py')
downloader = importlib.util.module_from_spec(spec); spec.loader.exec_module(downloader)
DATA = bytes(range(256))*1537
ATTEMPTS = {}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        first,last = map(int,self.headers['Range'].removeprefix('bytes=').split('-'))
        last=min(last,len(DATA)-1)
        if self.path=='/wrong': first += 1
        self.send_response(206)
        self.send_header('Content-Range',f'bytes {first}-{last}/{len(DATA)}')
        self.send_header('Content-Length',str(last-first+1));self.end_headers()
        key=(self.path,first); ATTEMPTS[key]=ATTEMPTS.get(key,0)+1
        if self.path=='/retry' and first==65536 and ATTEMPTS[key]==1:
            self.wfile.write(DATA[first:first+100]);self.close_connection=True
        else:self.wfile.write(DATA[first:last+1])

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls): cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def test_truncation_retries_and_preserves_all_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'data'
            downloader.download(self.url+'/retry',target,hashlib.sha256(DATA).hexdigest())
            self.assertEqual(target.read_bytes(),DATA)
            self.assertEqual(ATTEMPTS[('/retry',65536)],2)
    def test_wrong_range_or_hash_never_replaces_existing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'data';target.write_bytes(b'original')
            for path,digest in [('/wrong',None),('/hash','0'*64)]:
                with self.assertRaises((OSError,ValueError)):downloader.download(self.url+path,target,digest)
                self.assertEqual(target.read_bytes(),b'original')
                self.assertFalse(target.with_name('data.part').exists())

if __name__=='__main__':unittest.main()
