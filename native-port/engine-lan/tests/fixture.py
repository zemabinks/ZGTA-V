"""Tiny synthetic engine: eight typed socket functions, table and deferred start."""
import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('browser_wasm', ROOT / 'browser_wasm.py')
patcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(patcher)
leb, section, string = patcher.leb, patcher.section, patcher.string
FIELDS = [('profiler_push', ['i64','i64','i32']), ('create_socket', ['i64','i32','i32','i32','i32']),
          ('socket_bind', ['i64']), ('socket_send', ['i64','i64','i64','i32','i64']),
          ('socket_receive', ['i64','i64','i64','i32','i64']), ('socket_select', ['i32','i64','i64','i64','i64']),
          ('local_ip_address', ['i64']), ('public_ip_address', ['i64'])]


def engine(table64=True, include_close=False):
    fields = FIELDS + ([('socket_close',['i64'])] if include_close else [])
    count = len(fields) + 1
    inverse = {'i32':0x7f,'i64':0x7e}
    types = [b'\x60'+leb(len(args))+bytes(inverse[a] for a in args)+(b'\x00' if name=='socket_close' else b'\x01\x7f') for name, args in fields]
    types.append(b'\x60\x00\x00')
    imports = string('env') + string('memory') + b'\x02\x03' + leb(256) + leb(256)
    exports = [string('test:'+name)+b'\x00'+leb(i) for i,(name,_) in enumerate(fields)]
    exports += [string('__indirect_function_table')+b'\x01\x00',string('starts')+b'\x03\x00']
    bodies = [b'\x00\x41\x00\x0b']*8
    if include_close:bodies.append(b'\x00\x20\x00\xa7\x42\x7f\x37\x03\x08\x0b')
    bodies.append(b'\x00\x23\x00\x41\x01\x6a\x24\x00\x0b')
    names = leb(count)+b''.join(leb(i)+string('Fixture::'+name) for i,(name,_) in enumerate(fields))+leb(count-1)+string('Fixture::start')
    data=(b'\0asm\x01\0\0\0'+section(1,leb(count)+b''.join(types))+section(2,b'\x01'+imports)+
          section(3,leb(count)+b''.join(leb(i) for i in range(count)))+section(4,b'\x01\x70'+leb(5 if table64 else 1)+b'\x01\x01')+
          section(6,b'\x01\x7f\x01\x41\x00\x0b')+section(7,leb(len(exports))+b''.join(exports))+
          section(8,leb(count-1))+section(10,leb(count)+b''.join(leb(len(b))+b for b in bodies))+section(0,string('name')+section(1,names)))
    contract={'engine_sha256':hashlib.sha256(data).hexdigest(),'upstream_revision':'SYNTHETIC_FIXTURE_ONLY',
              'hooks':[{'field':name,'group':'vnet','name':'Fixture::'+name,'index':i,'params':args,'results':[] if name=='socket_close' else ['i32']} for i,(name,args) in enumerate(fields)]}
    return data, contract


def reviewed_feature_lan():
    """Rebuild the exact pinned intermediate; historical stage folders can advance."""
    import browser_features
    data = (ROOT.parent / 'app/Build/EngineLAN-OnlineBrowser-20261017-v5/game.engine-lan.wasm').read_bytes()
    if hashlib.sha256(data).hexdigest() != browser_features.LAN:
        raise ValueError('Reviewed base LAN engine changed')
    output, _ = browser_features.transform(data)
    if hashlib.sha256(output).hexdigest() != patcher.FEATURE_LAN_BEFORE_CLOSE:
        raise ValueError('Reviewed feature intermediate changed')
    return output
