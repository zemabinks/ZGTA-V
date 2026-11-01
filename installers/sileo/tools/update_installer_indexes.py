#!/usr/bin/env python3
"""Update only our installer stanzas; retain existing package metadata exactly."""
import bz2,gzip,hashlib,lzma
from datetime import datetime,timezone
from email.utils import format_datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
INSTALLERS={'com.zema.zgta-v.trollstore':'all','com.zema.zgta-v.appsync':'iphoneos-arm'}
def update():
    existing=(ROOT/'Packages').read_text()
    def identity(stanza):
        fields=dict(line.split(': ',1) for line in stanza.splitlines() if ': ' in line)
        return tuple(fields[key] for key in ('Package','Version','Architecture'))
    # Keep exact earlier versions available to Sileo's selected/cached packages.
    # An idempotent rebuild replaces only the same id, version and architecture.
    current={identity((ROOT/f'package-sources/{flavor}-installer/control').read_text().strip())
             for flavor in ('trollstore','appsync')}
    retained=[s for s in existing.strip().split('\n\n') if identity(s) not in current]
    stanzas=[]
    for package,arch in INSTALLERS.items():
        flavor='appsync' if package.endswith('.appsync') else 'trollstore'
        control=(ROOT/f'package-sources/{flavor}-installer/control').read_text().strip()
        fields=dict(line.split(': ',1) for line in control.splitlines())
        assert fields['Package']==package and fields['Architecture']==arch
        filename=f"pool/{package}_{fields['Version']}_{arch}.deb";data=(ROOT/filename).read_bytes()
        checksum=''.join(f'{field}: {hashlib.new(algo,data).hexdigest()}\n' for field,algo in [('MD5sum','md5'),('SHA1','sha1'),('SHA256','sha256'),('SHA512','sha512')])
        stanzas.append(control+f'\nFilename: ./{filename}\nSize: {len(data)}\n'+checksum.rstrip())
    data=('\n\n'.join(retained+stanzas)+'\n\n').encode();(ROOT/'Packages').write_bytes(data)
    (ROOT/'Packages.gz').write_bytes(gzip.compress(data,compresslevel=9,mtime=0))
    (ROOT/'Packages.bz2').write_bytes(bz2.compress(data));(ROOT/'Packages.xz').write_bytes(lzma.compress(data))
    header="Origin: Zema's Repo\nLabel: Zema's Repo\nSuite: stable\nCodename: ios\nVersion: 1.0\nArchitectures: iphoneos-arm iphoneos-arm64 iphoneos-arm64e all\nComponents: main\nDate: "+format_datetime(datetime.now(timezone.utc),usegmt=True)+"\nDescription: Zema's iOS tweaks, apps and ports\n"
    for section,algorithm in [('MD5Sum','md5'),('SHA1','sha1'),('SHA256','sha256'),('SHA512','sha512')]:
        header+=section+':\n'
        for name in ['Packages','Packages.gz','Packages.bz2','Packages.xz']:
            payload=(ROOT/name).read_bytes();header+=f' {hashlib.new(algorithm,payload).hexdigest()} {len(payload):16d} {name}\n'
    # Signing and verification must finish before replacing public Release files.
    (ROOT/'Release.unsigned').write_text(header)
if __name__=='__main__':update()
