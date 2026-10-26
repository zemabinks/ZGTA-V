#!/usr/bin/env python3
"""Rebuild the build inputs uploaded by the website builder into a minimal game folder.

The website stores your own files in your private repository's `build-inputs`
branch, split into parts: inputs/files.json lists each file's name, parts and
SHA-256. The shaders arrive either as separate files or as one zip of the
shaders folder (made with Compress in the iPhone Files app).
"""
import argparse
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--inputs', type=Path, required=True, help='checkout of the build-inputs branch')
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
listing = json.loads((args.inputs / 'inputs/files.json').read_text())
shaders = args.out / 'b/8b0b5899ed/shaders'
shaders.mkdir(parents=True, exist_ok=True)
(args.out / 'data').mkdir(parents=True, exist_ok=True)
targets = {'game.wasm': args.out / 'b/8b0b5899ed/game.wasm', 'manifest.json': args.out / 'data/manifest.json'}

for entry in listing['files']:
    data = b''.join((args.inputs / 'inputs' / part).read_bytes() for part in entry['parts'])
    if hashlib.sha256(data).hexdigest() != entry['sha256']:
        sys.exit(f"{entry['name']} was damaged during upload; upload it again.")
    name = entry['name']
    if name.lower().endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for member in archive.namelist():
                base = Path(member).name
                if base == 'index.json' or (base.startswith('pack') and base.endswith('.bin')):
                    (shaders / base).write_bytes(archive.read(member))
    elif name in targets:
        targets[name].write_bytes(data)
    elif name == 'index.json' or (name.startswith('pack') and name.endswith('.bin')):
        (shaders / name).write_bytes(data)
    else:
        print(f'Ignoring unexpected file {name}')
print('Build inputs assembled.')
