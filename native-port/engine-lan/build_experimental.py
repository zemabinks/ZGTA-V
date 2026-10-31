#!/usr/bin/env python3
"""Incremental local build of the already staged lab; no installs or downloads."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parent
APP=ROOT.parent/'app'
REPO=ROOT.parents[1]
sys.path.insert(0,str(APP/'Scripts'))
from prepare_shaders import no_symlinks,verify_pair,digest_file
import prepare_experimental as prepare
import social_tables
import inspect_engine_lan as gate


def staged_sources(run):
    app=run/'AppRoot';hashes={}
    for folder in ['Source','App','EngineLAN','Generated','GeneratedResources','GeneratedUIAssets','Resources']:
        for file in sorted((app/folder).rglob('*')):
            if file.is_symlink():raise ValueError('Symlink in staged source')
            if file.is_file():hashes[str(file.relative_to(app))]=digest_file(file)
    for name in ['Build/Online/libmugoat_online.a','project.experimental.json','PlayGTA5Native.xcodeproj/project.pbxproj']:
        hashes[name]=digest_file(app/name)
    # New stages attest the one reviewed vendor patch as a compilation input.
    # Preserved stages retain their original receipt schema for exact reuse.
    stage_record=run/'stage.json'
    if stage_record.is_file():
        if stage_record.is_symlink():raise ValueError('Symlink in staged receipt')
        bcdec=json.loads(stage_record.read_text()).get('bcdec_sign_extension')
        if bcdec is not None:
            patch=prepare.prepare_bcdec
            if not isinstance(bcdec,dict) or bcdec.get('source_sha256')!=patch.SOURCE_SHA256 or bcdec.get('patched_sha256')!=patch.PATCHED_SHA256:
                raise ValueError('Staged BC decoder receipt differs')
            header=app/'Tools/bcdec/bcdec.h'
            no_symlinks(header)
            hashes['Tools/bcdec/bcdec.h']=digest_file(header)
            if hashes['Tools/bcdec/bcdec.h']!=patch.PATCHED_SHA256:
                raise ValueError('Staged BC decoder differs from checked patch')
    return hashes


def validate(run,engine):
    no_symlinks(run)
    if run.parent!=APP.absolute()/'Build':raise ValueError('Use the existing isolated Build child')
    app=run/'AppRoot';verify_pair(app/'GeneratedResources');prepare.verify_ui(app/'GeneratedUIAssets')
    # Current candidates require the checked vendor fix; legacy receipts are
    # accepted only by staged_sources when attesting preserved object reuse.
    if 'bcdec_sign_extension' not in json.loads((run/'stage.json').read_text()):
        raise ValueError('Current candidate lacks checked BC decoder receipt')
    staged_sources(run)
    for file in (app/'EngineLAN').iterdir():
        if file.is_file() and file.read_bytes()!=(ROOT/file.name).read_bytes():raise ValueError('Staged engine source differs: '+file.name)
    for name,patch in [('Source/EngineHost.c',prepare.engine_patch),('Source/NativeAssets.m',prepare.asset_patch),('App/NativePortViewController.swift',prepare.controller_patch)]:
        if (app/name).read_text()!=patch((APP/name).read_text()):raise ValueError('Staged patch differs: '+name)
    special={'Source/EngineHost.c','Source/NativeAssets.m','Source/Native-Bridging-Header.h','App/Info.plist','App/NativePortViewController.swift'}
    for folder in ['Source','App']:
        for file in (APP/folder).rglob('*'):
            relative=str(file.relative_to(APP))
            if file.is_file() and relative not in special:
                expected=prepare.app_patch(file.name,file.read_text()).encode() if folder=='App' and file.suffix=='.swift' else file.read_bytes()
                if expected!=(app/relative).read_bytes():raise ValueError('Staged application source differs: '+relative)
    data=engine.read_bytes();gate.inspect(data,json.loads(gate.CONTRACT.read_text()));types,_,_=gate.module_abi(data)
    h,c,_=social_tables.native(types)
    if (app/'Generated/ZemaSocial.h').read_text()!=h or (app/'Generated/ZemaSocial.c').read_text()!=c:raise ValueError('Generated typed tables differ')
    import native_script_bank
    native_script_bank.verify_generated(data,app/'Generated')
    import world_commands
    cached=REPO.parent/'gta-intel-multiplayer-build-20261016/native-port/app/Generated/MugoatCommands.c'
    if (app/'Generated/MugoatCommands.c').read_text()!=world_commands.patch(cached.read_text(),data,app/'Generated'):
        raise ValueError('Staged world-tool command dispatch differs')
    import gamer_tags
    gamer_tags.verify(data,app/'Generated')
    import engine_safety
    engine_safety.verify_native(app/'Generated')
    import resource_reclaim
    resource_reclaim.verify(app/'Generated',data)
    import open_rpf
    open_rpf.verify_native(app/'Generated')
    import render_hooks
    render_hooks.verify_native(app/'Generated')
    import prepare_stipple_shaders
    prepare_stipple_shaders.verify(app/'GeneratedResources/shader-reflection.jsonl',app/'GeneratedResources')
    return app


def compile_rust(run,toolchain):
    no_symlinks(toolchain)
    if toolchain.parent!=REPO.parent or toolchain.name!='gta-intel-toolchain-20261016':raise ValueError('Use the existing isolated Intel Rust toolchain')
    for path in [toolchain/'cargo/bin/cargo',toolchain/'rustup']:
        if not path.exists():raise ValueError('Existing toolchain is unavailable; do not install')
    env=dict(os.environ,CARGO_HOME=str(toolchain/'cargo'),RUSTUP_HOME=str(toolchain/'rustup'),CARGO_NET_OFFLINE='true',RUSTUP_AUTO_INSTALL='0',IPHONEOS_DEPLOYMENT_TARGET='15.0')
    output=run/'CombinedRust';command=[str(toolchain/'cargo/bin/cargo'),'build','--offline','--locked','--release','--target','aarch64-apple-ios','--manifest-path',str(ROOT.parent/'engine-lan-lab/Cargo.toml'),'--target-dir',str(output)]
    with (run/'combined-rust.log').open('w') as log:subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    library=output/'aarch64-apple-ios/release/libzema_engine_lan_lab.a';shutil.copy2(library,run/'AppRoot/Build/Online/libmugoat_online.a')


def build(run,engine,toolchain,reuse_run=None,reuse_receipt=None,direct=False):
    if subprocess.check_output(['git','status','--porcelain=v1'],cwd=REPO,text=True):raise ValueError('Commit reviewed source before final build')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip();app=validate(run,engine)
    compile_rust(run,toolchain)
    command=['/usr/bin/xcodebuild','-project','PlayGTA5Native.xcodeproj','-scheme','PlayGTA5Native','-configuration','Release','-sdk','iphoneos','-destination','generic/platform=iOS','-derivedDataPath',str(run/'DerivedData'),'-jobs','2','GCC_OPTIMIZATION_LEVEL=2','SWIFT_OPTIMIZATION_LEVEL=-O','DEBUG_INFORMATION_FORMAT=dwarf','CODE_SIGNING_ALLOWED=NO','CODE_SIGN_ENTITLEMENTS=App/Free.entitlements','PRODUCT_BUNDLE_IDENTIFIER=com.zemabinks.gtamp.enginelanlab','CLANG_MODULE_CACHE_PATH='+str(run/'ModuleCache'),'build']
    if json.loads((run/'build-command.json').read_text())!=command:raise ValueError('Build command changed')
    object_cache=None
    if (reuse_run is None)!=(reuse_receipt is None):raise ValueError('Both preserved build and receipt required')
    if reuse_run is not None:
        import reuse_generated
        extra,object_cache=reuse_generated.prepare(run,reuse_run,reuse_receipt,staged_sources,digest_file,direct=direct)
        command[-1:-1]=extra
    before=staged_sources(run);stamp=time.strftime('%Y%m%dT%H%M%S');log=run/('xcodebuild-final-'+stamp+'.log');receipt=run/('build-final-'+stamp+'.json')
    with log.open('x') as output:result=subprocess.run(command,cwd=app,stdout=output,stderr=subprocess.STDOUT)
    logtext=log.read_text(errors='replace')
    if result.returncode==0 and '** BUILD SUCCEEDED **' not in logtext:raise ValueError('Expected Xcode build success marker')
    if any(token in logtext for token in ['CompileMetalFile ', 'CompileAssetCatalog ', 'CompileAssetCatalogVariant ']):raise ValueError('Unexpected shader or asset compilation')
    if before!=staged_sources(run):raise ValueError('Staged inputs changed during build; no successful receipt recorded')
    executable=run/'DerivedData/Build/Products/Release-iphoneos/PlayGTA5Native.app/PlayGTA5Native'
    record={'format':'zema-engine-lan-build-v1','exit_code':result.returncode,'tool_head':head,'log':str(log),'input_hashes':before,'app_executable_sha256':digest_file(executable) if result.returncode==0 else None,'runtime_verified':False,'shader_compilation':False,'original_build_changed':False}
    if object_cache is not None:
        if object_cache.get('link_mode')=='verified-object-filelist':
            if digest_file(Path(object_cache['filelist']))!=object_cache['filelist_sha256']:raise ValueError('Verified linker file list changed during build')
            for unit in object_cache['reused_units']:
                if digest_file(Path(unit['object']))!=unit['object_sha256']:raise ValueError('Reused engine object changed during build')
        elif digest_file(Path(object_cache['library']))!=object_cache['library_sha256']:raise ValueError('Object cache changed during build')
        record['generated_object_reuse']=object_cache
    record['actual_build_command']=command
    receipt.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({'exit_code':result.returncode,'receipt':str(receipt),'log':str(log)}),flush=True)
    return result.returncode

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--engine',type=Path,required=True);p.add_argument('--toolchain',type=Path,required=True);p.add_argument('--reuse-run',type=Path);p.add_argument('--reuse-receipt',type=Path);p.add_argument('--reuse-objects-direct',action='store_true',help='Link individually attested objects without copying them into another archive');a=p.parse_args();os.umask(0o077)
    try:raise SystemExit(build(a.run.absolute(),a.engine,a.toolchain.absolute(),a.reuse_run.absolute() if a.reuse_run else None,a.reuse_receipt.absolute() if a.reuse_receipt else None,a.reuse_objects_direct))
    except (OSError,ValueError,subprocess.CalledProcessError) as e:p.exit(1,str(e)+'\n')
