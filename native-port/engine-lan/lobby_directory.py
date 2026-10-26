"""Read-only checks of explicitly supplied private ZGTA hosts; no subnet scanning.

No redirects, DNS names, credentials, proxy environment or arbitrary HTTP paths.
The HTTP read has one total deadline and strict header/body/schema limits.
"""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import json
import re
import socket
import threading
import time
import relay


def endpoint(value):
    if not isinstance(value,str) or len(value)>128:raise ValueError('Enter a private host address.')
    match=re.fullmatch(r'ws://([0-9.]+)(?::([1-9][0-9]{0,4}))?/engine-lan',value)
    if not match:raise ValueError('Use a Wi-Fi or Tailscale IPv4 address, not a website.')
    ip=ipaddress.IPv4Address(match[1]);relay.bind_address(match[1],tailscale=ip in relay.TAILSCALE_RANGE)
    port=int(match[2] or 80)
    if not 1<=port<=65535:raise ValueError('Invalid host port.')
    return str(ip),port


def checked_health(data):
    if not isinstance(data,dict) or data.get('service')!='zgta-engine-lan':raise ValueError('This address is not a ZGTA V host.')
    if data.get('protocol')!=relay.PROTOCOL or data.get('build')!=relay.BUILD:return {'state':'incompatible','message':'This host uses a different game version.'}
    if not isinstance(data.get('instance'),str) or not re.fullmatch('[a-f0-9]{32}',data['instance']):raise ValueError('Invalid host identity.')
    for key,max_value in [('peers',1024),('rooms',32)]:
        if type(data.get(key)) is not int or not 0<=data[key]<=max_value:raise ValueError('Invalid host counts.')
    result={'state':'online','players':data['peers'],'rooms':data['rooms'],'lobbies':[],'catalog':False,'room_policy':data.get('room_policy') if data.get('room_policy') in ('open','hosted') else 'unknown'}
    if data.get('catalog_version')==1 and type(data['catalog_version']) is int:
        lobbies=data.get('lobbies')
        if not isinstance(lobbies,list) or len(lobbies)>32:raise ValueError('Invalid lobby list.')
        seen=set()
        for entry in lobbies:
            if not isinstance(entry,dict):raise ValueError('Invalid lobby.')
            room=entry.get('room')
            if not isinstance(room,str) or not room.strip() or len(room.encode())>64 or any(ord(c)<32 or 127<=ord(c)<160 for c in room) or room in seen:raise ValueError('Invalid lobby room.')
            players,slots,capacity=(entry.get(k) for k in ('players','slots','capacity'))
            if any(type(n) is not int for n in (players,slots,capacity)) or not 0<=players<=slots<=capacity<=32 or capacity<1:raise ValueError('Invalid lobby capacity.')
            seen.add(room);result['lobbies'].append({'room':room,'players':players,'slots':slots,'capacity':capacity})
        result['catalog']=True
    return result


def read_health(address,timeout=2.5):
    ip,port=endpoint(address);start=time.monotonic();deadline=start+timeout
    with socket.create_connection((ip,port),timeout=timeout) as stream:
        def receive():
            left=deadline-time.monotonic()
            if left<=0:raise TimeoutError('Host check timed out.')
            stream.settimeout(left);part=stream.recv(4096)
            if not part:raise ValueError('Host closed the health response.')
            return part
        stream.settimeout(max(.01,deadline-time.monotonic()))
        stream.sendall(('GET /health HTTP/1.1\r\nHost: %s:%d\r\nConnection: close\r\n\r\n'%(ip,port)).encode('ascii'))
        raw=b''
        while b'\r\n\r\n' not in raw:
            raw+=receive()
            if len(raw)>24576:raise ValueError('Host response is too large.')
        header,body=raw.split(b'\r\n\r\n',1)
        if len(header)>8192:raise ValueError('Host header is too large.')
        lines=header.decode('ascii').split('\r\n')
        if not re.fullmatch(r'HTTP/1\.[01] 200(?: .*)?',lines[0]):raise ValueError('The host did not accept its health check.')
        headers={}
        for line in lines[1:]:
            key,value=line.split(':',1);key=key.lower()
            if key in headers:raise ValueError('Duplicate health header.')
            headers[key]=value.strip()
        length=headers.get('content-length','')
        if 'transfer-encoding' in headers or not length.isdecimal() or not 0<int(length)<=16384 or not headers.get('content-type','').lower().startswith('application/json'):raise ValueError('Invalid health response.')
        length=int(length)
        while len(body)<length:body+=receive()
        if len(body)!=length:raise ValueError('Invalid health response length.')
        result=checked_health(json.loads(body.decode('utf8')))
        return dict(result,latency_ms=max(0,round((time.monotonic()-start)*1000)),address=address)


class LobbyDirectory:
    def __init__(self):
        self.pool=ThreadPoolExecutor(max_workers=4,thread_name_prefix='zgta-lobby-check')
        self.lock=threading.Lock();self.cache=OrderedDict();self.closed=False
    def _probe(self,address):
        with self.lock:
            found=self.cache.get(address)
            if found and time.monotonic()-found[0]<3:return dict(found[1])
        try:result=read_health(address)
        except (OSError,ValueError,TypeError,UnicodeError):result={'address':address,'state':'offline','message':'Host unavailable. Check that the game/relay is open and both devices use the same Wi-Fi or Tailscale network.'}
        with self.lock:
            self.cache[address]=(time.monotonic(),result);self.cache.move_to_end(address)
            while len(self.cache)>32:self.cache.popitem(last=False)
        return result
    def probe(self,addresses):
        if not isinstance(addresses,list) or len(addresses)>12:raise ValueError('Check at most 12 hosts at a time.')
        for address in addresses:endpoint(address)
        if self.closed:raise ValueError('The lobby browser is closing.')
        return {'hosts':list(self.pool.map(self._probe,dict.fromkeys(addresses))),'checked_at':int(time.time()*1000)}
    def close(self):
        self.closed=True;self.pool.shutdown(wait=True)
