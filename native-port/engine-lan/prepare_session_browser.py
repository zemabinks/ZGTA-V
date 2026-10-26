"""Extend reviewed browser67 in a new stage; no engine body or game data edits."""
import argparse,hashlib,json,subprocess
from pathlib import Path
import browser_wasm as b
import session_restart as restart
from stage_browser import APP
ROOT=Path(__file__).resolve().parent
INPUT='9b71157daa37dcec25541fe8ab354f34ffc0a6704a94683b95136cfb7f4eb030'
def sha(data):return hashlib.sha256(data).hexdigest()
def transform(data):
    if sha(data)!=INPUT:raise ValueError('Unreviewed direct-restart input')
    types,indices,names=b.gate.module_abi(data);restart.validate_abi(types,indices,names)
    parts=list(b.gate.sections(data));exports=dict(parts)[7];r=b.gate.Reader(exports);count=r.count();old=r.take(len(exports)-r.pos)
    extra=b''.join(b.string('zema:features:'+alias)+b'\0'+b.leb(index)for alias,name,index,params,results in restart.COMMANDS)
    output=data[:8]+b''.join(b.section(k,b.leb(count+len(restart.COMMANDS))+old+extra if k==7 else raw)for k,raw in parts)
    if b.gate.module_abi(output)[:2]!=(types,indices):raise ValueError('Existing ABI changed')
    if [(k,v)for k,v in b.gate.sections(output)if k!=7]!=[(k,v)for k,v in parts if k!=7]:raise ValueError('Engine body or other section changed')
    return output

def stage(previous,output):
    if previous.is_symlink()or output.exists()or output.parent!=APP/'Build':raise ValueError('A new isolated Build child is required')
    receipt=json.loads((previous/'browser-stage.json').read_text());metadata=json.loads((previous/'engine-lan-module.json').read_text())
    for name,digest in receipt['staged_hashes'].items():
        if Path(name).name!=name or sha((previous/name).read_bytes())!=digest:raise ValueError('Previous stage changed: '+name)
    data=(previous/'game.engine-lan.wasm').read_bytes()
    if metadata['patched_sha256']!=sha(data):raise ValueError('Input metadata changed')
    patched=transform(data);output.mkdir(mode=0o700);subprocess.run(['/bin/cp','-cR',str(previous)+'/.',str(output)],check=True)
    metadata['patched_sha256']=sha(patched);features=metadata['features'];features['patched_sha256']=sha(patched);features['session_restart']=restart.CONTRACT
    features['exports'].update({alias:{'index':index,'params':params,'results':results}for alias,name,index,params,results in restart.COMMANDS})
    for name in ['session-restart.js','browser-features.js','engine-lan-browser.js']:
        source=ROOT/('browser.js'if name=='engine-lan-browser.js'else name);(output/name).write_bytes(source.read_bytes())
    for name in ['game.js','loader.js']:
        p=output/name;text=p.read_text();p.write_text("importScripts(new URL('session-restart.js',self.location.href).href);\n"+text)
    (output/'game.engine-lan.wasm').write_bytes(patched)
    (output/'engine-lan-module.json').write_text(json.dumps(metadata)+'\n');(output/'engine-lan-module.js').write_text('globalThis.ZemaEngineLanModule='+json.dumps(metadata)+';\n')
    receipt['staged_hashes'].update({name:sha((output/name).read_bytes())for name in ['session-restart.js','browser-features.js','engine-lan-browser.js','game.js','loader.js','engine-lan-module.js']})
    receipt['direct_session_restart']={'previous':str(previous),'input':INPUT,'output':sha(patched),'contract':restart.CONTRACT,'engine_bodies_unchanged':True,'menu_input':False,'runtime_verified':False}
    (output/'browser-stage.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt['direct_session_restart']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--previous',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();print(json.dumps(stage(a.previous.absolute(),a.output.absolute()),indent=2))
