"""ZGTA V's user LaunchAgent. Explicit on/off only; no privileged operations."""
import contextlib
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import plistlib
import stat
import subprocess
import sys
import time
import urllib.request
from service_runner import lan_ip, RANGES, TAILSCALE_RANGE

LABEL = 'com.zema.zgtav.engine-lan-relay'
ROOT = Path.home()/'Library/Application Support/ZRemote Controller/Games/ZGTAEngineLAN'
AGENT = Path.home()/'Library/LaunchAgents'/(LABEL+'.plist')
SOURCE = Path(__file__).resolve().parent
RUNNER = ROOT/'service_runner.py'
PYTHON = '/usr/bin/python3'

def command(args,timeout=8):
    return subprocess.run(args,capture_output=True,text=True,timeout=timeout,check=False)

def no_links(path):
    for p in (path,*path.parents):
        if p.is_symlink(): raise RuntimeError('Symlink path refused: '+str(p))

def regular(path,private=False):
    no_links(path); s=path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode & (0o077 if private else 0o022):
        raise RuntimeError('File ownership/permissions refused: '+str(path))

def directory(path,private=False):
    no_links(path)
    if not path.exists(): path.mkdir(parents=True,mode=0o700)
    s=path.stat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode & (0o077 if private else 0o022):
        raise RuntimeError('Directory ownership/permissions refused: '+str(path))

def target(): return 'gui/%d/%s'%(os.getuid(),LABEL)

def loaded():
    result=command(['/bin/launchctl','print',target()],5)
    if result.returncode!=0:return False
    if str(RUNNER) not in result.stdout:raise RuntimeError('Another job uses the relay label; refused')
    return True

def agent_data():
    return {'Label':LABEL,'ProgramArguments':[PYTHON,'-B','-u',str(RUNNER)],'RunAtLoad':True,
            'KeepAlive':True,'ThrottleInterval':10,'ExitTimeOut':6,'ProcessType':'Background',
            'WorkingDirectory':str(ROOT),'StandardOutPath':str(ROOT/'launchd.log'),
            'StandardErrorPath':str(ROOT/'launchd-error.log')}

def verify_agent():
    no_links(AGENT)
    if AGENT.exists():
        regular(AGENT,True)
        with AGENT.open('rb') as f:data=plistlib.load(f)
        if data!=agent_data():raise RuntimeError('Existing relay agent differs; refused to replace or remove it')

def published_address(vpn=False):
    path=ROOT/('relay-vpn-bind.json' if vpn else 'relay-bind.json');no_links(path)
    if not path.exists():return None
    regular(path,True)
    if path.stat().st_size>512:raise RuntimeError('Invalid relay bind record')
    data=json.loads(path.read_text())
    if not isinstance(data,dict) or set(data)!={'address'}:raise RuntimeError('Invalid relay bind record')
    if vpn and data['address'] is None:return None
    address=ipaddress.IPv4Address(data['address'])
    ranges=(TAILSCALE_RANGE,) if vpn else RANGES
    if str(address)!=data['address'] or not any(address in network for network in ranges):raise RuntimeError('Invalid private relay bind address')
    return str(address)

def checked_catalog(health):
    """Optional catalog is never inferred from legacy aggregate counts."""
    if type(health.get('catalog_version')) is not int or health['catalog_version']!=1:return None
    rows=health.get('lobbies')
    if not isinstance(rows,list) or len(rows)>32:return None
    found=[];seen=set()
    for row in rows:
        if not isinstance(row,dict):return None
        room=row.get('room');players=row.get('players');slots=row.get('slots');capacity=row.get('capacity')
        if not isinstance(room,str) or not room.strip() or len(room.encode())>64 or any(ord(c)<32 or 127<=ord(c)<160 for c in room) or room in seen:return None
        if any(type(n) is not int for n in (players,slots,capacity)) or not 0<=players<=slots<=capacity<=32 or capacity<1:return None
        names=row.get('player_names')
        if names is not None and (not isinstance(names,list) or len(names)!=players or any(not isinstance(n,str) or not n.strip() or len(n.encode())>48 or any(ord(c)<32 or 127<=ord(c)<160 for c in n) for n in names)):return None
        seen.add(room);found.append(dict(room=room,players=players,slots=slots,capacity=capacity,player_names=names))
    return found


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def health_at(ip,port=47540):
    if not ip:return {}
    try:
        # Only caller-selected owned bind records or fixed loopback are accepted.
        address=ipaddress.IPv4Address(ip)
        if str(address)!=ip or not any(address in n for n in (*RANGES,TAILSCALE_RANGE,ipaddress.IPv4Network('127.0.0.0/8'))):return {}
        if type(port) is not int or not 1<=port<=65535:return {}
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        with opener.open('http://%s:%d/health'%(ip,port),timeout=1.25) as r:raw=r.read(131073)
        if len(raw)>131072:return {}
        data=json.loads(raw)
        if not isinstance(data,dict):return {}
        if data.get('service')=='zgta-engine-lan' and data.get('protocol')=='zema-engine-lan/1' and data.get('build')=='8b0b5899ed' and all(type(data.get(k)) is int and 0<=data[k]<=limit for k,limit in [('peers',1024),('rooms',32)]):return data
    except (OSError,ValueError):pass
    return {}


def browser_host_status():
    """Observe the independent browser-owned host; never start/stop it here."""
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        request=urllib.request.Request('http://127.0.0.1:18887/zema-lab/host/status',data=b'{}',headers={'Content-Type':'application/json','X-Zema-Lab':'1'})
        with opener.open(request,timeout=1.25) as response:raw=response.read(4097)
        if len(raw)>4096:return None
        data=json.loads(raw)
        if data.get('running') is not True or data.get('owned') is not True:return None
        from urllib.parse import urlsplit
        url=urlsplit(data.get('join',''))
        if url.scheme!='ws' or url.hostname!='127.0.0.1' or url.username or url.password or url.path!='/engine-lan' or url.query or url.fragment:return None
        health=health_at('127.0.0.1',url.port)
        if not health:return None
        address=data.get('remote') or data.get('lan') or data['join']
        return dict(running=True,address=address,peers=health['peers'],rooms=health['rooms'],lobbies=checked_catalog(health))
    except (OSError,ValueError,TypeError,AttributeError):return None


def status():
    no_links(ROOT);verify_agent();active=loaded();ip=(published_address() if active else None) or lan_ip();health=health_at(ip)
    vpn_ip=published_address(True) if active else None;vpn_health=health_at(vpn_ip)
    identity=health.get('instance')
    vpn_running=bool(active and isinstance(identity,str) and len(identity)==32 and vpn_health.get('instance')==identity)
    return {'enabled':AGENT.exists(),'agent_loaded':active,'running':bool(active and health),
            'address':'ws://%s:47540/engine-lan'%ip if ip else '', 'room':'LOS-SANTOS',
            'vpn_address':'ws://%s:47540/engine-lan'%vpn_ip if vpn_ip else '', 'vpn_running':vpn_running,
            'peers':health.get('peers',0),'rooms':health.get('rooms',0),
            'lobbies':checked_catalog(health),'browser_host':browser_host_status(),
            'availability':'While this Mac is awake and the owner is logged in',
            'log_directory':str(ROOT)}

def atomic(path,data):
    no_links(path)
    if path.exists():regular(path,True)
    temp=path.with_name(path.name+'.new')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()

@contextlib.contextmanager
def locked():
    directory(ROOT,True);path=ROOT/'control.lock';no_links(path)
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        regular(path,True);end=time.monotonic()+8
        while True:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>=end:raise RuntimeError('Another relay control action is still running')
                time.sleep(.1)
        yield
    finally:os.close(fd)

def start():
    with locked():
        verify_agent()
        if loaded():
            if not AGENT.exists():raise RuntimeError('The previous relay is still stopping. Retry Relay On shortly.')
            return 'Relay is enabled; '+('online.' if status()['running'] else 'waiting for Wi-Fi or recovering. Check Status shortly.')
        port=command(['/usr/sbin/lsof','-nP','-iTCP:47540','-sTCP:LISTEN'],5)
        if port.returncode!=1:raise RuntimeError('Port 47540 is occupied or could not be checked. No existing process was stopped.')
        regular(SOURCE/'payload-sha256.json')
        hashes=json.loads((SOURCE/'payload-sha256.json').read_text())
        if set(hashes)!={'relay.py','service_runner.py'}:raise RuntimeError('Unexpected relay package manifest')
        payload={}
        for name,want in hashes.items():
            p=SOURCE/name;regular(p);data=p.read_bytes()
            if hashlib.sha256(data).hexdigest()!=want:raise RuntimeError('Relay package checksum failed: '+name)
            payload[name]=data
        for name,data in payload.items():atomic(ROOT/name,data)
        directory(AGENT.parent);atomic(AGENT,plistlib.dumps(agent_data()))
        result=command(['/bin/launchctl','bootstrap','gui/%d'%os.getuid(),str(AGENT)])
        if result.returncode:raise RuntimeError('Relay enable failed: '+result.stderr.strip()[:300])
        for _ in range(20):
            if status()['running']:return 'Relay on. No one-hour timeout; starts at login and recovers after a crash.'
            time.sleep(.3)
        return 'Relay enabled. Waiting for a private LAN address or startup; use Check Status.'

def stop():
    with locked():
        verify_agent();active=loaded()
        # Persist OFF before removing the running job, including at next login.
        if AGENT.exists():AGENT.unlink()
        if active:
            result=command(['/bin/launchctl','bootout',target()])
            if result.returncode:raise RuntimeError('Auto-start disabled, but running relay could not be stopped: '+result.stderr.strip()[:300])
            end=time.monotonic()+8
            while loaded():
                if time.monotonic()>=end:raise RuntimeError('Auto-start disabled; relay shutdown is still pending. Check Status shortly.')
                time.sleep(.1)
        return 'Relay off. Login auto-start is disabled. Browser hosting and other ZRemote services were not stopped.'

def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    if len(args)!=1 or args[0] not in ('start','stop','status','logs'):raise ValueError('Choose start, stop, status or logs')
    action=args[0];message=start() if action=='start' else stop() if action=='stop' else 'Relay status checked.'
    result={'ok':True,'message':message,'status':status()}
    if action=='logs':
        path=ROOT/'relay-service.log'
        if path.exists():
            regular(path)
            with path.open('rb') as f:f.seek(max(0,path.stat().st_size-12000));result['logs']=f.read().decode('utf-8',errors='replace')
    return result

if __name__=='__main__':
    try:print(json.dumps(main(),indent=2))
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
        print(json.dumps({'ok':False,'message':str(error)}));sys.exit(1)
