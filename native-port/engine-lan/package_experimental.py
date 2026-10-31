#!/usr/bin/env python3
"""Separate TrollStore IPA from a successful exact-input local lab build."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import struct
import subprocess
import sys
import zipfile
ROOT=Path(__file__).resolve().parent
APP=ROOT.parent/'app'
REPO=ROOT.parents[1]
sys.path.insert(0,str(APP/'Scripts'))
from prepare_shaders import no_symlinks,verify_pair,digest_file
from package_trollstore import profile,MEMORY,UI_SHA
from ipa_permissions import normalize_bundle
from prepare_ui_assets import FILES as UI_FILES
from build_experimental import staged_sources
from app_branding import icon_properties,stage_icons,verify_icons
IDENTITY='com.zemabinks.gtamp.enginelanlab'


def package_identity(info,spec):
    """Apply only the staged project's declared user-visible package identity."""
    props=spec['targets']['PlayGTA5Native']['info']['properties']
    result=dict(info)
    for key in ['CFBundleVersion','CFBundleDisplayName','CFBundleShortVersionString']:
        if key not in props:continue
        value=props[key]
        if not isinstance(value,str) or not value or (key=='CFBundleVersion' and not value.isdigit()):
            raise ValueError('Invalid declared package identity: '+key)
        result[key]=value
    if result.get('CFBundleDisplayName')!='ZGTA V':raise ValueError('Expected declared ZGTA V branding')
    for key,expected in icon_properties().items():
        if props.get(key)!=expected:raise ValueError('Missing or changed declared icon metadata: '+key)
        result[key]=copy.deepcopy(expected)
    return result


def verify_packaged_icons(app,info,icons_root=None):
    """Check icon declarations AND their pinned device images before signing."""
    spec={'targets':{'PlayGTA5Native':{'info':{'properties':info}}}}
    if package_identity(info,spec)!=info:raise ValueError('Packaged icon metadata differs')
    for name,(size,sha) in UI_FILES.items():
        path=app/name
        if not path.is_file() or path.stat().st_size!=size or digest_file(path)!=sha:
            raise ValueError('Packaged icon/catalog asset differs: '+name)
    return verify_icons(app) if icons_root is None else verify_icons(app,icons_root)


def package(run,receipt,output_name="Package"):
    no_symlinks(run);no_symlinks(receipt)
    if run.parent!=APP.absolute()/'Build' or receipt.parent!=run:raise ValueError('Use isolated lab build and receipt')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if subprocess.check_output(['git','status','--porcelain=v1'],cwd=REPO,text=True):raise ValueError('Source changed after build')
    record=json.loads(receipt.read_text());app=run/'DerivedData/Build/Products/Release-iphoneos/PlayGTA5Native.app';info=plistlib.loads((app/'Info.plist').read_bytes());executable=app/info['CFBundleExecutable'];stage=run/'AppRoot'
    if info.get('CFBundleIdentifier')!=IDENTITY or info.get('DTPlatformName')!='iphoneos' or info.get('CFBundleExecutable')!='PlayGTA5Native':raise ValueError('Expected the separate iPhone lab app')
    with executable.open('rb') as source:
        if struct.unpack('<II',source.read(8))!=(0xfeedfacf,0x100000c):raise ValueError('Expected ARM64 iPhone executable')
    if record.get('format')!='zema-engine-lan-build-v1' or record.get('exit_code')!=0 or record.get('tool_head')!=head or record.get('app_executable_sha256')!=digest_file(executable) or record.get('input_hashes')!=staged_sources(run):raise ValueError('Successful exact-source build receipt required')
    verify_pair(app)
    import prepare_stipple_shaders
    prepare_stipple_shaders.verify(app/'shader-reflection.jsonl',app)
    if digest_file(app/'Assets.car')!=UI_SHA:raise ValueError('Intel cached device UI catalog differs')
    selected=profile(stage)
    if not re.fullmatch(r'Package(?:-[A-Za-z0-9]+)*',output_name):raise ValueError('Use a separate Package output name')
    output=run/output_name
    if output.exists() or output.is_symlink():raise ValueError('Preserve existing package')
    output.mkdir(mode=0o700);(output/'Payload').mkdir();target=output/'Payload/PlayGTA5Native.app'
    subprocess.run(['/bin/cp','-cR',str(app),str(target)],check=True)
    original_identity={key:info.get(key) for key in ['CFBundleVersion','CFBundleDisplayName','CFBundleShortVersionString']}
    info=package_identity(info,json.loads((stage/'project.experimental.json').read_text()))
    icon_source=stage/'Resources/AppIcons'
    stage_icons(target,icon_source)
    icons=verify_packaged_icons(target,info,icon_source)
    (target/'Info.plist').write_bytes(plistlib.dumps(info))
    licenses=[(REPO/'LICENSE','LICENSE-mugoat.txt'),(ROOT.parent/'LICENSE','LICENSE-native-port.txt'),(stage/'Vendor/LICENSE-libarchive.txt','LICENSE-libarchive.txt'),(stage/'Tools/bcdec/LICENSE','LICENSE-bcdec.txt'),(stage/'Tools/simde/COPYING','LICENSE-simde.txt'),(stage/'Tools/wabt-1.0.42/LICENSE','LICENSE-wabt.txt'),(ROOT/'THIRD_PARTY_NOTICES.md','THIRD_PARTY_NOTICES-glue5.txt')]
    for source,name in licenses:(target/name).write_bytes(source.read_bytes())
    report={'format':'zema-engine-lan-experimental-package-v1','source_revision':head,'bundle_identifier':IDENTITY,'display_name':info.get('CFBundleDisplayName'),'bundle_version':info['CFBundleVersion'],'compiled_bundle_identity':original_identity,'package_identity_source':'AppRoot/project.experimental.json','bundle_copy':'APFS_CLONE_SIGNED_SEPARATELY','entitlements':MEMORY,'shader_inputs':'PINNED_INTEL_PAIR_REUSED','asset_catalog':'PINNED_DEVICE_CACHE_REUSED','app_icons':'SUPPLIED_V_AND_Z_PHONE_AND_IPAD_PASS','icon_source_sha256':icons['source_sha256'],'icon_files':icons['files'],'cost':'No paid service, Apple account or hosted build','runtime':'UNVERIFIED','multiplayer':'UNVERIFIED','saved_character_restart':'UNVERIFIED','memory_grants':'REQUESTED_NOT_DEVICE_VERIFIED','installed':False,'original_ipa_changed':False,'original_intel_folder_changed':False,'build_receipt_sha256':digest_file(receipt)}
    (target/'local-build-info.json').write_text(json.dumps(report,indent=2)+'\n');(target/'zema-build-revision.txt').write_text(head+'\n')
    (output/'Payload').chmod(0o755)
    normalize_bundle(target)
    subprocess.run(['/usr/bin/codesign','--force','--sign','-','--entitlements',str(selected),'--generate-entitlement-der',str(target)],check=True)
    normalize_bundle(target)  # codesign may create _CodeSignature under the private umask
    subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(target)],check=True)
    ent=subprocess.run(['/usr/bin/codesign','-d','--entitlements',':-',str(target)],capture_output=True,check=True).stdout
    if plistlib.loads(ent)!=MEMORY:raise ValueError('Signed entitlements differ')
    (output/'signed-entitlements.plist').write_bytes(ent)
    ipa=output/'zema-EngineLAN-Experimental-Intel-TrollStore.ipa';subprocess.run(['/usr/bin/zip','-qry',str(ipa),'Payload'],cwd=output,check=True)
    with zipfile.ZipFile(ipa) as archive:
        if archive.testzip() is not None or len(archive.namelist())!=len(set(archive.namelist())):raise ValueError('IPA CRC or duplicate paths')
    report.update(ipa=str(ipa),bytes=ipa.stat().st_size,sha256=digest_file(ipa),signature='AD_HOC_STRICT_PASS',archive='CRC_PASS');(output/'package-verification.json').write_text(json.dumps(report,indent=2)+'\n');(output/(ipa.name+'.sha256')).write_text(report['sha256']+'  '+ipa.name+'\n');return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--output-name',default='Package');a=p.parse_args();os.umask(0o077)
    try:print(json.dumps(package(a.run.absolute(),a.receipt.absolute(),a.output_name),indent=2))
    except (OSError,ValueError,KeyError,subprocess.CalledProcessError,zipfile.BadZipFile) as e:p.exit(1,str(e)+'\n')
