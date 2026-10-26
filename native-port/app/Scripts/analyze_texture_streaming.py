#!/usr/bin/env python3
"""Relate native texture decode/upload costs to world frames, without attributing causality."""
import argparse
import collections
import csv
import json
import statistics
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('run',type=Path)
a=p.parse_args()

def percentile(values,fraction):
    if not values:return None
    ordered=sorted(values)
    return ordered[min(len(ordered)-1,int(len(ordered)*fraction))]

def timing(values):
    return dict(calls=len(values),total_ms=sum(values),median_ms=statistics.median(values) if values else None,p95_ms=percentile(values,.95),p99_ms=percentile(values,.99),max_ms=max(values) if values else None)

with (a.run/'renderer-frames.csv').open() as f:
    frames=[{key:float(value) for key,value in row.items()} for row in csv.DictReader(f) if row['world']=='1']
with (a.run/'native-texture-timings.csv').open() as f:
    textures=[{key:float(value) for key,value in row.items()} for row in csv.DictReader(f)]
if not frames:raise RuntimeError('No world frames')
records=len(textures)
last_record=max((row['start_ms'] for row in textures),default=0)
textures=[row for row in textures if frames[0]['time_ms']-frames[0]['frame_ms']<=row['start_ms']<=frames[-1]['time_ms']]
textures.sort(key=lambda row:row['start_ms'])
by_format=collections.defaultdict(list)
for t in textures:
    if t['decode']:by_format['BC'+str(int(t['format']))].append(t['duration_ms'])
index=0
for frame in frames:
    start,end=frame['time_ms']-frame['frame_ms'],frame['time_ms']
    while index<len(textures) and textures[index]['start_ms']+textures[index]['duration_ms']<start:index+=1
    frame.update(decode_ms=0,upload_ms=0,compressed_bytes=0,uploaded_bytes=0)
    current=index
    while current<len(textures) and textures[current]['start_ms']<=end:
        t=textures[current];overlap=max(0,min(end,t['start_ms']+t['duration_ms'])-max(start,t['start_ms']))
        frame['decode_ms' if t['decode'] else 'upload_ms']+=overlap
        if start<=t['start_ms']<=end:frame['compressed_bytes' if t['decode'] else 'uploaded_bytes']+=t['bytes']
        current+=1
loading=[f for f in frames if f['uploaded_bytes']>=65536]
result=dict(texture_records=records,profile_record_limit_reached=records>=1000000 or records==200000,last_texture_record_ms=last_record,hardware='Mac iOS simulator; not a phone measurement',world_texture_decodes=timing([t['duration_ms'] for t in textures if t['decode']]),world_texture_uploads=timing([t['duration_ms'] for t in textures if not t['decode']]),formats={k:timing(v) for k,v in by_format.items()},uploaded_world_bytes=sum(t['bytes'] for t in textures if not t['decode']),decoded_world_bytes=sum(t['bytes'] for t in textures if t['decode']),loading_frames=dict(threshold_uploaded_bytes=65536,frames=len(loading),average_fps=1000/statistics.mean(f['frame_ms'] for f in loading) if loading else None,p95_frame_ms=percentile([f['frame_ms'] for f in loading],.95),p99_frame_ms=percentile([f['frame_ms'] for f in loading],.99),frames_over_33_33_ms=sum(f['frame_ms']>1000/30 for f in loading),decode_ms=sum(f['decode_ms'] for f in loading),upload_ms=sum(f['upload_ms'] for f in loading)),worst_texture_frames=sorted(frames,key=lambda f:f['decode_ms']+f['upload_ms'],reverse=True)[:20],interpretation='Frame overlap is correlation. Decode and upload totals reflect synchronous native texture work; loading-frame FPS is a subset, not the engine benchmark average.')
(a.run/'texture-summary.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='worst_texture_frames'},indent=2))
