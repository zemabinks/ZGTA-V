"""Pinned LAN-only save compatibility hook; no change to global sign-in state.

The queued MP stats writer checks GetActiveGamerInfo only for non-null before
posting the serialized bytes. Our offline profile can be signed out of the
external service while using the local member-file writer. Keep every other
caller, and every non-null original result, unchanged.
"""
import hashlib
import browser_wasm as b

INPUT = '9992cec25e2827f56ca7432fa9df3f926401ffc31fe4f3ed65aac0c7ce6c1591'
BODY='84aef3288950076de03ba1ef1db3276ade192b77868ef9d90591d5dbd8683cc9'
SAVE_BODY='8b605974e9d50e0005202b1f79cc4851b91cc5532d9e5d97ca4069edfd6540cd'
NAME='NetworkInterface::GetActiveGamerInfo()'
INDEX=83013


def append(data):
    if hashlib.sha256(data).hexdigest()!=INPUT:raise ValueError('Unreviewed LAN engine for local save gamer hook')
    types,indices,names=b.gate.module_abi(data)
    if names.get(NAME)!=[INDEX] or types[indices[INDEX]]!=([],['i64']):raise ValueError('Local save gamer ABI changed')
    parts=list(b.gate.sections(data));sections=dict(parts)
    r=b.gate.Reader(sections[3]);functions=[r.uint() for _ in range(r.count())];r.finish();imported=len(indices)-len(functions)
    r=b.gate.Reader(sections[10]);bodies=[r.take(r.uint()) for _ in range(r.count())];r.finish()
    original=bodies[INDEX-imported]
    if hashlib.sha256(original).hexdigest()!=BODY:raise ValueError('Local save gamer body changed')
    r=b.gate.Reader(sections[7]);count=r.count();old=r.take(len(sections[7])-r.pos)
    r=b.gate.Reader(sections[7]);r.count();save_index=None;alias='zema:lan:original:active_gamer_info'
    for _ in range(count):
        name=r.text();kind=r.byte();index=r.uint()
        if name==alias:raise ValueError('Local save gamer hook already present')
        if name=='zema:lan:original:mpstats_save_update' and kind==0:save_index=index
    if save_index is None or hashlib.sha256(bodies[save_index-imported]).hexdigest()!=SAVE_BODY:raise ValueError('Reviewed MP save caller changed')
    r=b.gate.Reader(sections[4])
    if r.count()!=1 or r.byte()!=0x70:raise ValueError('Expected one local save function table')
    flags,minimum=r.uint(),r.uint();maximum=r.uint() if flags&1 else None;r.finish()
    if flags&~5:raise ValueError('Unexpected local save table flags')
    bodies[INDEX-imported]=b'\0'+(b'\x42' if flags&4 else b'\x41')+b.sleb(minimum)+b'\x11'+b.leb(indices[INDEX])+b'\0\x0b'
    bodies.append(original);functions.append(indices[INDEX]);out=bytearray(data[:8])
    for kind,raw in parts:
        if kind==3:raw=b.leb(len(functions))+b''.join(b.leb(v) for v in functions)
        elif kind==4:raw=b'\x01\x70'+b.leb(flags)+b.leb(minimum+1)+(b.leb(maximum+1) if maximum is not None else b'')
        elif kind==7:raw=b.leb(count+1)+old+b.string(alias)+b'\0'+b.leb(len(indices))
        elif kind==10:raw=b.leb(len(bodies))+b''.join(b.leb(len(v))+v for v in bodies)
        out.extend(b.section(kind,raw))
    out=bytes(out);new_types,new_indices,_=b.gate.module_abi(out)
    if new_types!=types or new_indices!=indices+[indices[INDEX]]:raise ValueError('Local save hook moved existing ABI indices')
    return out,{'group':'cloud','field':'active_gamer_info','name':NAME,'index':INDEX,'params':[],'results':['i64'],'body_sha256':BODY,'slot':minimum,'original_export':alias,'save_caller_sha256':SAVE_BODY,'scope':'local queued MP save only; no global sign-in writes'}
