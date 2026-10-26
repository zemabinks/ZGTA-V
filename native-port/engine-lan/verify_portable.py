#!/usr/bin/env python3
"""Check an extracted portable package on this host; never claim device gameplay.

Uses an existing read-only mirror and a disposable loopback HTTP listener. No
browser/game is opened, relay started, game data downloaded, or save accessed.
"""
import argparse
import hashlib
import http.client
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import threading
import zipfile

import portable_launcher as integrity


def require(value,message):
    if not value:raise ValueError(message)


def pe_machine(path):
    with path.open('rb') as stream:
        header=stream.read(64);require(header[:2]==b'MZ','Missing Windows executable header')
        stream.seek(struct.unpack_from('<I',header,60)[0]);signature=stream.read(6)
    require(signature[:4]==b'PE\0\0','Missing PE signature')
    return struct.unpack_from('<H',signature,4)[0]


def source_match(manifest,reference):
    require(reference.get('format')=='zgta-source-manifest-v1','Expected published source manifest')
    require(reference.get('original_source_revision')==manifest.get('source_revision'),'Published source revision differs')
    require(reference.get('build')==manifest.get('build'),'Published source build differs')
    require(manifest.get('source_worktree_dirty') is False,'Release package was made from unfinished source')
    sources=manifest.get('source_files');require(isinstance(sources,dict) and bool(sources),'Missing source provenance')
    for target,record in sources.items():
        require(target in manifest['files'] and isinstance(record,dict) and isinstance(record.get('source'),str) and reference.get('files',{}).get(record['source'])==record.get('sha256')==manifest['files'][target],'Packaged source differs from published manifest: '+target)
    for target in manifest['files']:
        if target.startswith(('native-port/','Notices/')):require(target in sources,'Missing package source mapping: '+target)


def verify(package,mirror,source_manifest=None,python_archive=None):
    package=Path(package).resolve(strict=True);mirror=Path(mirror).resolve(strict=True)
    code=package/'native-port/engine-lan'
    # Verify bytes before importing helpers from the extracted package.
    manifest=integrity.verify_package(package)
    source_check='NOT_COMPARED_TO_PUBLISHED_SOURCE_MANIFEST'
    if source_manifest:
        source_match(manifest,json.loads(Path(source_manifest).read_text()));source_check='PASS'
    # Run this verifier as its own process, with the extracted helpers first.
    sys.path.insert(0,str(code))
    import portable_launcher
    import serve_browser as server
    import package_portable
    import launch_channels, graphics_status
    require(Path(server.__file__).parent.resolve()==code,'Verifier imported helpers outside package')
    for name in manifest['files']:
        if name.endswith('.py'):
            path=package/name;compile(path.read_bytes(),name,'exec')
    require(package_portable.checked_runtime(package/'Runtime')==manifest['runtime_provenance'],'Runtime provenance differs')
    portable_launcher.validate_mirror(mirror)
    python_check='NOT_BUNDLED_USES_EXISTING_PYTHON'
    if manifest['platform']=='Windows-x64':
        for name in ('python.exe','pythonw.exe','python313.dll'):
            require(pe_machine(package/'Python'/name)==0x8664,'Windows runtime is not x64: '+name)
        require((package/'Python/python313._pth').read_text()=='python313.zip\n.\n..\n../native-port/engine-lan\n','Embedded Python import path differs')
        python_check='X64_PE_HEADERS_PASS_NOT_EXECUTED'
        if python_archive:
            require(package_portable.sha256(python_archive)==package_portable.PYTHON_SHA,'Official Python archive checksum mismatch')
            with zipfile.ZipFile(python_archive) as archive:
                require(archive.testzip() is None,'Python archive CRC failed')
                names=set(archive.namelist());packaged={p.name for p in (package/'Python').iterdir() if p.is_file()}
                require(names==packaged,'Bundled Python member inventory differs')
                for name in names-{'python313._pth'}:
                    require((package/'Python'/name).read_bytes()==archive.read(name),'Bundled Python differs: '+name)
            python_check='X64_PE_HEADERS_AND_PINNED_ARCHIVE_CONTENT_PASS_NOT_EXECUTED'
    preserved={name:package_portable.sha256(mirror/name) for name in ('index.html','data/manifest.json','data/common/data/dlcList.xml')}
    with tempfile.TemporaryDirectory(prefix='zgta-portable-check-') as folder:
        result=subprocess.run([sys.executable,'-B',str(code/'portable_launcher.py'),'--mirror',str(mirror),'--check','--data',str(Path(folder).resolve()/'private')],capture_output=True,text=True,timeout=180)
        require(result.returncode==0,'Packaged launcher check failed: '+result.stderr[-2000:])
        startup=json.loads(result.stdout)
        content=server.Content(mirror,package/'Runtime')
        listener=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);listener.content=content;listener.daemon_threads=True
        thread=threading.Thread(target=listener.serve_forever,daemon=True);thread.start()
        fetched=[]
        def get(path,headers=None):
            connection=http.client.HTTPConnection('127.0.0.1',listener.server_port,timeout=15)
            try:
                connection.request('GET',path,headers=headers or {});response=connection.getresponse();data=response.read()
                require(response.status in (200,206),'Packaged HTTP failed: '+path)
                require(response.getheader('Cross-Origin-Embedder-Policy')=='require-corp','Missing packaged isolation header')
                require(response.getheader('Cross-Origin-Opener-Policy')=='same-origin','Missing packaged opener header')
                fetched.append(path);return response.status,data
            finally:connection.close()
        try:
            require(get('/')[1]==(code/'launcher.html').read_bytes(),'Packaged launcher bytes differ')
            for name in ('vehicle-catalog.js','vehicle-ui.js','browser-trainer.js','trainer-ui.js','launcher.js','launcher.css'):
                expected=graphics_status.worker(name,launch_channels.worker(name,(code/name).read_bytes()))
                require(get('/zema-lab/'+name)[1]==expected,'Packaged shared UI differs: '+name)
            import mod_previews
            for row in mod_previews.load().values():
                require(get('/zema-lab/'+row['file'])[1]==(mod_previews.RESOURCES/row['file']).read_bytes(),'Packaged mod preview differs')
            for mode in ('lan','story','sandbox'):
                page=get('/play/'+mode)[1]
                require(b'/zema-lab/vehicle-catalog.js' in page and b'/zema-lab/vehicle-ui.js' in page,'Missing packaged vehicle scripts: '+mode)
            for prefix in ('','/offline/story','/offline/sandbox'):
                path=prefix+server.BUILD+'game.wasm' if prefix else server.BUILD+'game.engine-lan.wasm'
                status,raw=get(path,{'Range':'bytes=0-7'})
                require(status==206 and raw==b'\0asm\x01\0\0\0','Packaged engine range/header differs')
            require(content.map_icons.get('active') is True,'Shared modern map icon delta failed to initialize')
        finally:
            listener.shutdown();listener.server_close();thread.join(timeout=5)
            content.lobby_host.close();content.lobby_directory.close()
    for name,want in preserved.items():require(package_portable.sha256(mirror/name)==want,'Read-only mirror changed: '+name)
    return {'format':'zgta-portable-host-validation-v1','platform':manifest['platform'],'build':manifest['build'],'source_revision':manifest['source_revision'],'source_worktree_dirty':manifest['source_worktree_dirty'],'published_source_match':source_check,'host_platform':sys.platform,'package_hashes':'PASS','python_source_syntax':'PASS','runtime_provenance':'PASS','packaged_launcher_initialization':startup,'packaged_http':{'status':'PASS','requests':fetched},'modern_map_icons':'PASS','mirror_preserved':'PASS','windows_runtime':python_check,'physical_platform_execution':'NOT_TESTED','gameplay':'NOT_TESTED','paired_visibility':'NOT_TESTED','fps':'NOT_MEASURED'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package',type=Path,required=True);parser.add_argument('--mirror',type=Path,required=True);parser.add_argument('--source-manifest',type=Path);parser.add_argument('--python-archive',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=verify(args.package,args.mirror,args.source_manifest,args.python_archive)
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))
