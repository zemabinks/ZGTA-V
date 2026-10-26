"""Bundled reference images supplied separately from installed vehicle packs."""
import hashlib
import json
from pathlib import Path
import re
import struct

RESOURCES=Path(__file__).resolve().parent.parent/'app/Resources'


def load():
    rows=json.loads((RESOURCES/'mod-vehicle-previews.json').read_text())
    if not isinstance(rows,dict) or len(rows)>32:
        raise ValueError('Invalid mod preview catalog')
    for model,row in rows.items():
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}',model) or set(row)!={'file','credit','sha256'}:
            raise ValueError('Invalid mod preview record')
        name=row['file']
        if not isinstance(name,str) or not re.fullmatch(r'mod-vehicle-[a-z0-9_]+\.png',name):
            raise ValueError('Invalid mod preview image path')
        file=RESOURCES/name
        if file.is_symlink() or not 0<file.stat().st_size<=4*1024*1024:
            raise ValueError('Invalid mod preview image')
        data=file.read_bytes()
        if (data[:8]!=b'\x89PNG\r\n\x1a\n' or len(data)<24 or
                not all(0<n<=8192 for n in struct.unpack_from('>II',data,16)) or
                hashlib.sha256(data).hexdigest()!=row['sha256']):
            raise ValueError('Mod preview image identity differs')
        if not isinstance(row['credit'],str) or not 0<len(row['credit'])<=200:
            raise ValueError('Invalid mod preview credit')
    return rows
