"""Exact CTextFile hook pin; no game execution or transformation on import."""
import hashlib
import browser_wasm as b

ENGINE_SHA256='11ca8d2c04c5e843d18ff4aea4899d72c86973c6b031df334e67c446b2ae83e0'
NAME='CTextFile::GetInternal(unsigned int)'
BODY_SHA256='fd017869f336468fcfc1e7aff84596ed412b4f694dceeca6ec95dfb819b9c182'
LAN_BODY_SHA256='834a6dab325197b3917d75a99620720f53059852e31c9a05e568027432bccead'
UPSTREAM='551ccf25fcbb07de0acabb365b310ad80ac69659'
HOOK={'field':'text_get_internal','index':77480,'params':['i32'],'results':['i64'],
      'name':NAME,'body_sha256':BODY_SHA256}


def pin(types,indices,names,bodies,imported,derived=False):
    if names.get(NAME)!=[HOOK['index']]:raise ValueError('Text getter name/index changed')
    if types[indices[HOOK['index']]]!=(HOOK['params'],HOOK['results']):raise ValueError('Text getter ABI changed')
    body=bodies[HOOK['index']-imported]
    # The separately full-SHA-admitted LAN input already remaps its original
    # indirect calls; preserve that exact body as the forwarded original.
    length,want=(1130,LAN_BODY_SHA256) if derived else (1114,BODY_SHA256)
    if len(body)!=length or hashlib.sha256(body).hexdigest()!=want:raise ValueError('Text getter body changed')
    return dict(HOOK)


def inspect(data):
    if hashlib.sha256(data).hexdigest()!=ENGINE_SHA256:raise ValueError('Unreviewed engine for text inspection')
    types,indices,names=b.gate.module_abi(data);sections=dict(b.gate.sections(data))
    r=b.gate.Reader(sections[3]);imported=len(indices)-r.count()
    r=b.gate.Reader(sections[10]);bodies=[r.take(r.uint()) for _ in range(r.count())];r.finish()
    return pin(types,indices,names,bodies,imported)
