"""Disposable real-browser workers and restartable relay; no GTA or saves."""
from pathlib import Path
import argparse,io,json,sys,threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from serve_browser import Handler,ThreadingHTTPServer,ROOT
from browser_lobby_host import BrowserLobbyHost

parser=argparse.ArgumentParser();parser.add_argument('--restart-delay',type=float,default=27)
args=parser.parse_args()
if not 0.1<=args.restart_delay<=45:parser.error('restart delay must be between 0.1 and 45 seconds')
host=BrowserLobbyHost(discover=lambda:{'lan':'127.0.0.1','remote':None},ports=(47640,47641))
timers=[]
class Content:
    def select(self,path):
        if path=='/':return io.BytesIO((ROOT/'tests/reconnect_fixture.html').read_bytes()),'text/html'
        names={'/browser.js':'browser.js','/network-worker.js':'network-worker.js','/engine-lan-browser.js':'browser.js'}
        if path in names:return io.BytesIO((ROOT/names[path]).read_bytes()),'text/javascript'
        raise FileNotFoundError(path)
class FixtureHandler(Handler):
    def do_POST(self):
        if not self.allowed() or self.headers.get('X-Zema-Lab')!='1' or self.headers.get('Origin')!='http://127.0.0.1:18886' or self.headers.get('Content-Length')!='2' or self.headers.get('Content-Type')!='application/json' or self.rfile.read(2)!=b'{}':self.send_error(403);return
        if self.path=='/fixture/start':result=host.start('QA-RECONNECT','LAN')
        elif self.path=='/fixture/restart':
            state=host.status();host.stop(state['id'])
            timer=threading.Timer(args.restart_delay,lambda:host.restart(state['id']));timers.append(timer);timer.start();result={'restarting':True,'delay':args.restart_delay}
        else:self.send_error(404);return
        data=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
server=ThreadingHTTPServer(('127.0.0.1',18886),FixtureHandler);server.content=Content();server.daemon_threads=True
print('Disposable reconnect check: http://127.0.0.1:18886/',flush=True)
try:server.serve_forever()
except KeyboardInterrupt:pass
finally:
    for timer in timers:timer.cancel();timer.join()
    host.close();server.server_close()
