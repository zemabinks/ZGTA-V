"""Serve only synthetic save tests on a new, isolated localhost origin."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = {'/': ROOT/'tests/story_save_fixture.html',
         '/story_save_fixture.js': ROOT/'tests/story_save_fixture.js',
         '/browser-saves.js': ROOT/'browser-saves.js'}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=FILES.get(self.path)
        if not path:
            self.send_error(404);return
        data=path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8' if self.path=='/' else 'text/javascript; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(data)))
        self.end_headers();self.wfile.write(data)
    def log_message(self, *_):pass

if __name__=='__main__':
    with ThreadingHTTPServer(('127.0.0.1',0),Handler) as server:
        print('Isolated Story-save checks: http://127.0.0.1:'+str(server.server_port)+'/',flush=True)
        server.serve_forever()
