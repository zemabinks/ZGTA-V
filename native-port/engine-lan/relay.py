#!/usr/bin/env python3
"""Explicit LAN/Tailscale WebSocket relay. No discovery, game or startup side effects.

Carries glue5 DATA datagrams; does not translate Mugoat snapshots. Launch only
for an explicit test or explicitly enabled managed service. All connections
and reservations end with this process.
"""
import argparse
import asyncio
import base64
from dataclasses import dataclass, field
import hashlib
import ipaddress
import json
import secrets
import signal
import struct
import time

PROTOCOL = 'zema-engine-lan/1'
BUILD = '8b0b5899ed'
NET = 0x0a4d0000
MAX_FRAME = 2048
TTL = 20
ORIGINS = {'http://127.0.0.1:18886', 'http://localhost:18886',
           'http://127.0.0.1:18887', 'http://localhost:18887'}
TAILSCALE_RANGE = ipaddress.IPv4Network('100.64.0.0/10')
LOCAL_RANGES = tuple(ipaddress.IPv4Network(value) for value in
                     ('127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12',
                      '192.168.0.0/16', '169.254.0.0/16'))


def bind_address(text, tailscale=False):
    """Select one literal local interface; never wildcard or public binding.

    --tailscale acknowledges an already assigned VPN address, not proof that
    Tailscale owns it. The operator must verify its interface and tailnet policy.
    No interface, route, credential or access policy is changed here.
    """
    address = ipaddress.IPv4Address(text)
    if str(address) != text:
        raise ValueError('Use a literal dotted-decimal IPv4 address')
    if tailscale:
        if address not in TAILSCALE_RANGE:
            raise ValueError('--tailscale requires the Mac Tailscale IPv4 in 100.64.0.0/10')
    elif not any(address in network for network in LOCAL_RANGES):
        raise ValueError('Use an explicit local IPv4; Tailscale addresses require --tailscale')
    return str(address)


def valid_ip(ip):
    return ip & 0xffff0000 == NET and ip & 255 not in (0, 255)


def datagram(data):
    if not isinstance(data, bytes) or not 16 <= len(data) <= MAX_FRAME or data[:4] != b'G5\x01\x03':
        raise ValueError('invalid engine datagram')
    source, src_port, destination, dst_port = struct.unpack('>IHIH', data[4:16])
    broadcast = destination == 0xffffffff or (destination & 0xffff0000 == NET and destination & 255 == 255)
    if not valid_ip(source) or not (valid_ip(destination) or broadcast) or not src_port or not dst_port:
        raise ValueError('invalid virtual address/port')
    return source, destination, broadcast


async def frame(reader):
    first, second = await reader.readexactly(2)
    opcode = first & 15
    if first & 0x70 or not first & 0x80 or not second & 0x80 or opcode not in (1, 2, 8, 9, 10):
        raise ValueError('unsupported WebSocket frame')
    length = second & 127
    if length == 126:
        length = struct.unpack('>H', await reader.readexactly(2))[0]
        if length < 126:
            raise ValueError('noncanonical WebSocket length')
    elif length == 127:
        raise ValueError('oversized WebSocket frame')
    if length > MAX_FRAME or (opcode >= 8 and length > 125) or (opcode == 8 and length == 1):
        raise ValueError('WebSocket frame limit')
    mask = await reader.readexactly(4)
    payload = await reader.readexactly(length)
    return opcode, bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))


def encode_frame(data, opcode):
    length = len(data)
    if length > MAX_FRAME:
        raise ValueError('outbound WebSocket frame limit')
    return bytes([0x80 | opcode]) + (bytes([length]) if length < 126 else b'\x7e' + struct.pack('>H', length)) + data


@dataclass(eq=False)
class Peer:
    room: str
    name: str
    vip: int
    resume: str
    writer: object = None
    generation: int = 0
    expires: float = 0
    queue: object = field(default_factory=lambda: asyncio.Queue(maxsize=128))
    sent: float = 0
    count: int = 0


class ResumeUnavailable(ValueError):
    pass


class AddressUnavailable(ValueError):
    pass


class Relay:
    def __init__(self, clock=time.monotonic, advertised_room=None):
        if advertised_room is not None and (not isinstance(advertised_room, str) or not advertised_room.strip() or len(advertised_room.encode()) > 64 or any(ord(c) < 32 or 127 <= ord(c) < 160 for c in advertised_room)):
            raise ValueError('Invalid advertised room')
        self.clock = clock
        self.advertised_room = advertised_room
        self.epoch = secrets.token_hex(8)
        self.health_id = secrets.token_hex(16)
        self.rooms = {}
        self.connections = set()
        self.closing = False

    def expire(self):
        now = self.clock()
        for room, peers in list(self.rooms.items()):
            for vip, peer in list(peers.items()):
                if peer.writer is None and now >= peer.expires:
                    del peers[vip]
            if not peers:
                del self.rooms[room]

    def catalog(self):
        self.expire()
        rows = [{'room':room,'players':sum(p.writer is not None for p in peers.values()),
                 'slots':len(peers),'capacity':32,
                 'player_names':[p.name for p in peers.values() if p.writer is not None]} for room,peers in self.rooms.items()]
        # An explicitly hosted default room stays joinable before the first
        # player and after the last reservation expires. Other rooms stay open.
        if self.advertised_room is not None and self.advertised_room not in self.rooms and len(rows) < 32:
            rows.insert(0, {'room':self.advertised_room,'players':0,'slots':0,'capacity':32,'player_names':[]})
        return rows

    def health(self):
        lobbies=self.catalog()
        # Keep the additive roster inside existing 16 KiB health clients even
        # at the 32-room / 32-player limits. Totals never depend on name budget.
        budget=4096
        for lobby in lobbies:
            names=lobby.get('player_names')
            if names is not None:
                size=len(json.dumps(names).encode())
                if size>budget:del lobby['player_names']
                else:budget-=size
        return {'service':'zgta-engine-lan','protocol':PROTOCOL,'build':BUILD,
                'instance':self.health_id,'peers':sum(p.writer is not None for ps in self.rooms.values() for p in ps.values()),
                'rooms':len(lobbies),'catalog_version':1,'lobbies':lobbies,'room_policy':'open'}

    def admit(self, message, writer):
        if self.closing:
            raise ValueError('relay stopping')
        self.expire()
        if not isinstance(message, dict) or set(message) - {'type', 'protocol', 'build', 'room', 'name', 'resume', 'rejoin'}:
            raise ValueError('invalid join')
        if (message.get('type') != 'join' or message.get('protocol') != PROTOCOL or message.get('build') != BUILD):
            raise ValueError('engine protocol/build mismatch')
        room, name = message.get('room'), message.get('name')
        for value, maximum in [(room, 64), (name, 48)]:
            if (not isinstance(value, str) or not value.strip() or len(value.encode()) > maximum
                    or any(ord(c) < 32 or 127 <= ord(c) < 160 for c in value)):
                raise ValueError('invalid room/name')
        token = message.get('resume')
        if token is not None and (not isinstance(token, str) or len(token) != 32
                                  or not token.isascii() or not all(c.isalnum() or c in '-_' for c in token)):
            raise ValueError('invalid resume')
        peers = self.rooms.get(room, {})
        recovery = message.get('rejoin')
        if 'rejoin' in message and ('resume' in message or not isinstance(recovery, dict)):
            raise ValueError('invalid recovery')
        if token:
            peer = next((p for p in peers.values() if secrets.compare_digest(p.resume, token)), None)
            if peer is None:
                raise ResumeUnavailable('session expired')
            if peer.writer is not None:
                peer.writer.close()
            peer.queue = asyncio.Queue(maxsize=128)
            peer.name = name
        else:
            if room not in self.rooms and len(self.rooms) >= 32:
                raise ValueError('room limit')
            # 32 local players per room; no dynamically growing peer table.
            if recovery is not None:
                vip = recovery.get('vip')
                if (set(recovery) != {'vip', 'epoch'} or recovery.get('epoch') != self.epoch
                        or type(vip) is not int or not NET | 1 <= vip <= NET | 32):
                    raise ValueError('invalid recovery')
                if vip in peers:
                    raise AddressUnavailable('original address is occupied or reserved')
            else:
                vip = next((NET | i for i in range(1, 33) if NET | i not in peers), None)
            if vip is None:
                raise ValueError('room full')
            peer = Peer(room, name, vip, secrets.token_urlsafe(24))
            self.rooms.setdefault(room, {})[vip] = peer
        peer.writer = writer
        peer.generation += 1
        peer.sent = self.clock(); peer.count = 0
        return peer, peer.generation

    def depart(self, peer, generation):
        if peer.generation == generation:
            peer.writer = None
            peer.expires = self.clock() + TTL
            peer.queue = asyncio.Queue(maxsize=128)

    def route(self, peer, generation, data):
        if self.closing or peer.writer is None or peer.generation != generation:
            raise ValueError('replaced connection')
        source, destination, broadcast = datagram(data)
        if source != peer.vip:
            raise ValueError('sender address mismatch')
        now = self.clock()
        if now - peer.sent >= 1:
            peer.sent = now; peer.count = 0
        peer.count += 1
        if peer.count > 4096:
            raise ValueError('datagram rate limit')
        for other in self.rooms[peer.room].values():
            if other is peer or other.writer is None or (not broadcast and other.vip != destination):
                continue
            try:
                other.queue.put_nowait((data, 2))
            except asyncio.QueueFull:
                # Drop this peer's connection; never grow memory or block the room.
                other.writer.close()

    async def send_loop(self, peer, generation, queue, writer):
        try:
            while peer.generation == generation:
                payload, opcode = await queue.get()
                writer.write(encode_frame(payload, opcode))
                await asyncio.wait_for(writer.drain(), 2)
        finally:
            writer.close()

    async def client(self, reader, writer):
        if len(self.connections) >= 256:
            writer.close()
            return
        self.connections.add(writer)
        peer = task = None; generation = 0
        try:
            raw = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 5)
            if len(raw) > 8192:
                raise ValueError('HTTP header limit')
            lines = raw.decode('ascii').split('\r\n')
            if lines[0] not in ('GET /engine-lan HTTP/1.1', 'GET /health HTTP/1.1'):
                raise ValueError('wrong endpoint')
            headers = {}
            for line in lines[1:]:
                if not line:
                    continue
                key, value = line.split(':', 1); key = key.lower()
                if key in headers:
                    raise ValueError('duplicate header')
                headers[key] = value.strip()
            if headers.get('origin') is not None and headers['origin'] not in ORIGINS:
                raise ValueError('invalid origin')
            if lines[0] == 'GET /health HTTP/1.1':
                data = json.dumps(self.health()).encode()
                writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: '+str(len(data)).encode()+b'\r\n\r\n'+data)
                await writer.drain()
                return
            key = headers.get('sec-websocket-key', '')
            if (len(base64.b64decode(key, validate=True)) != 16
                    or headers.get('sec-websocket-version') != '13'
                    or headers.get('upgrade', '').lower() != 'websocket'
                    or 'upgrade' not in {x.strip().lower() for x in headers.get('connection', '').split(',')}
                    or (headers.get('origin') is not None and headers['origin'] not in ORIGINS)):
                raise ValueError('invalid WebSocket handshake')
            accept = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
            writer.write(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ' + accept + b'\r\n\r\n')
            await writer.drain()
            opcode, payload = await asyncio.wait_for(frame(reader), 5)
            if opcode != 1:
                raise ValueError('join required')
            try:
                peer, generation = self.admit(json.loads(payload), writer)
            except ResumeUnavailable:
                response = {'type':'resume-unavailable', 'protocol':PROTOCOL, 'build':BUILD,
                            'epoch':self.epoch, 'recovery':'same-address-v1'}
                writer.write(encode_frame(json.dumps(response).encode(), 1)); await writer.drain()
                opcode, payload = await asyncio.wait_for(frame(reader), 5)
                if opcode != 1:
                    raise ValueError('recovery join required')
                try:
                    peer, generation = self.admit(json.loads(payload), writer)
                except AddressUnavailable:
                    writer.write(encode_frame(json.dumps({'type':'rejoin-unavailable', 'protocol':PROTOCOL, 'build':BUILD}).encode(), 1))
                    await writer.drain()
                    return
            joined = {'type': 'joined', 'protocol': PROTOCOL, 'build': BUILD, 'vip': peer.vip,
                      'epoch': self.epoch, 'resume': peer.resume}
            writer.write(encode_frame(json.dumps(joined).encode(), 1)); await writer.drain()
            task = asyncio.create_task(self.send_loop(peer, generation, peer.queue, writer))
            while peer.generation == generation:
                opcode, payload = await asyncio.wait_for(frame(reader), 30)
                if opcode == 8:
                    break
                if opcode == 2:
                    self.route(peer, generation, payload)
                elif opcode == 9:
                    peer.queue.put_nowait((payload, 10))
                elif opcode == 1 and payload == b'{"type":"ping"}':
                    peer.queue.put_nowait((b'{"type":"pong"}', 1))
                elif opcode != 10:
                    raise ValueError('unsupported message')
        except (ValueError, OSError, asyncio.TimeoutError, asyncio.IncompleteReadError,
                asyncio.LimitOverrunError, asyncio.QueueFull):
            pass
        finally:
            if task:
                task.cancel(); await asyncio.gather(task, return_exceptions=True)
            if peer:
                self.depart(peer, generation)
            self.connections.discard(writer); writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), 2)
            except (OSError, asyncio.TimeoutError):
                writer.transport.abort()

    async def close(self):
        self.closing = True
        writers = tuple(self.connections)
        for writer in writers:
            writer.close()
        if writers:
            try:
                await asyncio.wait_for(asyncio.gather(*(writer.wait_closed() for writer in writers), return_exceptions=True), 2)
            except asyncio.TimeoutError:
                for writer in writers:
                    writer.transport.abort()
        self.rooms.clear()


async def serve(address, port, duration, vpn_address=None, advertised_room=None):
    relay = Relay(advertised_room=advertised_room)
    server = await asyncio.start_server(relay.client, address, port, limit=8192)
    servers = [server]
    stopped = asyncio.Event(); loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stopped.set)
    print('ENGINE_LAN_RELAY_READY', address, server.sockets[0].getsockname()[1], flush=True)
    try:
        if vpn_address:
            try:
                vpn_server = await asyncio.start_server(relay.client, vpn_address, port, limit=8192)
                servers.append(vpn_server)
                print('ENGINE_LAN_VPN_READY', vpn_address, port, flush=True)
            except OSError as error:
                # Optional VPN loss must never take the working LAN listener down.
                print('ENGINE_LAN_VPN_UNAVAILABLE', vpn_address, error.errno, flush=True)
        if duration is None:
            await stopped.wait()
        else:
            await asyncio.wait_for(stopped.wait(), duration)
    except asyncio.TimeoutError:
        pass
    finally:
        for listener in servers:listener.close()
        for listener in servers:await listener.wait_closed()
        await relay.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--tailscale', action='store_true',
                        help='bind only the specified, already assigned Mac Tailscale IPv4; no VPN setup')
    parser.add_argument('--port', type=int, default=47540)
    parser.add_argument('--vpn-bind', help='add one already assigned Tailscale IPv4 to the same LAN relay; no VPN setup')
    parser.add_argument('--advertise-room', help='keep this explicitly hosted room listed when empty; does not restrict other rooms')
    lifetime = parser.add_mutually_exclusive_group()
    lifetime.add_argument('--duration', type=int, default=1800)
    lifetime.add_argument('--service', action='store_true', help='run until stopped; explicit managed-service mode without the test timer')
    args = parser.parse_args(argv)
    try:
        address = bind_address(args.bind, args.tailscale)
        if args.vpn_bind is not None and args.tailscale:raise ValueError('Use either a single --tailscale bind or LAN plus --vpn-bind')
        vpn_address = bind_address(args.vpn_bind, True) if args.vpn_bind is not None else None
    except ValueError as error:
        parser.error(str(error))
    if not 1024 <= args.port <= 65535 or not 60 <= args.duration <= 3600:
        parser.error('use port 1024–65535 and duration 60–3600')
    duration = None if args.service else args.duration
    advertised_room = args.advertise_room if args.advertise_room is not None else 'LOS-SANTOS' if args.service else None
    try:
        Relay(advertised_room=advertised_room)
    except ValueError as error:
        parser.error(str(error))
    if advertised_room is not None:
        asyncio.run(serve(address, args.port, duration, vpn_address, advertised_room=advertised_room))
    else:
        asyncio.run(serve(address, args.port, duration, vpn_address) if vpn_address else serve(address, args.port, duration))


if __name__ == '__main__':
    main()
