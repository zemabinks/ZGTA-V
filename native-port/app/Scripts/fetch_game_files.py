#!/usr/bin/env python3
"""Download the game files the build needs from YOUR OWN server.

The build needs the engine (b/8b0b5899ed/game.wasm), the file list
(data/manifest.json) and the shaders (b/8b0b5899ed/shaders: index.json and
18 shader packs, about 75 MB), which are precompiled into the app for Metal.
Everything else streams to the phone while you play. Nothing is downloaded
from anywhere except the server you give.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from download_ranges import download

ENGINE = 'b/8b0b5899ed/game.wasm'
ENGINE_SHA256 = '11ca8d2c04c5e843d18ff4aea4899d72c86973c6b031df334e67c446b2ae83e0'
SHADERS = 'b/8b0b5899ed/shaders'
SHADER_INDEX_SHA256 = '11c331895051b30126980ef666bd8935314ab400348b17c56ef8fe8983f50ee0'

parser = argparse.ArgumentParser()
parser.add_argument('--server', required=True, help='e.g. https://my-pc.tailnet-name.ts.net')
parser.add_argument('--out', type=Path, required=True, help='folder to place a minimal mirror in')
args = parser.parse_args()
server = args.server.rstrip('/')

def fetch(relative, expected_sha256=None, expected_bytes=None):
    target = args.out / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f'Downloading {relative} from your server...', flush=True)
    last_error = None
    for attempt in range(1, 4):
        try:
            download(f'{server}/{relative}', target, expected_sha256)
            if expected_bytes is not None and target.stat().st_size != expected_bytes:
                raise ValueError('Shader pack size does not match the pinned index')
            return target
        except Exception as error:
            last_error = error
    sys.exit(f'Could not download {server}/{relative}: {last_error}\n'
             'Check that the server is running, reachable, and serves the folder that contains data/ and b/.')

engine = args.out / ENGINE
if not (engine.exists() and hashlib.sha256(engine.read_bytes()).hexdigest() == ENGINE_SHA256):
    engine = fetch(ENGINE, ENGINE_SHA256)
if hashlib.sha256(engine.read_bytes()).hexdigest() != ENGINE_SHA256:
    sys.exit('Your game.wasm is not the build this port supports (8b0b5899ed). '
             'The engine patches are made for that exact file.')
fetch('data/manifest.json')
index = fetch(SHADERS + '/index.json', SHADER_INDEX_SHA256)
if hashlib.sha256(index.read_bytes()).hexdigest() != SHADER_INDEX_SHA256:
    sys.exit('Your shader index does not match game build 8b0b5899ed.')
for pack in json.loads(index.read_text())['_packs']:
    target = args.out / SHADERS / pack['file']
    if not target.exists() or target.stat().st_size != pack['bytes']:
        fetch(SHADERS + '/' + pack['file'], expected_bytes=pack['bytes'])
print('Game files OK.')

