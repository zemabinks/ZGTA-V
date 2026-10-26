"""Clone a successful native stage and apply current source before full validation.

Avoid rewriting identical generated engine translation units on a nearly full
APFS volume. The successful source receipt and executable are checked first;
the regular final-build validator still checks the complete resulting stage.
"""
import argparse,json,subprocess,shutil
from pathlib import Path
import build_experimental as build
import prepare_experimental as prepare
from prepare_shaders import digest_file,no_symlinks

def stage(previous,receipt,output,engine):
    no_symlinks(previous);no_symlinks(output.parent)
    if previous.parent!=build.APP.absolute()/'Build' or output.parent!=previous.parent or output.exists() or receipt.parent!=previous:
        raise ValueError('Distinct new isolated stage and successful receipt required')
    proof=json.loads(receipt.read_text())
    if proof.get('format')!='zema-engine-lan-build-v1' or proof.get('exit_code')!=0 or proof.get('input_hashes')!=build.staged_sources(previous):
        raise ValueError('Preserved source receipt differs')
    binary=previous/'DerivedData/Build/Products/Release-iphoneos/PlayGTA5Native.app/PlayGTA5Native'
    if digest_file(binary)!=proof['app_executable_sha256']:raise ValueError('Preserved executable differs')
    subprocess.run(['git','merge-base','--is-ancestor',proof['tool_head'],'HEAD'],cwd=build.REPO,check=True)
    output.mkdir(mode=0o700);app=output/'AppRoot';prepare.clone(previous/'AppRoot',app)
    for folder in ['Source','App','Resources','Scripts','IntelInputs']:shutil.copytree(build.APP/folder,app/folder,dirs_exist_ok=True)
    for name,patch in [('Source/EngineHost.c',prepare.engine_patch),('Source/NativeAssets.m',prepare.asset_patch),('App/NativePortViewController.swift',prepare.controller_patch)]:
        (app/name).write_text(patch((build.APP/name).read_text()))
    for p in (app/'App').glob('*.swift'):
        if p.name!='NativePortViewController.swift':p.write_text(prepare.app_patch(p.name,p.read_text()))
    for p in (app/'EngineLAN').iterdir():
        if p.is_file():shutil.copy2(prepare.ROOT/p.name,p)
    (app/'Source/Native-Bridging-Header.h').open('a').write('\n#include "ZemaExperimental.h"\n')
    import resource_reclaim
    resource_reclaim.stage(app/'Generated',engine.read_bytes())
    import open_rpf
    if open_rpf.C_GUARD in (app/'Generated/game_1.c').read_text():
        open_rpf.verify_native(app/'Generated')
    else:
        open_rpf.stage_native(app/'Generated')
    # Regenerate Info.plist from the current declared project. Preserving an old
    # template here lost the icon dictionaries and left stale build branding.
    specfile=app/'project.experimental.json'
    spec=prepare.configure_identity(json.loads(specfile.read_text()))
    specfile.write_text(json.dumps(spec,indent=2)+'\n')
    subprocess.run(['/usr/local/bin/xcodegen','generate','--spec',str(specfile)],cwd=app,check=True)
    # Validate before describing this as a complete stage. This checks current
    # typed dispatch, generated hooks, shaders, UI inputs and source transforms.
    build.validate(output,engine)
    metadata=json.loads((previous/'stage.json').read_text());metadata.update(app_root=str(app),runtime_verified=False,cloned_from_verified_build=str(previous),verified_build_receipt_sha256=digest_file(receipt))
    metadata['open_rpf']={'format':'zgta-open-rpf-v1','index':open_rpf.INDEX,'original_body_sha256':open_rpf.C_SHA,'scope':'OPEN_PLAINTEXT_TABLES_ONLY','archive_bytes_changed':False,'runtime_verified':False}
    (output/'stage.json').write_text(json.dumps(metadata,indent=2)+'\n')
    command=json.loads((previous/'build-command.json').read_text());(output/'build-command.json').write_text(json.dumps([x.replace(str(previous),str(output))for x in command],indent=2)+'\n')
    prepare.clone(previous/'DerivedData',output/'DerivedData')
    return {'output':str(output),'validated':True,'runtime_verified':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--previous',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--engine',type=Path,required=True);a=p.parse_args();print(json.dumps(stage(a.previous.absolute(),a.receipt.absolute(),a.output.absolute(),a.engine.absolute())))
