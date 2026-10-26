"""Stage exact-source browser worker wiring without editing the game mirror.

Adds files only to a newly generated engine-LAN Build output. Game launch is
blocked until the separate online startup/character callbacks are ready.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
APP = ROOT.parent / 'app'
PINS = {'game.js': '81a7d6e912238de3d89bcafb1b01450671c6793167babb0ec970f308f454bcf0',
        'loader.js': '9de25898fa9a9ec5e67ca647debf941849b936e3163402944581feaaae5ac0ff',
        'io_worker.js': 'd91c89e64f7f280666b5c9d1669ed6d65d66605077264569a49146ed79fe0bae'}
PREFIX = "importScripts(new URL('online.js',self.location.href).href,new URL('profile-rpc.js',self.location.href).href,new URL('engine-lan-browser.js',self.location.href).href,new URL('engine-lan-module.js',self.location.href).href);\n"


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Reviewed browser source anchor changed')
    return text.replace(before, after)


def patch(name, data):
    if hashlib.sha256(data).hexdigest() != PINS[name]:
        raise ValueError('Browser source hash changed: ' + name)
    text = data.decode()
    if name == 'io_worker.js':
        import io_lifecycle
        text = io_lifecycle.apply(text)
    if name == 'io_worker.js':
        import ui_asset_refresh
        text=ui_asset_refresh.apply(text)
        return once(text, "indexedDB.open('gta5-userdata', 1)",
                    "indexedDB.open('zema-engine-lan-userdata-v1', 1)").encode()
    if name == 'game.js':
        text = once(text, 'wasmMemory=msgData.wasmMemory;',
                    'self.__zemaEngineLanContext=msgData.zemaEngineLanContext;wasmMemory=msgData.wasmMemory;')
        text = once(text, 'worker.postMessage({cmd:1,handlers,wasmMemory,wasmModule})',
                    'worker.postMessage({cmd:1,handlers,wasmMemory,wasmModule,zemaEngineLanContext:self.__zemaEngineLanContext})')
        text = once(text, 'new WebAssembly.Instance(wasmModule,getWasmImports())',
                    'ZemaEngineLan.instance(wasmModule,getWasmImports(),self.__zemaEngineLanContext)')
    else:
        # Keep the original directive prologue effective after adding imports.
        text = once(text, "'use strict';", "'use strict';\n" + PREFIX)
        text = once(text, '\tconst m = ev.data;',
                    '\tconst m = ev.data;\n\tZemaEngineLan.requireGameReady();\n'
                    '\tif(!m.engineLan)throw Error("Explicit admitted engine-LAN context required");\n'
                    '\tself.__zemaEngineLanContext=m.engineLan;')
        text = once(text, "fetch(B + '/game.wasm')", "fetch(B + '/game.engine-lan.wasm')")
        text = once(text, 'WebAssembly.instantiate(bytes, imports)',
                    'ZemaEngineLan.instantiate(bytes,imports,self.__zemaEngineLanContext)')
        text = once(text, 'WebAssembly.instantiateStreaming(res, imports)',
                    'ZemaEngineLan.instantiateStreaming(res,imports,self.__zemaEngineLanContext)')
        # Experimental online profiles must not read/write existing Story saves.
        text = text.replace("'gta5-userdata'", "'zema-engine-lan-userdata-v1'")
    return ((PREFIX + text) if name == 'game.js' else text).encode()


def stage(mirror, output):
    if output.parent != APP.absolute() / 'Build' or '..' in output.parts:
        raise ValueError('Use an isolated app Build output')
    if any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('Symlinked browser output refused')
    metadata = json.loads((output / 'engine-lan-module.json').read_text())
    if metadata.get('format') != 'zema-browser-engine-lan-v1' or metadata.get('online_startup_ready') not in (True,False):
        raise ValueError('Expected the reviewed experimental browser module')
    if hashlib.sha256((output / 'game.engine-lan.wasm').read_bytes()).hexdigest() != metadata['patched_sha256']:
        raise ValueError('Prepared browser engine changed')
    files = {name: patch(name, (mirror / name).read_bytes()) for name in PINS}
    files.update({'engine-lan-browser.js': (ROOT / 'browser.js').read_bytes(),
                  'network-worker.js': (ROOT / 'network-worker.js').read_bytes(),
                  'online.js':(ROOT/'online.js').read_bytes(),'profile-rpc.js':(ROOT/'profile-rpc.js').read_bytes(),
                  'profile-worker.js':(ROOT/'profile-worker.js').read_bytes()})
    if any((output / name).exists() or (output / name).is_symlink() for name in files):
        raise ValueError('Preserve existing browser outputs')
    for name, data in files.items():
        with (output / name).open('xb') as target:
            target.write(data)
    return {'format': 'zema-browser-engine-lan-stage-v1', 'source_hashes': PINS,
            'staged_hashes': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
            'separate_network_worker': True, 'pthread_shared_queues': True,
            'original_files_changed': False, 'game_launch_enabled':metadata['online_startup_ready'],
            'runtime_verified':False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mirror', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    try:
        record = stage(args.mirror, args.output.absolute())
        with (args.output / 'browser-stage.json').open('x') as target:
            target.write(json.dumps(record, indent=2) + '\n')
        print(json.dumps(record, indent=2))
    except (OSError, ValueError, KeyError) as error:
        p.exit(1, str(error) + '\n')
