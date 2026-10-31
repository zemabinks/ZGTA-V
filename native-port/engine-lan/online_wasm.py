"""Exact-engine online callbacks and signature-preserving host role dispatch."""
import argparse
import hashlib
import json
from pathlib import Path
import browser_wasm as b
import social_tables as social
g=b.gate
FEATURE_BASE_SHA256='1f532d3c3d06f664c8698509652b9b19c646d1b5d574b93b4c399dd5e8261c79'

def feature_base(data,contract):
    """Produce the pinned 60-hook input consumed by browser_features.

    socket_close was introduced after the base feature transform. Its existing
    append_socket_close producer must run there, rather than shifting the base
    function table and all later phase hashes. General transform stays intact.
    """
    hooks=contract['hooks']
    close=[h for h in hooks if h['field']=='socket_close']
    if len(hooks)!=61 or len(close)!=1 or close[0]['index']!=184:
        raise ValueError('Reviewed feature-base hook phase changed')
    selected=dict(contract,hooks=[h for h in hooks if h['field']!='socket_close'])
    output,metadata=transform(data,selected)
    if hashlib.sha256(output).hexdigest()!=FEATURE_BASE_SHA256:
        raise ValueError('Reviewed feature-base output changed')
    return output,metadata

def signed(r):
    for _ in range(10):
        if not r.byte()&128:return
    raise ValueError('Invalid signed immediate')

def memarg(r):
    align=r.uint()
    if align&64:r.uint()
    r.uint()

def rewrite(body,resolvers):
    r=g.Reader(body);out=bytearray();count=r.count()
    for _ in range(count):
        r.uint();t=r.byte()
        if t in (0x63,0x64):signed(r)
    out.extend(body[:r.pos]);calls=0
    while r.pos<len(body):
        start=r.pos;op=r.byte()
        if op in (2,3,4,6):signed(r)
        elif op in (7,8,9,0x0c,0x0d,0x10,0x12,0x14,0x15,0x18,0x20,0x21,0x22,0x23,0x24,0x25,0x26,0x3f,0x40,0xd2,0xd5,0xd6):r.uint()
        elif op==0x0e:
            for _ in range(r.count()+1):r.uint()
        elif op in (0x11,0x13):
            type_index=r.uint();table=r.uint()
            if table!=0 or type_index not in resolvers:raise ValueError('Unknown indirect call boundary')
            out.extend(b'\x10'+b.leb(resolvers[type_index]));calls+=1
        elif op==0x1c:
            for _ in range(r.count()):
                if r.byte() in (0x63,0x64):signed(r)
        elif op==0x1f:
            signed(r)
            for _ in range(r.count()):
                kind=r.byte()
                if kind in (0,1):r.uint()
                elif kind not in (2,3):raise ValueError('Unknown exception clause')
                r.uint()
        elif 0x28<=op<=0x3e:memarg(r)
        elif op in (0x41,0x42,0xd0):signed(r)
        elif op==0x43:r.take(4)
        elif op==0x44:r.take(8)
        elif op==0xfc:
            sub=r.uint()
            if sub in (8,10,12,14):r.uint();r.uint()
            elif sub in (9,11,13,15,16,17,18):r.uint()
            elif sub>7:raise ValueError('Unknown misc instruction')
        elif op==0xfd:
            sub=r.uint()
            if sub<=11 or sub in (92,93):memarg(r)
            elif sub in (12,13):r.take(16)
            elif 21<=sub<=34:r.take(1)
            elif 84<=sub<=91:memarg(r);r.take(1)
            elif sub>0x113:raise ValueError('Unknown SIMD instruction')
        elif op==0xfe:
            sub=r.uint()
            if sub==3:r.take(1)
            elif sub<=2 or 0x10<=sub<=0x4e:memarg(r)
            else:raise ValueError('Unknown atomic instruction')
        elif not (op in (0,1,5,0x0a,0x0b,0x0f,0x19,0x1a,0x1b,0xd1,0xd3,0xd4) or 0x45<=op<=0xc4):
            raise ValueError(f'Unknown opcode {op:#x} at body offset {start}')
        out.extend(body[start:r.pos])
    return bytes(out),calls

def auxiliary(hooks,plan):
    inverse={name:kind for kind,name in g.TYPES.items()};types=[];imports=[];functions=[];bodies=[];exports=[]
    entries=[dict(h,imported=True) for h in hooks]+[dict(e,field='social_'+str(i),imported=e['role'] in (0,3)) for i,e in enumerate(plan['entries'])]
    for e in entries:
        types.append(b'\x60'+b.leb(len(e['params']))+bytes(inverse[t] for t in e['params'])+b.leb(len(e['results']))+bytes(inverse[t] for t in e['results']))
    imported=0
    for i,e in enumerate(entries):
        if e['imported']:
            imports.append(b.string('zema')+b.string(e['field'])+b'\x00'+b.leb(i));e['aux_index']=imported;imported+=1
    for i,e in enumerate(entries):
        if not e['imported']:
            e['aux_index']=imported+len(functions);functions.append(i);result=e['results']
            zero={'i32':b'\x41\x00','i64':b'\x42\x00','f32':b'\x43'+bytes(4),'f64':b'\x44'+bytes(8),'v128':b'\xfd\x0c'+bytes(16)}
            code=(b'\x41\x01' if result==['i32'] else b'\x42\x01') if e['role']==2 else (zero[result[0]] if result else b'')
            bodies.append(b'\x00'+code+b'\x0b')
        exports.append(b.string(e['field'])+b'\x00'+b.leb(e['aux_index']))
    out=b'\0asm\x01\0\0\0'+b.section(1,b.leb(len(types))+b''.join(types))+b.section(2,b.leb(len(imports))+b''.join(imports))
    if functions:out+=b.section(3,b.leb(len(functions))+b''.join(b.leb(t) for t in functions))
    out+=b.section(7,b.leb(len(exports))+b''.join(exports))
    if bodies:out+=b.section(10,b.leb(len(bodies))+b''.join(b.leb(len(x))+x for x in bodies))
    return out

def transform(data,contract):
    selected=dict(contract,hooks=[dict(h,group='vnet') for h in contract['hooks']]);prepared,metadata=b.transform(data,selected)
    for h,original in zip(metadata['hooks'],contract['hooks']):h['group']=original['group']
    types,indices,names=g.module_abi(prepared);parts=list(g.sections(prepared));index_type='i64' if metadata['table64'] else 'i32'
    signature=([index_type],[index_type]);new_type=signature not in types;resolve_type=len(types) if new_type else types.index(signature)
    table_reader=g.Reader(dict(parts)[4]);table_reader.count();table_reader.byte();flags=table_reader.uint();minimum=table_reader.uint();maximum=table_reader.uint() if flags&1 else None
    plan=social.model(types,minimum);resolvers={i:len(indices)+i for i in range(len(types))};changed_calls=0;out=bytearray(prepared[:8]);new_exports=[]
    for name in ['emscripten_builtin_malloc','emscripten_builtin_free']:
        if len(names.get(name,[]))!=1:raise ValueError('Allocator export pin absent')
        new_exports.append(b.string('zema:lan:'+('allocate' if name.endswith('malloc') else 'release'))+b'\x00'+b.leb(names[name][0]))
    for kind,body in parts:
        r=g.Reader(body)
        if kind==1 and new_type:
            count=r.count();t=0x7e if metadata['table64'] else 0x7f;body=b.leb(count+1)+r.take(len(body)-r.pos)+bytes([0x60,1,t,1,t])
        elif kind==3:
            count=r.count();body=b.leb(count+len(types))+r.take(len(body)-r.pos)+b.leb(resolve_type)*len(types)
        elif kind==4:
            body=b'\x01\x70'+b.leb(flags)+b.leb(minimum+plan['count'])+(b.leb(maximum+plan['count']) if maximum is not None else b'')
        elif kind==7:
            count=r.count();body=b.leb(count+len(new_exports))+r.take(len(body)-r.pos)+b''.join(new_exports)
        elif kind==10:
            bodies=[]
            for _ in range(r.count()):
                rewritten,n=rewrite(r.take(r.uint()),resolvers);bodies.append(rewritten);changed_calls+=n
            for row in plan['mapping']:
                code=bytearray(b'\x00');const=b'\x42' if metadata['table64'] else b'\x41';eq=b'\x51' if metadata['table64'] else b'\x46'
                for role,slot in enumerate(row):code.extend(b'\x20\x00'+const+b.sleb(minimum+role)+eq+b'\x04\x40'+const+b.sleb(slot)+b'\x0f\x0b')
                code.extend(b'\x20\x00\x0b');bodies.append(bytes(code))
            body=b.leb(len(bodies))+b''.join(b.leb(len(x))+x for x in bodies)
        out.extend(b.section(kind,body))
    output=bytes(out);new_types,new_indices,_=g.module_abi(output)
    if new_types[:len(types)]!=types or new_indices[:len(indices)]!=indices:raise ValueError('Original ABI indices moved')
    metadata.update(patched_sha256=hashlib.sha256(output).hexdigest(),social=plan,auxiliary_wasm=list(auxiliary(metadata['hooks'],plan)),indirect_sites_rewritten=changed_calls,online_startup_ready=True,experimental_only=True,shared_profile_required=True)
    return output,metadata

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--engine',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists() or a.output.parent.absolute()!=b.APP.absolute()/'Build' or any(x.is_symlink() for x in (a.output,*a.output.parents)):raise ValueError('New isolated Build child required')
    data,metadata=feature_base(a.engine.read_bytes(),json.loads(g.CONTRACT.read_text()));a.output.mkdir(mode=0o700)
    (a.output/'game.engine-lan.wasm').write_bytes(data);(a.output/'engine-lan-module.json').write_text(json.dumps(metadata)+'\n');(a.output/'engine-lan-module.js').write_text('globalThis.ZemaEngineLanModule='+json.dumps(metadata)+';\n')
    print(json.dumps({'output':str(a.output),'hooks':len(metadata['hooks']),'typed_social_entries':metadata['social']['count'],'indirect_sites':metadata['indirect_sites_rewritten'],'runtime_verified':False}))
