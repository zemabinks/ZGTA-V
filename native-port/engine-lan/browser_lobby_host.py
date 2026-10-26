"""Explicit lobby hosting owned by the local browser launcher, not ZRemote's job.

No shell commands, VPN setup, public binds or pre-existing process termination.
The HTTP launcher stays loopback-only; the relay binds only chosen private IPs.
"""
import asyncio
import ipaddress
import secrets
import socket
import threading
import sys
from pathlib import Path
import relay
from lobby_discovery import Announcement


def addresses():
    found={'lan':None,'remote':None}
    # UDP connect only asks the OS which local address its route would use.
    # No payload is sent, hostname resolved, or remote server contacted.
    for kind,target in [('lan','192.0.2.1'),('remote','100.100.100.100')]:
        try:
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as probe:
                probe.connect((target,9));value=probe.getsockname()[0]
            address=ipaddress.IPv4Address(value)
            if kind=='remote' and address in relay.TAILSCALE_RANGE:found[kind]=value
            if kind=='lan' and any(address in r for r in relay.LOCAL_RANGES) and not value.startswith('127.'):found[kind]=value
        except OSError:pass
    if sys.platform=='darwin':
        import importlib.util
        spec=importlib.util.spec_from_file_location('zgta_host_address_reader',Path(__file__).parent/'relay-service/service_runner.py')
        reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
        found['lan']=reader.lan_ip() or found['lan'];found['remote']=reader.tailscale_ip() or found['remote']
    return found


class RoomRelay(relay.Relay):
    def __init__(self,room):super().__init__();self.hosted_room=room
    def health(self):
        result=super().health();result['room_policy']='hosted';result['rooms']=1;return result
    def catalog(self):
        rows=super().catalog()
        return [dict(rows[0],capacity=8)] if rows else [{'room':self.hosted_room,'players':0,'slots':0,'capacity':8}]
    def admit(self,message,writer):
        if not isinstance(message,dict) or message.get('room')!=self.hosted_room:raise ValueError('Choose the hosted room')
        self.expire()
        recovery=message.get('rejoin')
        if isinstance(recovery,dict) and type(recovery.get('vip')) is int and not relay.NET | 1 <= recovery['vip'] <= relay.NET | 8:
            raise ValueError('Phone-compatible address must be in this lobby’s eight slots')
        if not message.get('resume') and len(self.rooms.get(self.hosted_room,{}))>=8:raise ValueError('Phone-compatible lobby is full')
        return super().admit(message,writer)


class BrowserLobbyHost:
    def __init__(self,discover=addresses,ports=(47540,47541,47542,47543)):
        self.discover,self.ports=discover,ports
        self.lock=threading.RLock();self.loop=None;self.thread=None
        self.engine=None;self.listeners=[];self.identifier=None;self.info=None
        self.restart_spec=None;self.last_port=None;self.announcement=Announcement()
    def _call(self,coroutine,timeout=8):return asyncio.run_coroutine_threadsafe(coroutine,self.loop).result(timeout)
    async def _status(self):
        if not self.engine:
            if self.restart_spec:
                return dict(self.restart_spec['info'],running=False,owned=True,can_restart=True,id=self.restart_spec['id'],peers=0)
            return {'running':False,'owned':False}
        self.engine.expire()
        return dict(self.info, running=True,owned=True,id=self.identifier,
                    peers=sum(p.writer is not None for ps in self.engine.rooms.values() for p in ps.values()))
    def status(self):
        with self.lock:
            return self._call(self._status()) if self.loop else {'running':False,'owned':False}
    async def _start(self,room,connection,selected,restart=None):
        if self.engine:
            if self.info['room']!=room or self.info['connection']!=connection:raise ValueError('Stop your current hosted lobby before creating another.')
            return await self._status()
        engine=RoomRelay(room)
        required=['127.0.0.1']
        if connection=='LAN' and selected['lan']:required.append(selected['lan'])
        # Remote can work without a LAN when a real VPN address is assigned.
        if connection=='Remote' and not selected['remote']:raise ValueError('Connect Tailscale on this computer before hosting Remote.')
        if connection=='LAN' and not selected['lan']:raise ValueError('Connect this computer to Wi-Fi/Ethernet before hosting LAN.')
        if connection=='Remote' and selected['remote']:required.append(selected['remote'])
        listeners=[];port=None
        candidates=[restart['port']] if restart else list(dict.fromkeys(([self.last_port] if self.last_port else [])+list(self.ports)))
        for candidate in candidates:
            try:
                for ip in dict.fromkeys(required):
                    # All values were discovered locally and validated again here.
                    relay.bind_address(ip,tailscale=ipaddress.IPv4Address(ip) in relay.TAILSCALE_RANGE)
                    listeners.append(await asyncio.start_server(engine.client,ip,candidate,limit=8192))
                port=candidate;break
            except OSError:
                for listener in listeners:listener.close();await listener.wait_closed()
                listeners=[]
        if port is None:raise ValueError('The previous lobby port is busy. Retry shortly; no existing server was stopped.' if restart else 'No private lobby port was available. Existing servers were left running.')
        self.engine,self.listeners,self.identifier=engine,listeners,restart['id'] if restart else secrets.token_hex(16)
        self.last_port=port
        self.info={'room':room,'connection':connection,'join':'ws://127.0.0.1:%d/engine-lan'%port,
                   'lan':'ws://%s:%d/engine-lan'%(selected['lan'],port) if connection=='LAN' and selected['lan'] else '',
                   'remote':'ws://%s:%d/engine-lan'%(selected['remote'],port) if connection=='Remote' and selected['remote'] else '',
                   'availability':'While the local launcher is running and this computer is awake'}
        self.restart_spec=None
        if connection=='LAN' and not selected['lan'].startswith('127.'):self.announcement.start(room,port)
        return await self._status()
    def start(self,room,connection):
        if not isinstance(room,str) or not room.strip() or len(room.encode())>64 or any(ord(c)<32 or 127<=ord(c)<160 for c in room):raise ValueError('Enter a room of 1–64 bytes without control characters.')
        if connection not in ('LAN','Remote'):raise ValueError('Choose LAN or Remote.')
        with self.lock:
            if not self.loop:
                self.loop=asyncio.new_event_loop();self.thread=threading.Thread(target=self.loop.run_forever,daemon=True,name='zgta-browser-host');self.thread.start()
            selected=self.discover()
            for key,value in selected.items():
                if value is not None:relay.bind_address(value,tailscale=key=='remote')
            return self._call(self._start(room,connection,selected))
    async def _stop(self):
        self.announcement.stop()
        if self.engine:
            self.restart_spec={'id':self.identifier,'info':dict(self.info),'port':self.last_port}
        for listener in self.listeners:listener.close()
        for listener in self.listeners:await listener.wait_closed()
        if self.engine:await self.engine.close()
        pending=[task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
        for task in pending:task.cancel()
        if pending:await asyncio.gather(*pending,return_exceptions=True)
        self.listeners=[];self.engine=None;self.info=None;self.identifier=None
        return await self._status()
    def stop(self,identifier):
        with self.lock:
            if not self.loop:return {'running':False,'owned':False}
            owned=self.identifier or (self.restart_spec or {}).get('id')
            if not isinstance(identifier,str) or not owned or not secrets.compare_digest(identifier,owned):raise ValueError('Only this launcher’s hosted lobby can be stopped.')
            return self._call(self._stop())
    def restart(self,identifier):
        with self.lock:
            if not isinstance(identifier,str):raise ValueError('Choose this launcher’s hosted lobby.')
            if self.engine:
                if not secrets.compare_digest(identifier,self.identifier):raise ValueError('Another hosted lobby is active.')
                return self._call(self._status())
            spec=self.restart_spec
            if not self.loop or not spec or not secrets.compare_digest(identifier,spec['id']):raise ValueError('This stopped lobby is no longer available. Start hosting from the launcher.')
            selected=self.discover();info=spec['info'];key='lan' if info['connection']=='LAN' else 'remote'
            # Keep the shared address as well as the port. Do not silently move
            # an existing game's lobby when its private network changes.
            expected='ws://%s:%d/engine-lan'%(selected.get(key),spec['port'])
            if expected!=info[key]:raise ValueError('The hosting network changed. Restore the previous Wi-Fi/VPN address before restarting this lobby.')
            for k,value in selected.items():
                if value is not None:relay.bind_address(value,tailscale=k=='remote')
            return self._call(self._start(info['room'],info['connection'],selected,restart=spec))
    def close(self):
        with self.lock:
            if not self.loop:return
            self._call(self._stop());self.loop.call_soon_threadsafe(self.loop.stop);self.thread.join(timeout=3)
            self.loop.close();self.loop=None;self.thread=None
            self.restart_spec=None
