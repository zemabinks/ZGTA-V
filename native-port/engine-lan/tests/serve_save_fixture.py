"""Disposable localhost storage fixture, no production database names or game."""
import io
from pathlib import Path
import sys
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from serve_browser import ROOT,Handler,ThreadingHTTPServer

class Content:
    def __init__(self):
        source=(ROOT/'browser-saves.js').read_text()
        before="'zema-browser-'+mode+'-userdata-v1'"
        if source.count(before)!=1:raise ValueError('Fixture namespace anchor changed')
        self.source=source.replace(before,"'zema-disposable-"+uuid.uuid4().hex+"-'+mode+'-userdata-v1'").encode()
    def select(self,path):
        if path=='/':return io.BytesIO((ROOT/'tests/save_fixture.html').read_bytes()),'text/html'
        if path=='/browser-saves.js':return io.BytesIO(self.source),'text/javascript'
        raise FileNotFoundError(path)

server=ThreadingHTTPServer(('127.0.0.1',18888),Handler);server.content=Content();server.daemon_threads=True
print('Disposable save test: http://127.0.0.1:18888/',flush=True)
try:server.serve_forever()
except KeyboardInterrupt:pass
finally:server.server_close()
