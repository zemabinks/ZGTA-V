"""Bounded macOS Bonjour discovery/advertising using its existing system tool.

Only _zgtav._tcp on local. is browsed. Resolved literal private IPv4s must still
pass a real health check before becoming joinable. No subnet or internet scan.
"""
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import os
from pathlib import Path
import re
import selectors
import subprocess
import sys
import time
import relay
TOOL=Path('/usr/bin/dns-sd')
TYPE='_zgtav._tcp'


def available():return sys.platform=='darwin' and TOOL.is_file()


def capture(args,timeout):
    process=subprocess.Popen([str(TOOL),*args],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    data=bytearray();deadline=time.monotonic()+timeout
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout,selectors.EVENT_READ)
            while len(data)<65536 and time.monotonic()<deadline:
                if not selector.select(max(0,deadline-time.monotonic())):break
                part=os.read(process.stdout.fileno(),min(4096,65536-len(data)))
                if not part:break
                data.extend(part)
    finally:
        if process.poll() is None:process.terminate()
        try:process.wait(timeout=1)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=1)
        process.stdout.close()
    return data.decode('utf8',errors='replace')


def instances(text):
    result=[]
    for line in text.splitlines():
        m=re.search(r'\bAdd\s+\d+\s+\d+\s+local\.\s+_zgtav\._tcp\.\s+(.+)$',line)
        if m and 0<len(m[1].encode())<=63 and m[1] not in result:result.append(m[1])
    return result[:4]


def resolve(name):
    text=capture(['-L',name,TYPE,'local.'],1.2)
    m=re.search(r'can be reached at ([A-Za-z0-9._-]+\.local\.?):([1-9][0-9]{0,4})\b',text)
    if not m or int(m[2])>65535:return []
    addresses=capture(['-G','v4',m[1]],1.2);found=[]
    for candidate in re.findall(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])',addresses):
        try:
            ip=ipaddress.IPv4Address(candidate)
            if ip in relay.TAILSCALE_RANGE or candidate.startswith('127.'):continue
            relay.bind_address(candidate)
            endpoint='ws://%s:%s/engine-lan'%(candidate,m[2])
            if endpoint not in found:found.append(endpoint)
        except ValueError:pass
    return found[:2]


def discover():
    if not available():return {'available':False,'addresses':[]}
    try:
        names=instances(capture(['-B',TYPE,'local.'],2))
        with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(resolve,names))
        return {'available':True,'addresses':list(dict.fromkeys(a for row in rows for a in row))[:8]}
    except OSError:return {'available':False,'addresses':[]}


class Announcement:
    def __init__(self):self.process=None
    def start(self,room,port):
        self.stop()
        if not available():return
        name=('ZGTA V · '+room).encode()[:63].decode('utf8',errors='ignore')
        try:self.process=subprocess.Popen([str(TOOL),'-R',name,TYPE,'local.',str(port),'protocol='+relay.PROTOCOL,'build='+relay.BUILD],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        except OSError:self.process=None
    def stop(self):
        process,self.process=self.process,None
        if process is None:return
        if process.poll() is None:process.terminate()
        try:process.wait(timeout=1)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=1)
