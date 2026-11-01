"""Explicit private loopback QA origin; never replace the owner's port 18887.

Uses the normal validated Content/Handler and a disposable unmodified relay.
This is a test harness, not a change to the production launcher port policy.
"""
import asyncio
import io
import json
from pathlib import Path
import sys
import threading
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import relay
import serve_browser as web

def main():
    mirror,stage,evidence=map(lambda s:Path(s).absolute(),sys.argv[1:])
    evidence.mkdir(parents=True,exist_ok=True)
    loop=asyncio.new_event_loop();thread=threading.Thread(target=loop.run_forever,daemon=True);thread.start()
    r=relay.Relay();server=asyncio.run_coroutine_threadsafe(asyncio.start_server(r.client,'127.0.0.1',0),loop).result()
    endpoint=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}/engine-lan'
    class Handler(web.Handler):
        def do_GET(self):
            if self.path in ['/voice108-probe','/voice108-ui','/voice108-endpoint']:
                if self.path=='/voice108-probe':data=(ROOT/'tests/voice_browser_probe.html').read_bytes()
                elif self.path=='/voice108-endpoint':data=endpoint.encode()
                else:data=b'''<!doctype html><meta charset="utf-8"><title>ZGTA voice controls 108 private preview</title><style>body{background:#243544;color:white;font:16px system-ui;padding:32px}</style><h1>Private voice controls preview</h1><p>Open Connection to inspect the production voice controls.</p><script src="/zema-lab/connection-ui.js"></script><script src="/zema-lab/voice-core.js"></script><script src="/zema-lab/voice-ui.js"></script><script>const s=new ZemaVoiceCore.Shared();s.connection(true,0x0a4d0001);s.publish([100,100,20]);const p=ZemaConnectionUI.mount({room:'VOICE108',relay:'Private QA',connection:'LAN'});ZemaVoiceUI.mount(s.buffer,p.root,'/b/8b0b5899ed/');p.show();</script>'''
                self.send_response(200);self.send_header('Content-Type','text/plain' if self.path.endswith('endpoint') else 'text/html');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
            super().do_GET()
        def do_POST(self):
            if self.path=='/voice108-result':
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<4096:self.send_error(400);return
                proof=json.loads(self.rfile.read(length));(evidence/'chrome-audio-probe.json').write_text(json.dumps(proof,indent=2)+'\n');self.send_response(204);self.end_headers();return
            super().do_POST()
    content=web.Content(mirror,stage)
    http=web.ThreadingHTTPServer(('127.0.0.1',18886),Handler);http.content=content;http.daemon_threads=True
    print('Private voice QA http://127.0.0.1:18886/voice108-probe',flush=True)
    try:http.serve_forever()
    finally:
        content.lobby_host.close();content.lobby_directory.close();http.server_close();server.close();asyncio.run_coroutine_threadsafe(r.close(),loop).result();loop.call_soon_threadsafe(loop.stop)

if __name__=='__main__':main()
