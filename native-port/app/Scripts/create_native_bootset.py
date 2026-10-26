#!/usr/bin/env python3
"""Build a startup warm set from native demand/prefetch reads of this mirror."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--trace", type=Path, required=True)
parser.add_argument("--manifest", type=Path, default=Path("Resources/manifest.json"))
parser.add_argument("--output", type=Path, default=Path("Resources/bootset_native.json"))
parser.add_argument("--base-bootset", type=Path)
parser.add_argument("--south-central", action="store_true")
parser.add_argument("--world-metadata", action="store_true")
parser.add_argument("--travel-common", action="store_true")
args = parser.parse_args()
manifest = json.loads(args.manifest.read_text())
files = manifest["files"]
ranges = collections.OrderedDict()
reads = 0
with args.trace.open() as stream:
    for row in csv.reader(stream):
        if len(row) != 3:
            continue
        identity, start, length = map(int, row)
        if not 0 <= identity < len(files) or length <= 0:
            continue
        size = int(files[identity][1])
        if start < 0 or start >= size:
            continue
        # Cache entries have 4 KB granularity except for a file's final block.
        end = min(((min(start + length, size) + 4095) // 4096) * 4096, size)
        start = start // 4096 * 4096
        ranges.setdefault(identity, []).append((start, end))
        reads += 1
path_ids = {entry[0]: index for index, entry in enumerate(files)}
if args.base_bootset:
    for path, spans in json.loads(args.base_bootset.read_text()):
        identity = path_ids.get(path)
        if identity is None:
            continue
        size = int(files[identity][1])
        for start, last in spans:
            if 0 <= start <= last and start < size:
                end = min(((min(last + 1, size) + 4095) // 4096) * 4096, size)
                ranges.setdefault(identity, []).append((start // 4096 * 4096, end))
neighborhood_bytes = 0
if args.south_central:
    # The current phone's incoming reads include sc1_24–sc1_29 and adjacent
    # South Central archives. Fetching the complete district also warms later
    # pieces that the recorded startup did not touch, without loading them in RAM.
    for identity, (path, size, *_) in enumerate(files):
        if "/scentral_01/" in path and path.endswith(".rpf"):
            ranges[identity] = [(0, int(size))]
            neighborhood_bytes += int(size)
metadata_bytes = common_bytes = 0
for identity, (path, size, *_) in enumerate(files):
    # Region placement tables are synchronous when the engine enters a new
    # area. The streamed route captured one 54.7 MB placement-table read that
    # spent five seconds fetching 1 MB pieces. Warm every region's table.
    metadata = args.world_metadata and (
        path.startswith('x64/levels/gta5/') and path.endswith('.rpf') and 'instance_placement' in path or
        path.startswith('x64/levels/gta5/navmeshes') and path.endswith('.rpf') or
        path.startswith('x64/levels/gta5/scenario/'))
    common = args.travel_common and (
        path.startswith('x64/models/cdimages/componentpeds') or
        path == 'x64/models/cdimages/pedprops.rpf' or
        path.startswith('x64/anim/ingame/') or
        path in ['x64/levels/gta5/vehicles.rpf', 'x64/levels/gta5/generic/gtxd.rpf'])
    if metadata or common:
        ranges[identity] = [(0, int(size))]
        if metadata: metadata_bytes += int(size)
        if common: common_bytes += int(size)
output = []
total = 0
for identity, reads_for_file in ranges.items():
    merged = []
    for start, end in sorted(reads_for_file):
        if merged and start <= merged[-1][1] + 4096:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    total += sum(end - start for start, end in merged)
    output.append([files[identity][0], [[start, end - 1] for start, end in merged]])
if not output:
    raise SystemExit("No valid native startup reads were recorded")
args.output.write_text(json.dumps(output, separators=(",", ":")) + "\n")
summary = {"version": manifest["version"], "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
           "trace_sha256": hashlib.sha256(args.trace.read_bytes()).hexdigest(), "reads": reads,
           "files": len(output), "ranges": sum(len(item[1]) for item in output), "bytes": total,
           "additional_neighborhood_bytes": neighborhood_bytes,
           "world_metadata_bytes": metadata_bytes,
           "common_travel_bytes": common_bytes,
           "recording": "native game startup and controller movement; demand reads plus engine prefetch hints"}
args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
