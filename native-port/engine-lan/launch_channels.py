"""Per-document browser channels; storage names and engine bytes are unchanged."""
import re
from stage_browser import once

MARK='/* ZGTA_LAUNCH_CHANNELS_V1 */'
BOOT=MARK+'''\n(function(root){
 if(root.ZemaLaunchChannels)return;
 const page=typeof document==='object',scope=page?crypto.randomUUID().replace(/-/g,''):new URL(root.location.href).searchParams.get('zgtaLaunch');
 if(!/^[a-f0-9]{32}$/.test(scope||''))throw Error('Game launch channel identity is missing. Return to the launcher.');
 const channels=new Set(['game-io','game-progress','game-crash','game-log','game-debug']);
 root.ZemaLaunchChannels=Object.freeze({scope,name:base=>{if(!channels.has(base))throw Error('Unknown game channel');return base+'-'+scope;},url:path=>{const url=new URL(path,root.location.href);if(url.origin!==root.location.origin)throw Error('Cross-origin game worker refused');url.searchParams.set('zgtaLaunch',scope);return url.href;}});
})(globalThis);\n'''
COUNTS={'loader.js':{'game-progress':2},'game.js':{'game-log':1,'game-crash':1,'game-progress':1},'io_worker.js':{'game-progress':1,'game-io':1},'wgpu_worker.js':{'game-log':1,'game-progress':2,'game-debug':1},'browser-features.js':{'game-log':4},'browser-trainer.js':{'game-log':1},'engine-lan-browser.js':{'game-log':4}}
LITERAL=re.compile(r'new BroadcastChannel\(([\'\"])(game-(?:io|progress|crash|log|debug))\1\)')

def channels(text,expected):
 counts={name:len([m for m in LITERAL.finditer(text) if m.group(2)==name]) for name in expected}
 if counts!=expected or any(m.group(2) not in expected for m in LITERAL.finditer(text)):raise ValueError('Reviewed launch channel anchors changed')
 return LITERAL.sub(lambda m:'new BroadcastChannel(ZemaLaunchChannels.name('+repr(m.group(2))+'))',text)

def page(text):
 if MARK in text:raise ValueError('Launch channels already applied')
 text=channels(text,{'game-crash':1,'game-progress':1,'game-log':1,'game-io':1,'game-debug':1})
 text=once(text,"const worker = new Worker(BASE + '/loader.js');","const worker = new Worker(ZemaLaunchChannels.url(BASE + '/loader.js'));\nwindow.ZemaGameWorker=worker;")
 return once(text,'<head>','<head>\n<script>'+BOOT+'</script>')

def worker(name,data):
 if name not in COUNTS:return data
 text=data.decode()
 if MARK in text:raise ValueError('Launch channels already applied')
 text=channels(text,COUNTS[name])
 if name=='loader.js':
  text=once(text,"new Worker(B + '/wgpu_worker.js' + (gq.toString() ? '?' + gq : ''))","new Worker(ZemaLaunchChannels.url(B + '/wgpu_worker.js' + (gq.toString() ? '?' + gq : '')))")
  text=once(text,"new Worker(B + '/io_worker.js')","new Worker(ZemaLaunchChannels.url(B + '/io_worker.js'))")
  anchor="B + '/game.js' + ((m.fullConsole || m.remoteLog) ? '?' + [m.fullConsole ? 'console=1' : '', m.remoteLog ? 'log=1' : ''].filter(Boolean).join('&') : '')"
  text=once(text,anchor,'ZemaLaunchChannels.url('+anchor+')')
 # Keep an original leading strict directive effective where one exists.
 if text.startswith("'use strict';"):text=once(text,"'use strict';","'use strict';\n"+BOOT)
 else:text=BOOT+text
 return text.encode()
