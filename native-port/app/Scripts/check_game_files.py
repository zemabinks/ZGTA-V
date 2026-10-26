#!/usr/bin/env python3
"""Check that a game folder has what the build needs, from game build 8b0b5899ed:
the engine, the file list and the shaders (index.json and its packs)."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ENGINE_SHA256 = '11ca8d2c04c5e843d18ff4aea4899d72c86973c6b031df334e67c446b2ae83e0'
SHADER_INDEX_SHA256 = '11c331895051b30126980ef666bd8935314ab400348b17c56ef8fe8983f50ee0'

parser = argparse.ArgumentParser()
parser.add_argument('--mirror', type=Path, required=True)
mirror = parser.parse_args().mirror

def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()

engine = mirror / 'b/8b0b5899ed/game.wasm'
index = mirror / 'b/8b0b5899ed/shaders/index.json'
for required in [engine, mirror / 'data/manifest.json', index]:
    if not required.exists():
        sys.exit(f'Missing {required.relative_to(mirror)} in {mirror}. Use the folder that contains data/ and b/.')
if sha256(engine) != ENGINE_SHA256:
    sys.exit('Your game.wasm is not the build this port supports (8b0b5899ed).')
if sha256(index) != SHADER_INDEX_SHA256:
    sys.exit('Your shader index does not match game build 8b0b5899ed.')
for pack in json.loads(index.read_text())['_packs']:
    if not (index.parent / pack['file']).exists():
        sys.exit(f"Missing shader pack {pack['file']} next to the shader index.")
print('Game files OK.')
