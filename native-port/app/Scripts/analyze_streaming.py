#!/usr/bin/env python3
"""Match native asset timings to simulator frame gaps using one uptime clock."""
import argparse
import csv
import json
from pathlib import Path
import statistics

parser = argparse.ArgumentParser()
parser.add_argument('run', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'Resources/manifest.json').read_text())['files']
with (args.run / 'renderer-frames.csv').open() as stream:
    frames = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(stream) if row['world'] == '1']
with (args.run / 'native-asset-timings.csv').open() as stream:
    reads = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(stream)]
if not frames:
    raise SystemExit('No world frame timings were captured')
world_start = frames[0]['time_ms'] - frames[0]['frame_ms']
world_end = frames[-1]['time_ms']
world_reads = [r for r in reads if r['end_ms'] >= world_start and r['start_ms'] <= world_end]
demand = [r for r in world_reads if not r['prefetch']]
network = [r for r in world_reads if r['network_bytes']]
stalls = []
for frame in sorted((f for f in frames if f['frame_ms'] >= 100), key=lambda f: f['frame_ms'], reverse=True):
    start, end = frame['time_ms'] - frame['frame_ms'], frame['time_ms']
    # Coinciding asset reads identify candidates, not proof of causation. GPU
    # uploads/decode/engine work may share the same interval.
    overlap = [r for r in demand if r['end_ms'] > start and r['start_ms'] < end]
    slow = sorted(overlap, key=lambda r: r['end_ms'] - r['start_ms'], reverse=True)[:5]
    stalls.append(dict(end_ms=end, frame_ms=frame['frame_ms'], draws=int(frame['draws']),
                      demand_reads=len(overlap), network_bytes=sum(int(r['network_bytes']) for r in overlap),
                      slow_reads=[dict(path=manifest[int(r['id'])][0], duration_ms=r['end_ms']-r['start_ms'],
                                       network_ms=r['network_ms'], lock_ms=r['lock_ms'], bytes=int(r['network_bytes'])) for r in slow]))
durations = [r['end_ms'] - r['start_ms'] for r in demand]
ordered = sorted(durations)
summary = dict(hardware='Mac iOS simulator with streaming; not a phone measurement',
               world_frames=len(frames), world_duration_s=(world_end-world_start)/1000,
               frame_gaps={str(t)+'ms': sum(f['frame_ms'] >= t for f in frames) for t in [100,250,500,1000]},
               worst_frame_ms=max(f['frame_ms'] for f in frames),
               world_asset_reads=len(world_reads), world_demand_reads=len(demand),
               world_network_reads=len(network), world_network_mb=sum(r['network_bytes'] for r in network)/1048576,
               demand_read_median_ms=statistics.median(durations) if durations else 0,
               demand_read_p95_ms=ordered[min(len(ordered)-1,int(len(ordered)*.95))] if ordered else 0,
               demand_read_max_ms=max(durations,default=0),
               demand_lock_wait_total_ms=sum(r['lock_ms'] for r in demand),
               failed_reads=sum(r['result'] < 0 for r in reads),
               all_network_mb=sum(r['network_bytes'] for r in reads)/1048576,
               interpretation='Read/frame overlap is correlation. A paired cached run helps separate network waits from texture upload, shader and engine work.',
               worst_stalls=stalls[:25])
(args.run / 'streaming-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='worst_stalls'},indent=2))
