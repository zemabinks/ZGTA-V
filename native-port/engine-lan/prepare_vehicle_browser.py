"""Append two pure model-query exports to a new clone of reviewed browser66.

No function body, import, index, renderer, save or game-data bytes are changed.
"""
import argparse,hashlib,json,subprocess
from pathlib import Path
import browser_wasm as b
from stage_browser import APP
PINS={'game.engine-lan.wasm':'7c46204042a555e8e9e9660ad3f41504757f059f2b187ebd8cfcf31186c2ba35',
      'game.features.offline.wasm':'5353df47dde7c26b426935ab911dd235362fffbe5576594643125fffbf9ac01e'}
QUERIES=[('IsModelInCdImage','streaming_commands::IsModelInCdImage(int)',60347,'924f85ad408cd3f67c8f371467ec8556e3c692d134901307e933e991eeb91d1e'),
         ('IsModelAVehicle','streaming_commands::CommandIsThisModelAVehicle(int)',60349,'4a081f32abb8e531fcd7c3c39aeed56a7c09f76d8a55783294df3a1e356b1c3e')]
def sha(data):return hashlib.sha256(data).hexdigest()
def transform(data):
    if sha(data) not in PINS.values():raise ValueError('Unreviewed vehicle-probe input')
    types,indices,names=b.gate.module_abi(data);parts=list(b.gate.sections(data));sections=dict(parts)
    reader=b.gate.Reader(sections[3]);functions=[reader.uint() for _ in range(reader.count())];reader.finish()
    imported=len(indices)-len(functions);reader=b.gate.Reader(sections[10]);bodies=[reader.take(reader.uint()) for _ in range(reader.count())];reader.finish()
    for alias,name,index,digest in QUERIES:
        if names.get(name)!=[index] or types[indices[index]]!=(['i32'],['i32']) or sha(bodies[index-imported])!=digest:raise ValueError('Model query name/body/ABI differs: '+alias)
    reader=b.gate.Reader(sections[7]);count=reader.count();old=reader.take(len(sections[7])-reader.pos)
    check=b.gate.Reader(sections[7]);check.count();exports=[]
    for _ in range(count):exports.append((check.text(),check.byte(),check.uint()))
    check.finish()
    if any(n=='zema:features:'+q[0] for n,_,_ in exports for q in QUERIES):raise ValueError('Query exports already present')
    extra=b''.join(b.string('zema:features:'+alias)+b'\x00'+b.leb(index) for alias,_,index,_ in QUERIES)
    output=data[:8]+b''.join(b.section(k,b.leb(count+2)+old+extra if k==7 else raw) for k,raw in parts)
    actual=b.gate.module_abi(output)
    if actual[:2]!=(types,indices):raise ValueError('Function ABI/index moved')
    if [(k,raw) for k,raw in b.gate.sections(output) if k!=7]!=[(k,raw) for k,raw in parts if k!=7]:raise ValueError('Non-export section changed')
    return output

def stage(previous,output):
    root=APP.absolute()/'Build';previous,output=previous.absolute(),output.absolute()
    for p in [previous,output]:
        if p.parent!=root or any(x.is_symlink() for x in [p,*p.parents]):raise ValueError('Use regular isolated Build children')
    if output.exists():raise ValueError('Preserve earlier stages')
    manifest=json.loads((previous/'browser-stage.json').read_text());module=json.loads((previous/'engine-lan-module.json').read_text());offline_helper=(previous/'browser-features-module.js').read_text();prefix='globalThis.ZemaBrowserFeaturesModule=';
    if not offline_helper.startswith(prefix) or not offline_helper.endswith(';\n'):raise ValueError('Offline metadata helper shape differs')
    offline=json.loads(offline_helper[len(prefix):-2])
    for name,want in manifest['staged_hashes'].items():
        if Path(name).name!=name or (previous/name).is_symlink() or sha((previous/name).read_bytes())!=want:raise ValueError('Prior stage differs: '+name)
    for name,prefix,meta in [('engine-lan-module.js','globalThis.ZemaEngineLanModule=',module),('browser-features-module.js','globalThis.ZemaBrowserFeaturesModule=',offline)]:
        if (previous/name).read_text()!=prefix+json.dumps(meta)+';\n':raise ValueError('Prior metadata helper differs')
    transformed={name:transform((previous/name).read_bytes()) for name in PINS}
    module['patched_sha256']=sha(transformed['game.engine-lan.wasm']);module['features']['patched_sha256']=module['patched_sha256'];offline['patched_sha256']=sha(transformed['game.features.offline.wasm'])
    for meta in [module['features'],offline]:
        for alias,_,index,_ in QUERIES:meta['exports'][alias]={'index':index,'params':['i32'],'results':['i32']}
    updates={**transformed,'engine-lan-module.json':(json.dumps(module)+'\n').encode(),'engine-lan-module.js':('globalThis.ZemaEngineLanModule='+json.dumps(module)+';\n').encode(),'browser-features-module.js':('globalThis.ZemaBrowserFeaturesModule='+json.dumps(offline)+';\n').encode(),'browser-trainer.js':(Path(__file__).parent/'browser-trainer.js').read_bytes()}
    subprocess.run(['/bin/cp','-cRp',str(previous),str(output)],check=True)
    for name,data in updates.items():
        (output/name).write_bytes(data)
        if name in manifest['staged_hashes']:manifest['staged_hashes'][name]=sha(data)
    record={'format':'zgta-vehicle-query-exports-v1','previous':str(previous),'input_engines':PINS,'output_engines':{n:sha(v) for n,v in transformed.items()},'function_bodies_indices_imports_unchanged':True,'renderer_saves_mirror_unchanged':True,'read_only_queries':[q[0] for q in QUERIES],'runtime_verified':False}
    manifest['vehicle_availability']=record;(output/'browser-stage.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return record
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--previous',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(stage(a.previous,a.output),indent=2))
