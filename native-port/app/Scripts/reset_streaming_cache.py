#!/usr/bin/env python3
"""Retain warmed blocks in an owned simulator trial; make route-only blocks cold."""
import argparse
import json
import os
from pathlib import Path
import re

parser = argparse.ArgumentParser()
parser.add_argument('--cache-tag', required=True)
args = parser.parse_args()
if not re.fullmatch(r'stream-[A-Za-z0-9_-]{1,57}',args.cache_tag):
    raise SystemExit('Only a named stream- simulator trial can be reset')
root = Path(__file__).resolve().parents[1]
manifest = json.loads((root/'Resources/manifest.json').read_text())
warm = dict(json.loads((root/'Resources/bootset_native.json').read_text()))
cache = root/'Build/SimulatorData'/('AssetCache-'+manifest['version']+'-'+args.cache_tag)/'Packed-v1'
if not cache.is_dir():
    raise SystemExit('No matching owned streaming trial cache')
before = after = 0
popcounts = [bin(value).count('1') for value in range(256)]
for identity,(path,size,*_) in enumerate(manifest['files']):
    bitmap,data = cache/(str(identity)+'.map'),cache/(str(identity)+'.data')
    if not bitmap.exists():continue
    if bitmap.is_symlink() or data.is_symlink():raise RuntimeError('Refusing linked trial cache files')
    old = bitmap.read_bytes()
    assert data.stat().st_size == size and len(old) == ((size+4095)//4096+7)//8
    new = bytearray(len(old))
    for first,last in warm.get(path,[]):
        for block in range(first//4096,last//4096+1):
            new[block//8] |= old[block//8] & (1<<(block%8))
    before += sum(popcounts[b] for b in old)
    after += sum(popcounts[b] for b in new)
    with bitmap.open('r+b') as stream:
        stream.write(new);stream.flush();os.fsync(stream.fileno())
print(json.dumps(dict(cache_tag=args.cache_tag,preserved_blocks=after,route_only_blocks_invalidated=before-after,
                     description='Only this owned simulator trial bitmap changed; immutable data files retained.'),indent=2))
