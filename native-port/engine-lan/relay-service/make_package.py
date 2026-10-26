"""Create a small importable ZRemote action package; no install/start side effects."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

HERE=Path(__file__).resolve().parent

def build(output):
    output=output.absolute()
    if output.parent!=HERE.parents[1]/'app/Build' or output.exists() or any(p.is_symlink() for p in (output,*output.parents)):
        raise ValueError('Use a new isolated app Build folder')
    output.mkdir(mode=0o700)
    package=output/'ZGTA-V-Relay-Controls';package.mkdir(mode=0o700)
    for name,source in [('relay.py',HERE.parent/'relay.py'),('service_runner.py',HERE/'service_runner.py'),('relay_control.py',HERE/'relay_control.py')]:
        shutil.copyfile(source,package/name)
    hashes={name:hashlib.sha256((package/name).read_bytes()).hexdigest() for name in ('relay.py','service_runner.py')}
    (package/'payload-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
    actions=[]
    for action,label in [('start','Relay On'),('stop','Relay Off'),('status','Check Status'),('logs','Show Logs')]:
        name=label+'.command'
        (package/name).write_text('#!/bin/zsh\nset -euo pipefail\nROOT="$(cd "$(dirname "$0")" && pwd)"\nexec /usr/bin/python3 -B "$ROOT/relay_control.py" '+action+'\n')
        (package/name).chmod(0o700)
        actions.append({'id':'zgtav.relay.'+action,'label':label,'detail':{'start':'Enable until switched off, including at Mac login. No one-hour timer.','stop':'Stop only the ZGTA V engine relay and disable its login auto-start.','status':'Show actual relay health, current Wi-Fi address and enabled state.','logs':'Show bounded local relay logs.'}[action],'relativePath':name,'role':'generic','risk':'safe' if action in ('status','logs') else 'caution','interactive':False})
    (package/'zremote-control.json').write_text(json.dumps({'schema':2,'id':'com.zema.zgtav.relay.controls.v1','displayName':'ZGTA V — LAN Relay Controls','kind':'generic','version':'1.0.0','autoStartActionID':None,'actions':actions},indent=2)+'\n')
    shutil.copyfile(HERE/'README.md',package/'README.md')
    for path in package.iterdir():
        if path.suffix!='.command':path.chmod(0o600)
    archive=output/'ZGTA-V-Relay-Controls-1.0.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(package.iterdir()):z.write(path,str(path.relative_to(output)))
    return {'package':str(package),'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    print(json.dumps(build(p.parse_args().output),indent=2))
