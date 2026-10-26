"""Apply only the pinned, reversible official-icon delta; no original writes."""
import base64,hashlib,json
from pathlib import Path
PATH='x64/data/cdimages/scaleform_minimap.rpf'
BASE_SHA='0f51cbf88739c7ac46779acfd7ef9e181aeeb54efee55ce721194b1e90463449'
PATCH=Path(__file__).resolve().parents[1]/'app/Resources/modern-map-icons.json'
def apply(original,patch):
 if patch.get('format')!='zgta-modern-map-delta-v1' or patch.get('path')!=PATH or patch.get('base_sha256')!=BASE_SHA:raise ValueError('Unreviewed minimap delta')
 if not isinstance(original,bytes) or len(original)!=patch['base_bytes'] or hashlib.sha256(original).hexdigest()!=BASE_SHA:raise ValueError('Original minimap differs')
 if not 0<patch['result_bytes']-len(original)<512*1024 or len(patch['edits'])!=1:raise ValueError('Minimap delta bounds')
 result=bytearray(original)
 for edit in patch['edits']:
  at=edit['offset'];before=bytes.fromhex(edit['before']);after=bytes.fromhex(edit['after'])
  if type(at) is not int or at<16 or at%16 or at>len(original)-16 or len(before)!=16 or len(after)!=16 or original[at:at+16]!=before:raise ValueError('Minimap table edit differs')
  result[at:at+16]=after
 append=base64.b64decode(patch['append_base64'],validate=True)
 if len(append)!=patch['result_bytes']-len(original):raise ValueError('Minimap append size')
 result.extend(append)
 if hashlib.sha256(result).hexdigest()!=patch['result_sha256']:raise ValueError('Minimap delta integrity')
 return bytes(result)
def manifest(raw,patch):
 data=json.loads(raw);matches=[r for r in data['files'] if r[0].lower()==PATH]
 if len(matches)!=1 or matches[0][1]!=patch['base_bytes']:raise ValueError('Original minimap manifest differs')
 matches[0][1]=patch['result_bytes']
 return json.dumps(data,separators=(',',':')).encode()
