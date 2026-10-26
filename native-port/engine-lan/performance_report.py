"""Summarize existing browser timing lines without running or changing a game.

Input is the bounded local diagnostics JSON. No device/user addresses, raw log
text or character data are copied to the resulting report. Worker busy time is
CPU-side command processing, not measured GPU hardware utilization.
"""
import argparse
import json
from pathlib import Path
import re
import statistics

FPS = re.compile(r'\[wgpu\] fps: ([\d.]+).*worker busy (\d+)% \(([\d.]+) ms/frame\)')

def summarize(data):
    # Unique signal entries survive an audio-warning flood. The collector moves
    # each updated entry to the end; these are the last observed timing windows.
    source = [r.get('text','') for r in data.get('signals',[]) if isinstance(r,dict)]
    if not source: source = data.get('lines',[])
    samples=[]
    for text in source:
        if not isinstance(text,str): continue
        m=FPS.search(text)
        if not m:continue
        fps,busy,work=map(float,m.groups())
        if 0 < fps <= 1000 and 0 <= busy <= 100 and 0 <= work <= 10000:
            samples.append(dict(fps=fps,worker_busy_percent=busy,worker_cpu_ms_per_frame=work))
    samples=samples[-30:]
    report={'scope':'last recorded browser timing windows; not a new benchmark',
            'samples':len(samples),'gpu_hardware_time_measured':False,
            'settings_comparison_controlled':False}
    if samples:
        report.update(fps_min=min(s['fps'] for s in samples),fps_median=statistics.median(s['fps'] for s in samples),
                      fps_max=max(s['fps'] for s in samples),
                      worker_cpu_ms_median=statistics.median(s['worker_cpu_ms_per_frame'] for s in samples),
                      worker_busy_percent_median=statistics.median(s['worker_busy_percent'] for s in samples))
    report['next_measurement']='Use the validated four-worker budget. Compare the same visible scene with a 60 FPS cap at 540p and 432p; record the actual adapter and distinguish cap-limited results from frame drops.'
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('diagnostics',type=Path);a=p.parse_args()
    print(json.dumps(summarize(json.loads(a.diagnostics.read_text())),indent=2))
