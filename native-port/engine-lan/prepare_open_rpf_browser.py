"""Apply the shared OPEN RPF correction to a new verified browser stage."""
import argparse
import json
from pathlib import Path
import subprocess

import open_rpf
from stage_browser import APP


def stage(previous, output):
    if previous.is_symlink() or output.exists() or output.parent != APP / 'Build':
        raise ValueError('A new isolated Build child is required')
    manifest = json.loads((previous / 'browser-stage.json').read_text())
    metadata = json.loads((previous / 'engine-lan-module.json').read_text())
    for name, digest in manifest['staged_hashes'].items():
        if Path(name).name != name or (previous/name).is_symlink() or open_rpf.sha((previous/name).read_bytes()) != digest:
            raise ValueError('Previous stage changed: ' + name)
    if open_rpf.sha((previous/'game.engine-lan.wasm').read_bytes()) != metadata['patched_sha256']:
        raise ValueError('Previous engine metadata changed')
    patched = {}
    records = {}
    for name in ['game.engine-lan.wasm', 'game.features.offline.wasm']:
        patched[name], records[name] = open_rpf.transform((previous/name).read_bytes())
    output.mkdir(mode=0o700)
    subprocess.run(['/bin/cp', '-cR', str(previous) + '/.', str(output)], check=True)
    for name, data in patched.items():
        (output/name).write_bytes(data)
    metadata['patched_sha256'] = records['game.engine-lan.wasm']['patched_sha256']
    metadata['features'].update(patched_sha256=metadata['patched_sha256'], open_rpf=records['game.engine-lan.wasm'])
    (output/'engine-lan-module.json').write_text(json.dumps(metadata)+'\n')
    (output/'engine-lan-module.js').write_text('globalThis.ZemaEngineLanModule='+json.dumps(metadata)+';\n')
    # The separate offline feature descriptor shares the same export metadata.
    descriptor=output/'browser-features-module.js'
    text=descriptor.read_text()
    prefix='globalThis.ZemaBrowserFeaturesModule='
    if not text.startswith(prefix) or not text.rstrip().endswith(';'):
        raise ValueError('Offline feature descriptor changed')
    offline=json.loads(text[len(prefix):].strip()[:-1])
    old=open_rpf.sha((previous/'game.features.offline.wasm').read_bytes())
    if offline['patched_sha256'] != old:
        raise ValueError('Offline feature descriptor changed')
    offline.update(patched_sha256=records['game.features.offline.wasm']['patched_sha256'],open_rpf=records['game.features.offline.wasm'])
    descriptor.write_text(prefix+json.dumps(offline)+';\n')
    for name in ['game.engine-lan.wasm','game.features.offline.wasm','engine-lan-module.js','browser-features-module.js']:
        manifest['staged_hashes'][name] = open_rpf.sha((output/name).read_bytes())
    manifest['open_rpf']={'previous':str(previous),'modules':records,'runtime_verified':False}
    (output/'browser-stage.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest['open_rpf']


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(stage(args.previous.absolute(),args.output.absolute()),indent=2))
