"""Pinned minimap asset lookup; the host chooses approved compatible assets only after a miss."""
import hashlib
import browser_wasm as b

ENGINE_SHA256='11ca8d2c04c5e843d18ff4aea4899d72c86973c6b031df334e67c446b2ae83e0'
NAME='CMiniMap_Common::GetBlipName(int const&)'
BODY_SHA256='78dc74cd2772bd5f8d7cbd6cc84c5c82884f3df16867caace594d039cb16263d'
TABLE_COUNT_ADDRESS=19520944
HOOK={'field':'blip_asset_name','index':35144,'params':['i64'],'results':['i64'],
      'name':NAME,'body_sha256':BODY_SHA256}

def pin(types,indices,names,bodies,imported,derived=False):
    # This function contains no indirect calls; original and LAN bytes match.
    if names.get(NAME)!=[HOOK['index']] or types[indices[HOOK['index']]]!=(HOOK['params'],HOOK['results']):
        raise ValueError('Blip asset name/index/ABI changed')
    body=bodies[HOOK['index']-imported]
    if len(body)!=195 or hashlib.sha256(body).hexdigest()!=BODY_SHA256:
        raise ValueError('Blip asset name body changed')
    return dict(HOOK)

def inspect(data):
    if hashlib.sha256(data).hexdigest()!=ENGINE_SHA256:raise ValueError('Unreviewed blip diagnostic engine')
    types,indices,names=b.gate.module_abi(data);sections=dict(b.gate.sections(data))
    r=b.gate.Reader(sections[3]);imported=len(indices)-r.count()
    r=b.gate.Reader(sections[10]);bodies=[r.take(r.uint()) for _ in range(r.count())];r.finish()
    return pin(types,indices,names,bodies,imported)
