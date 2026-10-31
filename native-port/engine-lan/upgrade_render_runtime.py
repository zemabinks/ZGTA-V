"""Upgrade an authenticated Build97 runtime in a new private Build directory.

The full source route applies prepare_render_browser after the existing
feature, safety and OPEN-RPF stages. This
bounded route reuses a preserved portable archive, with the same final bytes,
without rebuilding or copying game assets and without changing old packages.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile
import package_portable
import render_hooks
import render_performance
import stipple_gpu

APP = Path(__file__).resolve().parents[1]/'app'
WORKER97 = '615aac613ff798f3b953b102cf33194e0df42c929d31b58f829e40ff2b36c9c5'
WORKER98 = '321a83b99ee4ad41b48e12a2e96432f614ee4cfaeb6972f2434081c655fa8eba'
WORKER103 = 'eb37e248e5ec3dd9579ec12a82c64032e18c32b1dd1ff95a8647c44481a9454f'


def stage(archive, output):
    output = output.absolute()
    if output.parent != APP.absolute()/'Build' or output.exists() or any(p.is_symlink() for p in (output,*output.parents)):
        raise ValueError('A new isolated regular app Build output is required')
    with zipfile.ZipFile(archive) as source:
        names = [n for n in source.namelist() if n.startswith('ZGTA-V/Runtime/') and not n.endswith('/')]
        files = {}
        for name in names:
            local = name.removeprefix('ZGTA-V/Runtime/')
            if '/' in local or '\\' in local or local in files: raise ValueError('Unexpected runtime archive path')
            files[local] = source.read(name)
        manifest = json.loads(source.read('ZGTA-V/portable-manifest.json'))
        if manifest['build'] != 97: raise ValueError('Expected preserved Build97 package')
        for name,data in files.items():
            if hashlib.sha256(data).hexdigest() != manifest['files']['Runtime/'+name]: raise ValueError('Prior package bytes changed: '+name)
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        for name,data in files.items(): (base/name).write_bytes(data)
        package_portable.checked_runtime(base)
    return write_stage(transform_files(files),output)


def transform_files(files):
    files=dict(files)
    worker_sha=hashlib.sha256(files['wgpu_worker.js']).hexdigest()
    if worker_sha == WORKER98: raise ValueError('Legacy fade worker requires authenticated prepare_fade_browser103 regeneration')
    if worker_sha not in (WORKER97,WORKER103): raise ValueError('Unreviewed worker input')
    metadata = json.loads(files['engine-lan-module.json'])
    offline_meta = json.loads(files['browser-features-module.js'].decode().removeprefix('globalThis.ZemaBrowserFeaturesModule=').removesuffix(';\n'))
    for name,features in [('game.features.offline.wasm',offline_meta),('game.engine-lan.wasm',metadata['features'])]:
        files[name],features['render_hooks'] = render_hooks.append(files[name])
        features['patched_sha256'] = hashlib.sha256(files[name]).hexdigest()
    metadata['patched_sha256'] = metadata['features']['patched_sha256']
    if worker_sha==WORKER97:
        files['wgpu_worker.js'] = stipple_gpu.apply(render_performance.apply(files['wgpu_worker.js'].decode())).encode()
    if hashlib.sha256(files['wgpu_worker.js']).hexdigest()!=WORKER103: raise ValueError('Render worker output differs')
    files['engine-lan-module.json'] = (json.dumps(metadata)+'\n').encode()
    files['engine-lan-module.js'] = ('globalThis.ZemaEngineLanModule='+json.dumps(metadata)+';\n').encode()
    files['browser-features-module.js'] = ('globalThis.ZemaBrowserFeaturesModule='+json.dumps(offline_meta)+';\n').encode()
    record = json.loads(files['browser-stage.json'])
    # Match the full feature-stage convention: engine SHA is in module metadata.
    record['staged_hashes'] = {name:hashlib.sha256(data).hexdigest() for name,data in files.items()
                             if name not in ('browser-stage.json','engine-lan-module.json','game.engine-lan.wasm')}
    record['runtime_verified'] = False
    record['render_performance'] = {'build':103,'baseline_build':97,'worker_input_sha256':worker_sha,
                                    'official_public_source_promotion':'DENIED_PENDING_OWNER_TESTS_AND_BUILD_CHOICE'}
    files['browser-stage.json'] = (json.dumps(record,indent=2)+'\n').encode()
    return files


def write_stage(files,output):
    output.parent.mkdir(exist_ok=True)
    output.mkdir(mode=0o700)
    for name,data in files.items(): (output/name).write_bytes(data)
    proof = package_portable.checked_runtime(output)
    return {'output':str(output),'runtime_provenance':proof,'runtime_verified':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(stage(a.archive,a.output),indent=2))
