"""Append reviewed engine guards into a new stage; preserve previous outputs."""
import argparse
import json
from pathlib import Path
import subprocess
import engine_safety
from stage_browser import APP

def stage(previous, output):
    if subprocess.check_output(['git','status','--porcelain=v1'],text=True):
        raise ValueError('Commit reviewed source before staging a release candidate')
    previous, output = previous.absolute(), output.absolute()
    for path in [previous, output]:
        if path.parent != APP.absolute()/'Build' or any(p.is_symlink() for p in (path,*path.parents)):
            raise ValueError('Use isolated regular Build children')
    if output.exists() or not previous.is_dir():
        raise ValueError('Use a preserved input and new output')
    manifest=json.loads((previous/'browser-stage.json').read_text())
    module=json.loads((previous/'engine-lan-module.json').read_text())
    offline=json.loads((previous/'browser-features-offline.json').read_text())
    for name,prefix,value in [('engine-lan-module.js','globalThis.ZemaEngineLanModule=',module),
                              ('browser-features-module.js','globalThis.ZemaBrowserFeaturesModule=',offline)]:
        if (previous/name).read_text()!=prefix+json.dumps(value)+';\n':
            raise ValueError('Preserved metadata helper changed: '+name)
    for name,digest in manifest['staged_hashes'].items():
        if Path(name).name!=name or (previous/name).is_symlink() or engine_safety.sha((previous/name).read_bytes())!=digest:
            raise ValueError('Preserved input changed: '+name)
    lan_input=(previous/'game.engine-lan.wasm').read_bytes()
    if engine_safety.sha(lan_input)!=module['patched_sha256']:
        raise ValueError('Preserved LAN engine changed')
    offline_input=(previous/'game.features.offline.wasm').read_bytes()
    if engine_safety.sha(offline_input)!=offline['patched_sha256']:
        raise ValueError('Preserved offline engine changed')
    offline_bytes,offline_record=engine_safety.transform(offline_input)
    lan_bytes,lan_record=engine_safety.transform(lan_input)
    module['patched_sha256']=lan_record['patched_sha256']
    module['features'].update(patched_sha256=lan_record['patched_sha256'],engine_safety=lan_record)
    offline.update(patched_sha256=offline_record['patched_sha256'],engine_safety=offline_record)
    changed={'game.engine-lan.wasm':lan_bytes,'game.features.offline.wasm':offline_bytes,
             'engine-lan-module.json':(json.dumps(module)+'\n').encode(),
             'browser-features-offline.json':(json.dumps(offline)+'\n').encode(),
             'engine-lan-module.js':('globalThis.ZemaEngineLanModule='+json.dumps(module)+';\n').encode(),
             'browser-features-module.js':('globalThis.ZemaBrowserFeaturesModule='+json.dumps(offline)+';\n').encode()}
    subprocess.run(['/bin/cp','-cRp',str(previous),str(output)],check=True)
    for name,data in changed.items():
        (output/name).write_bytes(data)
        if name in manifest['staged_hashes']:manifest['staged_hashes'][name]=engine_safety.sha(data)
    manifest['engine_safety']={'source_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'offline':offline_record,'lan':lan_record,'original_files_changed':False,'runtime_verified':False}
    (output/'browser-stage.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest['engine_safety']

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(stage(args.previous,args.output),indent=2))
