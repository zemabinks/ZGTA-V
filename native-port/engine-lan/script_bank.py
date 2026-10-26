"""Exact-engine pins for Glue 5's failed script-bank compatibility hooks.

Source: glue5 a62e56a5/crates/glue5-runtime/src/script_assets.rs:57-79.
Inspection only; no game execution or transformation on import.
"""
import hashlib
import browser_wasm as b

ENGINE_SHA256='11ca8d2c04c5e843d18ff4aea4899d72c86973c6b031df334e67c446b2ae83e0'
UPSTREAM='a62e56a5b6423071c2f32c9c3446bca74734d9c3'
HOOKS=[
    {'field':'script_bank_request','index':21855,'params':['i32','i32','i32'],'results':['i32'],
     'name':'audScriptAudioEntity::RequestScriptBank(unsigned int, bool, unsigned int)',
     'body_sha256':'325fa66ec6242aa144d7c0b950b7b1ab0e1672572ac8d7a51f371491137d33a3'},
    {'field':'bank_loading_status','index':7226,'params':['i64','i32'],'results':['i32'],
     'name':'rage::audWaveSlot::GetBankLoadingStatus(unsigned int) const',
     'body_sha256':'17562dbe06dc555370e99be693f02ba9eb120c67096435322eac8f07fb391198'}
]
ORIGINAL_LENGTHS=[1794,95]
LAN_PINS=[(1806,'8edcea3253e6baf99381d80ed572f6d6cca170b96a7e811cd2efd8282db6c083'),
          (95,HOOKS[1]['body_sha256'])]


def pin(types,indices,names,bodies,imported,derived=False):
    out=[]
    for number,hook in enumerate(HOOKS):
        if names.get(hook['name'])!=[hook['index']]:raise ValueError('Script bank name/index changed: '+hook['field'])
        if types[indices[hook['index']]]!=(hook['params'],hook['results']):raise ValueError('Script bank ABI changed: '+hook['field'])
        body=bodies[hook['index']-imported]
        length,want=LAN_PINS[number] if derived else (ORIGINAL_LENGTHS[number],hook['body_sha256'])
        if len(body)!=length or hashlib.sha256(body).hexdigest()!=want:raise ValueError('Script bank body changed: '+hook['field'])
        out.append(dict(hook))
    return out


def inspect(data):
    if hashlib.sha256(data).hexdigest()!=ENGINE_SHA256:raise ValueError('Unreviewed engine for script bank inspection')
    types,indices,names=b.gate.module_abi(data);sections=dict(b.gate.sections(data))
    r=b.gate.Reader(sections[3]);imported=len(indices)-r.count()
    r=b.gate.Reader(sections[10]);bodies=[r.take(r.uint()) for _ in range(r.count())];r.finish()
    return pin(types,indices,names,bodies,imported)
