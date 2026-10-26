"""Exact original-engine and generated-source pins for glue5's name layout fix."""
import hashlib
import json
from pathlib import Path
import re
import browser_wasm as b
ROOT=Path(__file__).resolve().parent
ENGINE_SHA='11ca8d2c04c5e843d18ff4aea4899d72c86973c6b031df334e67c446b2ae83e0'
UPSTREAM='a62e56a5b6423071c2f32c9c3446bca74734d9c3'
SOURCE_SHA='6998d0b6a16350f76947f19b21c2b6612a1015c5ea8657905fb3577b61f24306'
HOOK={'field':'gamer_tag_render','index':35212,'name':'CMultiplayerGamerTagHud::Render()',
      'params':[],'results':[],'body_sha256':'e0ace01496a38052316e53d340f57787bc8a041f1aec8febb7c072e5dfedbfbb'}
C_SHA='ada8280dfc19f07477ed17f6c7dacd81b02ddfa45e67d7c6bd94b57320da3c53'
SIGNATURE='void w2c_game_f35212(w2c_game* instance)'
RENAMED=SIGNATURE.replace('f35212(', 'f35212_zema_tag_original(')
PATTERN=re.compile(rb'(?ms)^void w2c_game_f35212\([^\n]*\) \{\n.*?^\}')

def pin(types,indices,names,bodies,imported,derived=False):
    h=HOOK;i=h['index']
    if names.get(h['name'])!=[i] or types[indices[i]]!=(h['params'],h['results']):raise ValueError('Gamer tag name/index/ABI changed')
    body=bodies[i-imported]
    length,digest=(7775,'ab67aa3d56c6eac7cbd178cffc47fb7256b51fa6453f80c3733e7696cf23be6c') if derived else (7759,h['body_sha256'])
    if len(body)!=length or hashlib.sha256(body).hexdigest()!=digest:raise ValueError('Gamer tag render body changed')
    return dict(h)

def inspect(data):
    if hashlib.sha256(data).hexdigest()!=ENGINE_SHA:raise ValueError('Unreviewed gamer tag engine')
    types,indices,names=b.gate.module_abi(data);s=dict(b.gate.sections(data))
    r=b.gate.Reader(s[3]);imported=len(indices)-r.count()
    r=b.gate.Reader(s[10]);bodies=[r.take(r.uint()) for _ in range(r.count())];r.finish()
    return pin(types,indices,names,bodies,imported)

def patch_part(data):
    matches=list(PATTERN.finditer(data))
    if len(matches)!=1:raise ValueError('Gamer tag original missing/duplicate/already patched')
    body=matches[0][0]
    if not body.startswith(SIGNATURE.encode()+b' {\n') or len(body)!=160873 or hashlib.sha256(body).hexdigest()!=C_SHA:raise ValueError('Gamer tag generated C bytes/ABI changed')
    return data.replace(SIGNATURE.encode()+b' {\n',RENAMED.encode()+b' {\n',1)

def helper():
    return '''/* Pinned original Render first, then repair movie layout and request relayout. */
#include "game.h"
#include "ZemaGamerTagLayout.h"
extern void w2c_game_f35212_zema_tag_original(w2c_game*);
extern uint8_t* mugoat_memory_data(void*,uint64_t*);
void w2c_game_f35212(w2c_game* instance){
  w2c_game_f35212_zema_tag_original(instance);
  uint64_t size=0;uint8_t* memory=mugoat_memory_data(instance,&size);
  ZemaGamerTagComplete(memory,size);
}
'''.encode()

def stage(data,generated):
    inspect(data);generated=Path(generated);p=generated/'game_19.c';old=p.read_bytes();patched=patch_part(old)
    # A stage is a new output; accepted source builds are never passed here.
    if (generated/'ZemaNativeGamerTags.c').exists():raise ValueError('Preserve existing gamer tag stage')
    p.write_bytes(patched);(generated/'ZemaNativeGamerTags.c').write_bytes(helper())
    receipt={'format':'zema-native-gamer-tags-v1','engine_sha256':ENGINE_SHA,'upstream':UPSTREAM,'upstream_file_sha256':SOURCE_SHA,'original_part_sha256':hashlib.sha256(old).hexdigest(),'patched_part_sha256':hashlib.sha256(patched).hexdigest(),'helper_sha256':hashlib.sha256(helper()).hexdigest(),'runtime_verified':False}
    (generated/'gamer-tags-plan.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

def verify(data,generated):
    inspect(data);generated=Path(generated);part=(generated/'game_19.c').read_bytes()
    if part.count(RENAMED.encode()+b' {\n')!=1:raise ValueError('Gamer tag staged definition changed')
    original=part.replace(RENAMED.encode()+b' {\n',SIGNATURE.encode()+b' {\n',1)
    if patch_part(original)!=part or (generated/'ZemaNativeGamerTags.c').read_bytes()!=helper():raise ValueError('Gamer tag staged source changed')
    r=json.loads((generated/'gamer-tags-plan.json').read_text())
    expected={'format':'zema-native-gamer-tags-v1','engine_sha256':ENGINE_SHA,'upstream':UPSTREAM,'upstream_file_sha256':SOURCE_SHA,'original_part_sha256':hashlib.sha256(original).hexdigest(),'patched_part_sha256':hashlib.sha256(part).hexdigest(),'helper_sha256':hashlib.sha256(helper()).hexdigest(),'runtime_verified':False}
    if r!=expected:raise ValueError('Gamer tag receipt changed')
    return r
