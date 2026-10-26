"""Private LAN relay keeper. Only supervises its own child, never a port/PID search."""
import ipaddress
import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import signal
import stat
import subprocess
import sys
import threading

PORT = 47540
RANGES = tuple(ipaddress.IPv4Network(s) for s in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','169.254.0.0/16'))
TAILSCALE_RANGE = ipaddress.IPv4Network('100.64.0.0/10')
TAILSCALE_CLIENT = Path('/Applications/Tailscale.app/Contents/MacOS/Tailscale')

def tailscale_ip(run=subprocess.run, client=TAILSCALE_CLIENT):
    """Read only the existing client's local status. Never configure a VPN."""
    try:
        info=client.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid not in (0,os.getuid()) or info.st_mode&0o022:return None
        # The macOS app binary selects CLI mode only with a terminal marker.
        # launchd has no TERM; set it for this read-only child, never globally.
        result=run([str(client),'status','--json','--peers=false'],capture_output=True,text=True,timeout=3,env=dict(os.environ,TERM='dumb'))
        if result.returncode or len(result.stdout)>131072:return None
        data=json.loads(result.stdout);node=data.get('Self')
        if data.get('BackendState')!='Running' or not isinstance(node,dict) or node.get('Online') is not True:return None
        for value in node.get('TailscaleIPs',[]):
            try:
                address=ipaddress.IPv4Address(value)
                if str(address)==value and address in TAILSCALE_RANGE:return value
            except (ValueError,TypeError):pass
    except (OSError,ValueError,AttributeError,TypeError,subprocess.TimeoutExpired):pass
    return None

def lan_ip(run=subprocess.run):
    interfaces = []
    try:
        route = run(['/sbin/route','-n','get','default'],capture_output=True,text=True,timeout=3)
        for line in route.stdout.splitlines():
            if line.strip().startswith('interface:'):
                value = line.split(':',1)[1].strip()
                if value.startswith('en') and value[2:].isdigit(): interfaces.append(value)
    except (OSError,subprocess.TimeoutExpired): pass
    for interface in dict.fromkeys(interfaces+['en0','en1']):
        try:
            result = run(['/usr/sbin/ipconfig','getifaddr',interface],capture_output=True,text=True,timeout=3)
            text = result.stdout.strip(); address = ipaddress.IPv4Address(text)
            if result.returncode == 0 and str(address) == text and any(address in r for r in RANGES): return text
        except (OSError,ValueError,subprocess.TimeoutExpired): pass
    return None

def stop_child(child):
    if child is not None and child.poll() is None:
        child.terminate()
        try: child.wait(timeout=4)
        except subprocess.TimeoutExpired:
            child.kill(); child.wait(timeout=2)

def publish_address(root, address, filename='relay-bind.json'):
    target = root/filename
    temporary = root/(filename+'.%d.new'%os.getpid())
    fd = os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'w') as f:
            json.dump({'address':address},f);f.flush();os.fsync(f.fileno())
        os.replace(temporary,target)
    finally:
        if temporary.exists():temporary.unlink()

class RelaySupervisor:
    """A failed address observation must not tear down a healthy child/session."""
    def __init__(self, root, log, spawn=None, stop=stop_child):
        self.root, self.log = root, log
        self.spawn = spawn or self.start_child
        self.stop = stop
        self.child = None
        self.address = None
        self.pending_address = None
        self.waiting = False
        self.probe_missing = False

    def start_child(self, address):
        vpn_address=tailscale_ip()
        args=[sys.executable,'-B','-u',str(self.root/'relay.py'),'--bind',address,'--port',str(PORT),'--service']
        if vpn_address:args+=['--vpn-bind',vpn_address]
        child = subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        def drain(process):
            for line in process.stdout:self.log.info('engine: %s',line.rstrip()[:500])
        threading.Thread(target=drain,args=(child,),daemon=True).start()
        try:
            publish_address(self.root,address)
            publish_address(self.root,vpn_address,'relay-vpn-bind.json')
        except OSError as error:self.log.warning('Could not publish relay bind address: %s',error)
        return child

    def update(self, selected):
        if self.child is not None:
            code = self.child.poll()
            if code is not None:
                self.log.info('Relay exited (%s); recovering when a private address is available',code)
                self.child = None
                self.pending_address = None
            elif selected is None:
                # ipconfig/route can fail briefly, including during CPU load or
                # Wi-Fi changes. The existing private bind remains safe. Keep
                # its epoch, reservations and connections instead of restarting.
                self.pending_address = None
                if not self.probe_missing:
                    self.log.info('LAN address probe unavailable; keeping active relay and sessions')
                self.probe_missing = True
                return
            elif selected == self.address:
                if self.probe_missing:self.log.info('LAN address probe restored; active relay unchanged')
                self.probe_missing = False
                self.pending_address = None
                return
            elif selected != self.pending_address:
                # A positive change needs two consecutive observations. A missing
                # observation or a return to the current address cancels it.
                self.pending_address = selected
                self.log.info('Observed a different private LAN address; awaiting confirmation')
                return
            else:
                self.stop(self.child)
                self.child = None
                self.log.info('Confirmed private LAN address change; restarting relay')
        if self.child is None:
            if selected:
                self.child = self.spawn(selected)
                self.address = selected
                self.pending_address = None
                self.probe_missing = self.waiting = False
                self.log.info('Relay enabled at ws://%s:%s/engine-lan',selected,PORT)
            elif not self.waiting:
                self.log.info('Enabled; waiting for a private Ethernet/Wi-Fi address')
                self.waiting = True

    def close(self):
        self.stop(self.child)
        self.child = None


def main():
    os.umask(0o077)
    root = Path(__file__).resolve().parent
    handler = RotatingFileHandler(root/'relay-service.log',maxBytes=262144,backupCount=2)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    log = logging.getLogger('zgta-relay');log.setLevel(logging.INFO);log.addHandler(handler)
    stopped = threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,lambda *_: stopped.set())
    supervisor = RelaySupervisor(root,log)
    try:
        while not stopped.is_set():
            supervisor.update(lan_ip())
            stopped.wait(5)
    finally:
        supervisor.close();log.info('Relay stopped by its owner')

if __name__ == '__main__': main()
