#!/usr/bin/env python3
"""Unpack the game's shader packs into one WGSL file (+ constant table) per shader.

Input: a shaders folder with index.json and packN.<hash>.bin (your own game files).
Output: <hash>.wgsl and <hash>.consts.json next to a copy of index.json, which
Scripts/build_metal_shaders.py compiles into the app's Metal library.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--shaders', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
index = json.loads((args.shaders / 'index.json').read_text())
args.out.mkdir(parents=True, exist_ok=True)
shutil.copyfile(args.shaders / 'index.json', args.out / 'index.json')
packs = {}
written = 0
for name, record in index.items():
    if name.startswith('_') or not record.get('ok') or 'p' not in record:
        continue
    number, offset, wgsl_bytes, consts_bytes = record['p']
    if number not in packs:
        packs[number] = (args.shaders / index['_packs'][number]['file']).read_bytes()
    data = packs[number]
    if offset + wgsl_bytes + consts_bytes > len(data):
        sys.exit(f'Shader pack {number} is shorter than its index says.')
    (args.out / (name + '.wgsl')).write_bytes(data[offset:offset + wgsl_bytes])
    if consts_bytes:
        (args.out / (name + '.consts.json')).write_bytes(data[offset + wgsl_bytes:offset + wgsl_bytes + consts_bytes])
    written += 1
print(f'Unpacked {written} shaders.')
