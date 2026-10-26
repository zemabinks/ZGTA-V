"""Exact user-supplied V + Z icon family, independent of the pinned UI catalog."""
from pathlib import Path
import hashlib,json,shutil,struct
ICON_ROOT=Path(__file__).resolve().parent.parent/'app/Resources/AppIcons'
PHONE=['ZGTAIcon20x20','ZGTAIcon29x29','ZGTAIcon40x40','ZGTAIcon60x60']
IPAD=PHONE+['ZGTAIcon76x76','ZGTAIcon83.5x83.5']

def icon_properties():
    return {key:{'CFBundlePrimaryIcon':{'CFBundleIconFiles':list(names),'UIPrerenderedIcon':True}}
            for key,names in [('CFBundleIcons',PHONE),('CFBundleIcons~ipad',IPAD)]}

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def png_size(path):
    data=Path(path).read_bytes()
    if data[:16]!=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR':raise ValueError('Invalid icon PNG: '+str(path))
    width,height,depth,color=struct.unpack('>IIBB',data[16:26])
    if depth!=8 or color!=2:raise ValueError('App icon must be opaque 8-bit RGB: '+str(path))
    offset=8
    while offset+12<=len(data):
        length=struct.unpack('>I',data[offset:offset+4])[0]
        if data[offset+4:offset+8]==b'tRNS':raise ValueError('Transparent app icon: '+str(path))
        offset+=12+length
    return width,height

def verify_source(root=ICON_ROOT):
    root=Path(root);manifest=json.loads((root/'manifest.json').read_text())
    if manifest['format']!='zgta-app-icons-v1' or manifest['info_properties']!=icon_properties():raise ValueError('App icon declaration differs')
    source=root/manifest['source']
    if digest(source)!=manifest['source_sha256'] or png_size(source)!=(1254,1254):raise ValueError('Supplied icon original differs')
    expected={}
    for points,scales in [('20',[1,2,3]),('29',[1,2,3]),('40',[1,2,3]),('60',[2,3]),('76',[1,2]),('83.5',[2])]:
        for scale in scales:expected['ZGTAIcon'+points+'x'+points+('' if scale==1 else '@'+str(scale)+'x')+'.png']=int(float(points)*scale)
    if set(manifest['files'])!=set(expected):raise ValueError('Incomplete phone/iPad icon family')
    for name,pixels in expected.items():
        file=root/name;row=manifest['files'][name]
        if png_size(file)!=(pixels,pixels) or file.stat().st_size!=row['bytes'] or digest(file)!=row['sha256']:raise ValueError('App icon asset differs: '+name)
    return manifest

def stage_icons(app,root=ICON_ROOT):
    manifest=verify_source(root)
    for name in manifest['files']:shutil.copyfile(Path(root)/name,Path(app)/name)
    return manifest

def verify_icons(app,root=ICON_ROOT):
    manifest=verify_source(root)
    for name,row in manifest['files'].items():
        file=Path(app)/name
        if not file.is_file() or digest(file)!=row['sha256']:raise ValueError('Packaged app icon asset differs: '+name)
    return manifest
