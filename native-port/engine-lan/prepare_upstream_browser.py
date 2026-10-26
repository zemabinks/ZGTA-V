"""New renderer-only stage; preserve the reviewed engine, assets and old stage."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import browser_features
from stage_browser import APP

OLD = 'function markDepthDirty(t) { t.proxy_depth && (t.proxy_depth.dirty = true); t.proxy_stencil && (t.proxy_stencil.dirty = true); }'
NEW = 'function markDepthDirty(t, depth = true, stencil = true) { if(depth && t.proxy_depth)t.proxy_depth.dirty=true; if(stencil && t.proxy_stencil)t.proxy_stencil.dirty=true; }'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def worker(original, previous):
    current = browser_features.renderer(original)
    text = current.decode()
    for newer, older in [(NEW, OLD),
                         ('markDepthDirty(dt, !roDepth, hasStencil(dt.format) && !roStencil);',
                          'if (!roDepth && !roStencil) markDepthDirty(dt);')]:
        if text.count(newer) != 1:
            raise ValueError('Expected the reviewed aspect-tracking patch')
        text = text.replace(newer, older)
    if text.encode() != previous:
        raise ValueError('Prior worker differs beyond the reviewed renderer update')
    return current

def stage(previous, output, original):
    previous, output = previous.absolute(), output.absolute()
    root = APP.absolute() / 'Build'
    for path in [previous, output]:
        if path.parent != root or any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Use isolated regular Build children')
    if output.exists() or not previous.is_dir():
        raise ValueError('A preserved stage and new output are required')
    metadata = json.loads((previous / 'browser-stage.json').read_text())
    module = json.loads((previous / 'engine-lan-module.json').read_text())
    if module.get('engine_sha256') != browser_features.ORIGINAL:
        raise ValueError('Unexpected original engine identity')
    for name, sha in metadata['staged_hashes'].items():
        if Path(name).name != name or (previous / name).is_symlink() or digest((previous / name).read_bytes()) != sha:
            raise ValueError('Prior stage changed: ' + name)
    if digest((previous / 'game.engine-lan.wasm').read_bytes()) != module['patched_sha256']:
        raise ValueError('Prior engine bytes changed')
    updated = worker(original.read_bytes(), (previous / 'wgpu_worker.js').read_bytes())
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    subprocess.run(['/bin/cp', '-cRp', str(previous), str(output)], check=True)
    (output / 'wgpu_worker.js').write_bytes(updated)
    metadata['staged_hashes']['wgpu_worker.js'] = digest(updated)
    metadata['renderer_update'] = {'source_head': head, 'previous_worker_sha256': digest((previous / 'wgpu_worker.js').read_bytes()),
        'worker_sha256': digest(updated), 'scope': 'INDEPENDENT_DEPTH_STENCIL_INVALIDATION',
        'engine_changed': False, 'mirror_changed': False, 'runtime_verified': False}
    (output / 'browser-stage.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return metadata['renderer_update']

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--original-worker', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.previous, args.output, args.original_worker), indent=2))
