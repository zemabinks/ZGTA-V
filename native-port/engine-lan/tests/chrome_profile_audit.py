#!/usr/bin/env python3
"""Real Chrome IndexedDB audit using only a disposable profile and localhost."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
ROOT=Path(__file__).resolve().parents[1]
CHROME=Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy','same-origin');self.send_header('Cross-Origin-Embedder-Policy','require-corp');self.send_header('Cross-Origin-Resource-Policy','same-origin');super().end_headers()
    def do_GET(self):
        path=self.path.split('?',1)[0]
        allowed={'/':ROOT/'tests/chrome_profile.html',**{('/'+name):ROOT/name for name in ['online.js','profile-rpc.js','profile-worker.js','browser-saves.js']},'/tests/chrome_profile_worker.js':ROOT/'tests/chrome_profile_worker.js'}
        if path not in allowed:self.send_error(404);return
        data=allowed[path].read_bytes();self.send_response(200);self.send_header('Content-Type','text/html' if path=='/' else 'text/javascript');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_POST(self):
        if self.path!='/result':self.send_error(404);return
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=65536:raise ValueError('Report size')
            result=json.loads(self.rfile.read(n));self.server.results.put(result);self.send_response(200);self.send_header('Content-Length','0');self.end_headers()
        except (ValueError,OSError):self.send_error(400)

def run():
    if not CHROME.is_file():raise RuntimeError('Existing Chrome is unavailable; do not install')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.results=queue.Queue();server.daemon_threads=True
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();records=[]
    try:
        with tempfile.TemporaryDirectory(prefix='zema-chrome-profile-audit-') as folder:
            directory=Path(folder).resolve();profile=directory/'browser-profile'
            for phase in ['seed','resume','corrupt']:
                command=[str(CHROME),'--headless=new','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','--user-data-dir='+str(profile),'--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-sync','--disable-component-update','--disable-default-apps','--disable-extensions','--password-store=basic','--use-mock-keychain','--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=localhost;127.0.0.1','http://127.0.0.1:'+str(server.server_port)+'/?phase='+phase]
                with (directory/(phase+'.log')).open('w') as log:
                    process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
                    try:
                        try:result=server.results.get(timeout=45)
                        except queue.Empty:raise RuntimeError('Chrome fixture timeout: '+(directory/(phase+'.log')).read_text(errors='replace')[-2500:])
                        if result.get('phase')!=phase or not result.get('ok'):raise RuntimeError(json.dumps(result))
                        records.append(result);print('CHROME_PROFILE_'+phase.upper()+'_PASS',flush=True)
                    finally:
                        process.terminate()
                        try:process.wait(timeout=10)
                        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            if records[0]['sha256']!=records[1]['sha256'] or records[0]['id']!=records[1]['id']:raise RuntimeError('Browser process restart changed profile')
    finally:server.shutdown();server.server_close();thread.join()
    return {'format':'zema-real-chrome-profile-audit-v1','records':records,'profile':'DISPOSABLE_ONLY','game_executed':False,'external_network':'BLOCKED_BY_PROCESS_ONLY_LOOPBACK_PROXY','installed_software':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args();record=run()
    with a.output.open('x') as target:target.write(json.dumps(record,indent=2)+'\n')
    print('REAL_CHROME_SHARED_PROFILE_DISK_RESTART_CONFLICT_CORRUPTION_PASS',flush=True)
