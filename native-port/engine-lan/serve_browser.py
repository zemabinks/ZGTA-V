#!/usr/bin/env python3
"""Read-only game mirror with private lab imports on loopback. No auto-launch."""
import argparse
from collections import deque, OrderedDict
import gzip
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import mimetypes
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import unquote, urlsplit, parse_qs

ROOT=Path(__file__).resolve().parent
INDEX_SHA='ea61ad05772c2bd2409304bdb80520abf5c50723a95dccc6bcc185c367a3105b'
BUILD='/b/8b0b5899ed/'
SIZES={3600:3,2500:4,150:12,80:12,40:16}


def overlay(data):
    """Same fixed-length transaction as BroadcastOverlay.c, never disk writes."""
    if len(data)>16*1024*1024 or b'\0' in data:raise ValueError('Invalid gameconfig')
    start=data.index(b'<PlayerBroadcastData>');end=data.index(b'</PlayerBroadcastData>',start)
    changed=bytearray(data)
    for size,count in SIZES.items():
        tag=('<SizeOfData value="%d"/>'%size).encode();item=data.index(tag,start,end)
        if data.find(tag,item+len(tag),end)>=0:raise ValueError('Duplicate broadcast record')
        close=data.index(b'</Item>',item,end);field=data.index(b'<NumInstances value="',item,close);digits=field+21;quote=data.index(b'"',digits,close);old=data[digits:quote]
        if not old or len(old)>9 or not old.isdigit():raise ValueError('Invalid broadcast count')
        if int(old)>=count:continue
        value=str(count).encode();delta=len(value)-len(old)
        if delta<0 or data[field-delta:field]!=b'\t'*delta:raise ValueError('Broadcast width changed')
        changed[field-delta:quote]=data[field:digits]+value
    if len(changed)!=len(data):raise ValueError('Broadcast length changed')
    return bytes(changed)


def once(text,before,after):
    if text.count(before)!=1:raise ValueError('Reviewed launcher anchor changed')
    return text.replace(before,after)


def index(data,mode='lan',prefix=None,engine_sha=None,lease=None,vehicle_packs=None):
    if hashlib.sha256(data).hexdigest()!=INDEX_SHA:raise ValueError('Reviewed launcher source changed')
    if mode not in ('lan','story','sandbox'):raise ValueError('Unknown launch mode')
    if prefix is not None and not re.fullmatch(r'/session/[a-f0-9]{32}',prefix):raise ValueError('Unsafe launch namespace')
    if engine_sha is not None and not re.fullmatch('[a-f0-9]{64}',engine_sha):raise ValueError('Unsafe engine hash')
    if lease is not None and not re.fullmatch('[a-f0-9]{32}',lease):raise ValueError('Unsafe launch lease')
    scripts=['session-restart.js','launch-settings.js','browser-performance.js','browser-features.js','vehicle-catalog.js','browser-trainer.js','vehicle-ui.js','controller.js','runtime.js','browser-mods-ui.js','trainer-ui.js','performance-run.js']
    if mode=='lan':scripts+=['connection-ui.js','entry.js','lan-loading.js']
    inject='\n<link rel="icon" type="image/svg+xml" href="/zema-lab/zplay-gta-green.svg"><link rel="icon" type="image/png" sizes="32x32" href="/zema-lab/zplay-gta-green-32.png"><link rel="apple-touch-icon" href="/zema-lab/zplay-gta-green-180.png"><meta name="theme-color" content="#050605">'
    inject+='\n<style>html,body{background:#050605!important;color:#f4f6f2}button,a{accent-color:#78b843}button:focus-visible,a:focus-visible{outline:3px solid #78b843;outline-offset:3px}</style>'
    inject+='\n<script src="/b/8b0b5899ed/engine-lan-browser.js"></script>'+''.join('\n<script src="/zema-lab/'+name+'"></script>' for name in scripts)
    inject+='\n<script>window.ZemaBenchmarkEngine='+json.dumps(engine_sha)+';</script>'
    inject+='\n<script>window.ZemaLaunchLease='+json.dumps(lease)+';</script>'
    # Only vehicle names from this immutable launch snapshot, never future imports.
    loaded=[{'vehicleModels':p['vehicleModels']} for p in (vehicle_packs or [])] if mode!='lan' else []
    inject+='\n<script>window.ZemaLoadedVehiclePacks='+json.dumps(loaded).replace('<','\\u003c')+';</script>'
    text=once(data.decode(),'<head>','<head>'+inject)
    text=once(text,'const q = new URLSearchParams(location.search);','const q = window.ZemaRuntime.query;')
    text=once(text,"...(cores <= 2 ? ['-numCores=' + cores] : [])","...['-numCores=' + cores]")
    text=once(text,'startCommitted = false','startCommitted = true')
    text=once(text,"worker.onerror = (e) => { hud.textContent = 'worker error: ' + e.message; };",
        "worker.onerror = (e) => { window.ZemaGameReady=false; hud.textContent='The game worker stopped. '+(typeof e.message==='string'&&e.message?e.message.slice(0,240):'Return to the launcher and press Play again. Your saves are kept.'); const back=document.createElement('a');back.href='/';back.textContent='Back to launcher';back.style.cssText='position:fixed;left:20px;bottom:50px;z-index:3000;color:#acdfbb;background:#172923;padding:12px;border-radius:8px';document.body.append(back); };")
    # Retain the upstream scheduling timer until a real gameplay comparison
    # establishes that removing it on Mac preserves startup and frame pacing.
    text=once(text,'if (lowMemory) hud.textContent = \'Low-memory device (\' + (navigator.deviceMemory || \'?\') + \' GB reported): close other tabs. If the tab shows "Aw, Snap!" or SIGILL it ran out of memory.\';',"if (lowMemory) hud.textContent = 'Lower-detail graphics mode.';")
    text=once(text,'const offscreen = canvas.transferControlToOffscreen();','await window.ZemaRuntimeReady;\n\tconst offscreen = canvas.transferControlToOffscreen();')
    # Never unregister unrelated service workers or delete historical caches.
    text=once(text,'await dropOldCache();','/* Existing caches are preserved. */')
    text=once(text,'installInput(ev.data.input.memory, ev.data.input.block);','window.ZemaGameInput=ZemaController.install(ev.data.input.memory, ev.data.input.block,canvas,startSize,startMode,window.ZemaRuntime.settings,window.ZemaRuntime.features);')
    text=once(text,'canvas: offscreen,','canvas: offscreen,\n        features:window.ZemaRuntime.features,\n        fpsChannel:window.ZemaFPSChannel,')
    text=once(text,"new BroadcastChannel('game-fps')","new BroadcastChannel(window.ZemaFPSChannel)")
    text=once(text,'if (m.world) { ready = true;',"if (m.world || (m.frontend && window.ZemaRuntime.settings.mode==='lan')) { if(m.world)window.ZemaGameReady=true; ready = true;")
    if mode=='lan':
        text=once(text,"1: 'Loading Story Mode'","1: 'Loading multiplayer'")
        text=once(text,'worker.postMessage({','window.ZemaLabLaunch(worker,{')
    else:text=once(text,"const BASE = '/b/8b0b5899ed'.charAt(0) === '_' ? '' : '/b/8b0b5899ed';","const BASE = '"+(prefix or '/offline/'+mode)+"/b/8b0b5899ed';")
    import launch_channels, graphics_status
    return launch_channels.page(graphics_status.page(text)).encode()

def fps_transport(name,data):
    """Namespace actual presented FPS per launch, including simultaneous tabs."""
    text=data.decode()
    if name=='loader.js':
        if "gq.set('fpsChannel'" in text:raise ValueError('FPS loader transport already applied')
        text=once(text,'const gq = new URLSearchParams();',"const gq = new URLSearchParams();\n\tif (/^zema-fps-[a-f0-9-]{36}$/.test(m.fpsChannel || '')) gq.set('fpsChannel', m.fpsChannel);")
    elif name=='wgpu_worker.js':
        text=once(text,"new BroadcastChannel('game-fps')","new BroadcastChannel((()=>{const n=new URLSearchParams(self.location.search).get('fpsChannel');return /^zema-fps-[a-f0-9-]{36}$/.test(n||'')?n:'game-fps';})())")
    return text.encode()

def offline_worker(name,data,mode):
    from stage_browser import PINS
    if name not in PINS or hashlib.sha256(data).hexdigest()!=PINS[name]:raise ValueError('Reviewed offline worker changed: '+name)
    text=data.decode()
    if name == 'io_worker.js':
        import io_lifecycle
        text = io_lifecycle.apply(text)
    if name in ('loader.js','io_worker.js'):
        text=once(text,"indexedDB.open('gta5-userdata', 1)","indexedDB.open('zema-browser-"+mode+"-userdata-v1', 1)")
    if name=='loader.js':text=once(text,"self.location.origin + '/data/'","self.location.origin + '/offline/"+mode+"/data/'")
    if name=='io_worker.js':text=once(text,"getDirectoryHandle('gamedata', { create: true })","getDirectoryHandle('zema-browser-"+mode+"-gamedata-v1', { create: true })")
    if name=='io_worker.js':
        import ui_asset_refresh
        text=ui_asset_refresh.apply(text)
    return fps_transport(name,text.encode()) if name=='loader.js' else text.encode()


class Content:
    def __init__(self,mirror,stage,mods=None,modern_icons=True):
        from browser_lobby_host import BrowserLobbyHost
        self.lobby_host=BrowserLobbyHost()
        from lobby_directory import LobbyDirectory
        self.lobby_directory=LobbyDirectory()
        self.mirror=mirror.resolve(strict=True);self.stage=stage.resolve(strict=True)
        metadata=json.loads((stage/'engine-lan-module.json').read_text())
        if metadata.get('features',{}).get('format')!='zema-browser-features-v1':raise ValueError('This launcher needs the v6 analog/trainer feature stage; older stages are preserved but not compatible with this launcher.')
        if metadata.get('format')!='zema-browser-engine-lan-v1' or metadata.get('engine_sha256')!='11ca8d2c04c5e843d18ff4aea4899d72c86973c6b031df334e67c446b2ae83e0' or metadata.get('online_startup_ready') is not True or metadata.get('runtime_verified') is not False:raise ValueError('Expected experimental online module')
        expected=json.loads((stage/'browser-stage.json').read_text())['staged_hashes']
        expected['game.engine-lan.wasm']=metadata['patched_sha256']
        self.files=set(expected)|{'engine-lan-module.js'}
        for name,sha in expected.items():
            if not re.fullmatch(r'[a-zA-Z0-9_.-]+',name) or hashlib.sha256((stage/name).read_bytes()).hexdigest()!=sha:raise ValueError('Staged browser bytes changed: '+name)
        helper='globalThis.ZemaEngineLanModule='+json.dumps(metadata)+';\n'
        if (stage/'engine-lan-module.js').read_text()!=helper:raise ValueError('Module helper changed')
        self.entry=(ROOT/'entry.js').read_bytes()
        self.index_source=(self.mirror/'index.html').read_bytes()
        self.engine_hashes={'lan':metadata['patched_sha256'],**{mode:expected['game.features.offline.wasm'] for mode in ('story','sandbox')}}
        self.index=index((self.mirror/'index.html').read_bytes(),engine_sha=self.engine_hashes['lan'])
        self.config=overlay((self.mirror/'data/common/data/gameconfig.xml').read_bytes())
        import data_overlay
        self.ui_overlays={}
        for rel in data_overlay.PATCHES:
            try:source,_=self.open_safe(self.mirror/'data'/rel,self.mirror,rel)
            except FileNotFoundError:continue  # Optional UI fixes must not gate an otherwise usable mirror.
            with source:raw=source.read(16*1024*1024+1)
            if len(raw)>16*1024*1024:raise ValueError('UI overlay size limit')
            patched=data_overlay.patch(rel,raw)
            if patched is not None:self.ui_overlays['/data/'+rel]=patched
        # A hashed delta adds the missing official symbols without changing the mirror.
        import modern_map_assets
        self.map_icons={'active':False,'icons':0}
        try:
            if not modern_icons:raise ValueError('Exact map artwork disabled for comparison')
            patch=json.loads(modern_map_assets.PATCH.read_text())
            with self.open_safe(self.mirror/'data'/modern_map_assets.PATH,self.mirror,modern_map_assets.PATH)[0] as original:
                archive=modern_map_assets.apply(original.read(2*1024*1024+1),patch)
            self.ui_overlays['/data/manifest.json']=modern_map_assets.manifest((self.mirror/'data/manifest.json').read_bytes(),patch)
            self.ui_overlays['/data/'+modern_map_assets.PATH]=archive
            self.map_icons={'active':True,'icons':len(patch['icons']),'archive_sha256':patch['result_sha256']}
        except (OSError,ValueError,KeyError,TypeError) as error:
            self.map_icons['reason']=type(error).__name__  # Keep the original on unsupported inputs.
        self.assets={name:(ROOT/name).read_bytes() for name in ['session-restart.js','launcher.html','launcher.css','launcher.js','lobby-model.js','lobby-ui.js','launch-settings.js','browser-performance.js','controller.js','runtime.js','browser-saves.js','browser-features.js','vehicle-catalog.js','browser-trainer.js','vehicle-ui.js','trainer-ui.js','performance-run.js','browser-mods-ui.js','connection-ui.js','lan-loading.js','solo-card.png','friends-card.png','los-santos-map.jpg','zplay-gta-green.svg','zplay-gta-green-32.png','zplay-gta-green-180.png','favicon.ico']}
        self.assets['launcher-icon.png']=(ROOT.parent/'app/App/Assets.xcassets/HomeIcon.imageset/HomeIcon.png').read_bytes()
        import mod_previews
        for row in mod_previews.load().values():
            self.assets[row['file']]=(mod_previews.RESOURCES/row['file']).read_bytes()
        self.pages={mode:index((self.mirror/'index.html').read_bytes(),mode,engine_sha=self.engine_hashes[mode]) for mode in ('story','sandbox')}
        self.offline={mode:{name:offline_worker(name,(self.mirror/BUILD.lstrip('/')/name).read_bytes(),mode) for name in ('game.js','loader.js','io_worker.js')} for mode in ('story','sandbox')}
        h=hashlib.sha256()
        with (self.mirror/BUILD.lstrip('/')/'game.wasm').open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
        if h.hexdigest()!=metadata['engine_sha256']:raise ValueError('Reviewed offline engine changed')
        self.features=metadata.get('features') is not None
        if self.features:
            from browser_features import offline_patch
            self.offline={mode:{name:offline_patch(name,(self.mirror/BUILD.lstrip('/')/name).read_bytes(),mode,gamer_tags=metadata['features'].get('gamer_tag') is not None,blip_sprites=metadata['features'].get('blip_sprites') is not None) for name in ('game.js','loader.js','io_worker.js')} for mode in ('story','sandbox')}
        self.mods=mods;self.sessions={};self.session_leases={};self.session_releases={};self.session_clock=time.monotonic;self.session_lock=threading.RLock();self.runtime_lines=deque(maxlen=1024)
        # Repeated audio-bank dumps must not erase every GPU/failure signal.
        # Retain bounded unique messages with counts as well as the raw tail.
        self.runtime_signals=OrderedDict()
        self.save_signals=OrderedDict()
        self.asset_signals=OrderedDict()

    def record_runtime(self,lines):
        with self.session_lock:
            self.runtime_lines.extend(lines)
            for line in lines:
                if line.startswith('[online] LAN save:'):
                    if not hasattr(self,'save_signals'):self.save_signals=OrderedDict()
                    self.save_signals[line]=min(self.save_signals.get(line,0)+1,2**53-1)
                    if len(self.save_signals)>64:self.save_signals.popitem(last=False)
                if re.fullmatch(r'\[text-missing\] hash 0x[0-9a-f]{8}|\[blip-missing\] sprite -?[0-9]{1,10} table [0-9]{1,5}|\[blip-fallback\] sprite -?[0-9]{1,10} -> [0-9]{1,4} table [0-9]{1,5}',line):
                    if not hasattr(self,'asset_signals'):self.asset_signals=OrderedDict()
                    self.asset_signals[line]=min(self.asset_signals.get(line,0)+1,2**53-1)
                    if len(self.asset_signals)>256:self.asset_signals.popitem(last=False)
                self.runtime_signals[line]=min(self.runtime_signals.get(line,0)+1,2**53-1)
                self.runtime_signals.move_to_end(line)
                if len(self.runtime_signals)>256:self.runtime_signals.popitem(last=False)

    def launch(self,mode):
        if mode=='lan':return {'prefix':'','mode':mode,'mods':[]}
        if mode not in ('story','sandbox'):raise ValueError('Unknown launch mode')
        if not self.features:raise ValueError('Use the reviewed feature browser stage before starting this launcher')
        with self.session_lock:
            self.prune_sessions()
            if len(self.sessions)>=4:
                # A recently closed page can reload for 45 seconds, but does
                # not prevent a deliberate fifth launch from using its slot.
                for identifier in list(self.session_releases):
                    self.drop_session(identifier)
                    if len(self.sessions)<4:break
            if len(self.sessions)>=4:raise ValueError('Four launch snapshots remain open. Close unused lab game tabs before another launch.')
            manifest=getattr(self,'ui_overlays',{}).get('/data/manifest.json') or (self.mirror/'data/manifest.json').read_bytes()
            snapshot=self.mods.snapshot(mode,manifest,(self.mirror/'data/common/data/dlcList.xml').read_bytes()) if self.mods else None
            identifier=secrets.token_hex(16);self.sessions[identifier]=(mode,snapshot)
        return {'prefix':'/session/'+identifier,'mode':mode,'mods':snapshot.catalog if snapshot else []}

    def drop_session(self,identifier):
        self.sessions.pop(identifier,None);self.session_leases.pop(identifier,None);self.session_releases.pop(identifier,None)

    def prune_sessions(self):
        now=self.session_clock()
        for identifier,deadline in list(self.session_releases.items()):
            if deadline<=now:self.drop_session(identifier)

    def release(self,identifier,lease):
        if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('Invalid launch identifier')
        if not isinstance(lease,str) or not re.fullmatch('[a-f0-9]{32}',lease):raise ValueError('Invalid page lease')
        with self.session_lock:
            self.prune_sessions()
            current=identifier in self.sessions and self.session_leases.get(identifier)==lease
            if current:self.session_releases[identifier]=self.session_clock()+45
        return {'released':current}

    def feature_file(self,name):
        mapping={'game.wasm':'game.features.offline.wasm','browser-features.js':'browser-features.js','browser-trainer.js':'browser-trainer.js','browser-features-module.js':'browser-features-module.js'}
        if name=='wgpu_worker.js' and name in self.files:mapping[name]=name
        if name=='memory_filename.js' and name in self.files:mapping[name]=name
        if name in ('text_fallback.js','blip_sprites.js') and name in self.files:mapping[name]=name
        if name=='script_bank.js' and name in self.files:mapping[name]=name
        if name=='gamer_tags.js' and name in self.files:mapping[name]=name
        if name=='session-restart.js' and name in self.files:mapping[name]=name
        if self.features and name in mapping:
            source,mime=self.open_safe(self.stage/mapping[name],self.stage,name)
            if name=='wgpu_worker.js':
                with source:data=source.read()
                return io.BytesIO(fps_transport(name,data)),mime
            return source,mime
        return None

    def session_file(self,path,claim=True):
        match=re.fullmatch(r'/session/([a-f0-9]{32})(/.*)',path)
        if not match:raise FileNotFoundError(path)
        with self.session_lock:
            self.prune_sessions();session=self.sessions.get(match[1])
            lease=self.session_leases.get(match[1])
            if session and match[2]=='/play/'+session[0] and claim:
                lease=secrets.token_hex(16);self.session_leases[match[1]]=lease;self.session_releases.pop(match[1],None)
        if not session:raise FileNotFoundError('Launch snapshot is no longer available')
        mode,snapshot=session;tail=match[2];prefix='/session/'+match[1]
        if tail=='/play/'+mode:return io.BytesIO(index(self.index_source,mode,prefix,engine_sha=self.engine_hashes[mode],lease=lease,vehicle_packs=snapshot.catalog if snapshot else [])),'text/html'
        if tail.startswith(BUILD):
            name=tail[len(BUILD):]
            special=self.feature_file(name)
            if special:return special
            if name in self.offline[mode]:
                content=self.offline[mode][name]
                if name=='loader.js':content=once(content.decode(),"self.location.origin + '/offline/"+mode+"/data/'","self.location.origin + '"+prefix+"/data/'").encode()
                if name=='io_worker.js' and snapshot and snapshot.catalog:
                    content=once(content.decode(),"getDirectoryHandle('zema-browser-"+mode+"-gamedata-v1', { create: true })","getDirectoryHandle('zema-browser-"+mode+"-gamedata-"+snapshot.fingerprint+"', { create: true })").encode()
                return io.BytesIO(content),'text/javascript'
            return self.original(tail)
        if tail.startswith('/data/'):
            name=tail[6:]
            if snapshot:
                content=snapshot.manifest_bytes if name=='manifest.json' and snapshot.catalog else snapshot.resolve(name)
                if content is not None:return io.BytesIO(content),mimetypes.guess_type(name)[0] or 'application/octet-stream'
            return self.original(tail)
        raise FileNotFoundError(path)
    def select(self,path,head=False):
        source,mime=self._select(path,head=head)
        import launch_channels, graphics_status
        name=path.rsplit('/',1)[-1]
        if name in launch_channels.COUNTS:
            with source:data=source.read()
            return io.BytesIO(graphics_status.worker(name,launch_channels.worker(name,data))),mime
        return source,mime

    def _select(self,path,head=False):
        if '\0' in path or '\\' in path or any(x in ('..','.') or x.startswith('.') for x in path.split('/') if x):raise ValueError('Unsafe path')
        if path.startswith('/session/'):return self.session_file(path,claim=not head)
        if path=='/zema-lab/diagnostics':
            with self.session_lock:data=json.dumps({'scope':'bounded local LAN runtime diagnostics','lines':list(self.runtime_lines),'signals':[{'text':text,'count':count} for text,count in self.runtime_signals.items()],'save_signals':[{'text':text,'count':count} for text,count in getattr(self,'save_signals',{}).items()],'asset_signals':[{'text':text,'count':count} for text,count in getattr(self,'asset_signals',{}).items()]}).encode()
            return io.BytesIO(data),'application/json'
        if path=='/zema-lab/mods':
            if self.mods is None:raise ValueError('Private mod storage not configured')
            return io.BytesIO(json.dumps(self.mods.catalog()).encode()),'application/json'
        if path in ('/','/index.html'):return io.BytesIO(self.assets['launcher.html']),'text/html'
        if path=='/favicon.ico':return io.BytesIO(self.assets['favicon.ico']),'image/x-icon'
        if path=='/play/lan':return io.BytesIO(self.index),'text/html'
        if path in ('/play/story','/play/sandbox'):return io.BytesIO(self.pages[path.rsplit('/',1)[1]]),'text/html'
        if path=='/zema-lab/entry.js':return io.BytesIO(self.entry),'text/javascript'
        if path.startswith('/zema-lab/') and path[10:] in self.assets:
            name=path[10:];return io.BytesIO(self.assets[name]),mimetypes.guess_type(name)[0] or 'application/octet-stream'
        for mode in ('story','sandbox'):
            prefix='/offline/'+mode
            if path.startswith(prefix+BUILD):
                name=path[len(prefix+BUILD):]
                special=self.feature_file(name)
                if special:return special
                if name in self.offline[mode]:return io.BytesIO(self.offline[mode][name]),'text/javascript'
                path=path[len(prefix):]
                # Offline paths must never receive the patched LAN workers.
                return self.original(path)
            if path.startswith(prefix+'/data/'):return self.original(path[len(prefix):])
        if path=='/data/common/data/gameconfig.xml':return io.BytesIO(self.config),'application/xml'
        if path.startswith(BUILD) and path[len(BUILD):] in self.files:file=self.stage/path[len(BUILD):];base=self.stage
        else:return self.original(path)
        source,mime=self.open_safe(file,base,path)
        if file.name in ('loader.js','wgpu_worker.js'):
            with source:data=source.read()
            return io.BytesIO(fps_transport(file.name,data)),mime
        return source,mime
    def original(self,path):
        overlays=getattr(self,'ui_overlays',{})
        if path.lower() in overlays:return io.BytesIO(overlays[path.lower()]),mimetypes.guess_type(path)[0] or 'application/octet-stream'
        return self.open_safe(self.mirror/path.lstrip('/'),self.mirror,path)
    @staticmethod
    def open_safe(file,base,path):
        # Resolve before open; reject symlinks and directories, never list folders.
        cursor=file
        while cursor!=base:
            if cursor.is_symlink():raise ValueError('Symlink refused')
            cursor=cursor.parent
        if not file.resolve().is_relative_to(base) or not file.is_file():raise FileNotFoundError(path)
        return file.open('rb'),mimetypes.guess_type(str(file))[0] or 'application/octet-stream'


class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def setup(self):
        super().setup();self.connection.settimeout(15)
    def log_message(self,*args):pass
    def end_headers(self):
        for key,value in [('Cross-Origin-Opener-Policy','same-origin'),('Cross-Origin-Embedder-Policy','require-corp'),('Cross-Origin-Resource-Policy','same-origin'),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')]:self.send_header(key,value)
        super().end_headers()
    def allowed(self):
        port=self.server.server_port
        return self.headers.get('Host') in ('127.0.0.1:'+str(port),'localhost:'+str(port)) and self.headers.get('Origin') in (None,'http://127.0.0.1:'+str(port),'http://localhost:'+str(port))
    def do_GET(self):self.serve(False)
    def do_HEAD(self):self.serve(True)
    def serve(self,head):
        if not self.allowed():self.send_error(403);return
        try:
            path=unquote(urlsplit(self.path).path)
            source,mime=self.server.content.select(path,head=head)
            with source:
                source.seek(0,2);size=source.tell();source.seek(0);start=0;end=size-1;partial=False
                if self.headers.get('Range'):
                    m=re.fullmatch(r'bytes=(\d*)-(\d*)',self.headers['Range'])
                    if not m or not any(m.groups()):raise ValueError('Unsupported byte range')
                    start=int(m[1]) if m[1] else max(0,size-int(m[2]))
                    end=min(size-1,int(m[2])) if m[1] and m[2] else size-1
                    if start>=size or end<start:
                        self.send_response(416);self.send_header('Content-Range','bytes */%d'%size);self.send_header('Content-Length','0');self.end_headers();return
                    partial=True
                self.send_response(206 if partial else 200);self.send_header('Content-Type',mime);self.send_header('Accept-Ranges','bytes')
                if partial:self.send_header('Content-Range','bytes %d-%d/%d'%(start,end,size))
                count=max(0,end-start+1);self.send_header('Content-Length',str(count));self.end_headers()
                if not head:
                    source.seek(start)
                    while count:
                        chunk=source.read(min(count,1024*1024))
                        if not chunk:break
                        self.wfile.write(chunk);count-=len(chunk)
        except FileNotFoundError:self.send_error(404)
        except (ValueError,OSError):self.send_error(400)
    def do_POST(self):
        if not self.allowed():self.send_error(403);return
        batch_path=urlsplit(self.path).path
        if batch_path.startswith('/zema-lab/'):
            self.api_post(batch_path);return
        if batch_path not in ('/data/batch','/offline/story/data/batch','/offline/sandbox/data/batch') and not re.fullmatch('/session/[a-f0-9]{32}/data/batch',batch_path):self.send_error(404);return
        data_prefix=batch_path[:-5]
        try:
            if self.headers.get('Transfer-Encoding'):raise ValueError('Transfer coding refused')
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=262144:raise ValueError('Batch request too large')
            raw=self.rfile.read(length)
            if len(raw)!=length:raise ValueError('Short request')
            runs=json.loads(raw)
            if not isinstance(runs,list) or len(runs)>1000:raise ValueError('Batch limit')
            output=io.BytesIO();lengths=[]
            for row in runs:
                if not isinstance(row,list) or len(row)!=3:raise ValueError('Invalid run')
                name,start,end=row
                if not isinstance(name,str) or name.startswith('/') or any(type(x) is not int for x in (start,end)) or start<0 or end<start:raise ValueError('Invalid run')
                source,_=self.server.content.select(data_prefix+name)
                with source:
                    source.seek(0,2);n=max(0,min(end+1,source.tell())-start)
                    if output.tell()+n>64*1024*1024:raise ValueError('Batch limit')
                    source.seek(start);chunk=source.read(n)
                    if len(chunk)!=n:raise ValueError('Asset changed during read')
                    output.write(chunk);lengths.append(n)
            body=output.getvalue();compressed=parse_qs(urlsplit(self.path).query).get('gz')==['1']
            if compressed:body=gzip.compress(body,compresslevel=1)
            self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Length',str(len(body)));self.send_header('X-Run-Lengths',','.join(map(str,lengths)))
            if compressed:self.send_header('Content-Encoding','gzip')
            self.end_headers();self.wfile.write(body)
        except (ValueError,TypeError,OSError):self.send_error(400)

    def api_post(self,path):
        # Same-origin custom-header mutations cannot be submitted by cross-site forms.
        port=self.server.server_port;origin=self.headers.get('Origin')
        if self.headers.get('X-Zema-Lab')!='1' or origin not in (None,'http://127.0.0.1:'+str(port),'http://localhost:'+str(port)):
            self.send_error(403);return
        try:
            from browser_mods import MAX_IMPORT
            if self.headers.get('Transfer-Encoding'):raise ValueError('Transfer coding refused')
            length=int(self.headers.get('Content-Length','0'));limit=MAX_IMPORT if path=='/zema-lab/mods/import' else 65536 if path=='/zema-lab/runtime' else 4096
            if not 0<length<=limit:raise ValueError('Request body exceeds its limit')
            raw=self.rfile.read(length)
            if len(raw)!=length:raise ValueError('Incomplete request')
            content=self.server.content
            if path=='/zema-lab/mods/import':
                if self.headers.get('Content-Type')!='application/octet-stream':raise ValueError('Expected binary DLC upload')
                names=parse_qs(urlsplit(self.path).query).get('filename',[])
                if len(names)!=1:raise ValueError('One import filename required')
                result=content.mods.import_bytes(names[0],raw)
            else:
                if self.headers.get('Content-Type')!='application/json':raise ValueError('Expected JSON request')
                body=json.loads(raw)
                if not isinstance(body,dict):raise ValueError('Expected an object')
                if path=='/zema-lab/runtime' and set(body)=={'lines'}:
                    lines=body['lines']
                    if not isinstance(lines,list) or len(lines)>24 or any(not isinstance(line,str) or len(line)>512 for line in lines):raise ValueError('Runtime diagnostic limit')
                    content.record_runtime(lines)
                    result={'accepted':len(lines)}
                elif path=='/zema-lab/mods/toggle' and set(body)=={'id','enabled'}:result=content.mods.set_enabled(body['id'],body['enabled'])
                elif path=='/zema-lab/mods/remove' and set(body)=={'id'}:result=content.mods.remove(body['id'])
                elif path=='/zema-lab/lobbies/discover' and not body:
                    from lobby_discovery import discover
                    result=discover()
                elif path=='/zema-lab/lobbies/probe' and set(body)=={'addresses'}:result=content.lobby_directory.probe(body['addresses'])
                elif path=='/zema-lab/launcher/status' and not body:
                    from browser_lobby_host import addresses
                    result={'service':'zgta-browser-launcher','files_available':content.mirror.is_dir() and content.stage.is_dir(),'networks':addresses()}
                elif path=='/zema-lab/host/status' and not body:result=content.lobby_host.status()
                elif path=='/zema-lab/host/start' and set(body)=={'room','connection'}:result=content.lobby_host.start(body['room'],body['connection'])
                elif path=='/zema-lab/host/stop' and set(body)=={'id'}:result=content.lobby_host.stop(body['id'])
                elif path=='/zema-lab/host/restart' and set(body)=={'id'}:result=content.lobby_host.restart(body['id'])
                elif path=='/zema-lab/launch' and set(body)=={'mode'}:result=content.launch(body['mode'])
                elif path=='/zema-lab/session/release' and set(body)=={'id','lease'}:result=content.release(body['id'],body['lease'])
                else:raise ValueError('Unknown operation or fields')
            data=json.dumps(result).encode();self.send_response(200)
        except (ValueError,TypeError,OSError,AttributeError) as error:
            data=json.dumps({'error':str(error)[:300]}).encode();self.send_response(400)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mirror',type=Path,required=True);p.add_argument('--stage',type=Path,required=True);p.add_argument('--port',type=int,default=18887);p.add_argument('--original-map-icons',action='store_true',help='Use the installed minimap archive for an isolated comparison');a=p.parse_args()
    if a.port!=18887:p.error('Use the separate reviewed lab origin on port 18887')
    from browser_mods import BrowserMods
    from stage_browser import APP
    content=Content(a.mirror,a.stage,BrowserMods(APP/'Build/BrowserMods-20261017'),modern_icons=not a.original_map_icons)
    server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);server.content=content;server.daemon_threads=True
    print('Experimental browser: http://127.0.0.1:18887/ (Ctrl+C stops)',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:content.lobby_host.close();content.lobby_directory.close();server.server_close()

if __name__=='__main__':main()
