"""Pinned, index-preserving controller/trainer extension for isolated browser engines.

Inserts one typed host call at the native port's pre-UpdateDebug boundary.
Original function/type/import indices and all other bodies remain unchanged.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import browser_wasm as b
from stage_browser import PINS, once

ORIGINAL='11ca8d2c04c5e843d18ff4aea4899d72c86973c6b031df334e67c446b2ae83e0'
LAN='1f532d3c3d06f664c8698509652b9b19c646d1b5d574b93b4c399dd5e8261c79'
LOADING_HASH='e26ef5d2ee14a038c89052fd37041a9098b62a653a9a8270064a7ce4430042dc'
GPU_HASH='9f94832b93b5c4ada84a0cdffb65157a05e71890c1904d298c74b12c00da32e2'
SESSION_READERS=[
 ('NetworkInterface::IsSessionEstablished()',83019,'0a1e9b65d28c5bac1d3b4d70380f6aece8d104705eb13f9c0ae8b32184cac305'),
 ('network_commands::CommandNetworkGetNumPlayers()',54857,'11070da59d21321fdfd76f55bf1abe676b361aaf8c111beada00cad361f1dcee')]
SESSION_OBSERVATION={'session_pointer':29044456,'state_offset':99916,'players_address':28504084,
                     'readers':[{'index':i,'body_sha256':h} for _,i,h in SESSION_READERS]}
PAD_HASH='dbf7b4028d37b2cab1a02d7738fe15cd2a66dbec01a71b169ebc5d9ea1e251de'
EXPORTS={
 'PlayerPedId':(58715,[],['i32']), 'RequestModel':(60322,['i32'],[]),
 'HasModelLoaded':(60324,['i32'],['i32']), 'GetEntityCoords':(50028,['i64','i32','i32'],[]),
 'GetEntityHeading':(50032,['i32'],['f32']), 'CreateVehicle':(61266,['i32','i64','f32','i32','i32','i32'],['i32']),
 'IsPedInAnyVehicle':(57118,['i32','i32'],['i32']), 'GetVehiclePedIsIn':(57184,['i32','i32'],['i32']),
 'TaskLeaveVehicle':(60572,['i32','i32','i32'],[]), 'ClearPedTasksImmediately':(60722,['i32'],[]),
 'SetPedIntoVehicle':(57201,['i32','i32','i32'],[]), 'SetVehicleEngineOn':(61505,['i32','i32','i32','i32'],[]),
 'malloc':(100,['i64'],['i64']), 'SetMenuPreference':(36170,['i32','i32'],[]),
 'SetProfilePreference':(36175,['i64','i32','i32'],[])
}
from browser_world_exports import EXPORTS as WORLD_EXPORTS
EXPORTS.update(WORLD_EXPORTS)
import session_restart
EXPORTS.update({a:(i,p,r) for a,n,i,p,r in session_restart.COMMANDS})


def transform(data):
    digest=hashlib.sha256(data).hexdigest()
    if digest not in (ORIGINAL,LAN):raise ValueError('Unreviewed engine; feature patch refused')
    types,indices,names=b.gate.module_abi(data)
    session_restart.validate_abi(types,indices,names)
    if names.get('rage::ioPad::Update(bool)')!=[10454] or types[indices[10454]]!=(['i64'],[]):raise ValueError('Controller hook ABI changed')
    if names.get('rage::ioPad::UpdateDebug()')!=[10456]:raise ValueError('Controller post-update boundary changed')
    for alias,(index,params,results) in EXPORTS.items():
        if types[indices[index]]!=(params,results):raise ValueError('Feature export ABI changed: '+alias)
    parts=list(b.gate.sections(data));sections=dict(parts)
    r=b.gate.Reader(sections[3]);defined=r.count();imported=len(indices)-defined
    r=b.gate.Reader(sections[4])
    if r.count()!=1 or r.byte()!=0x70:raise ValueError('Expected one function table')
    flags=r.uint();minimum=r.uint();maximum=r.uint() if flags&1 else None;r.finish()
    if flags&~5:raise ValueError('Unexpected table flags')
    r=b.gate.Reader(sections[10]);bodies=[r.take(r.uint()) for _ in range(r.count())];r.finish()
    if names.get('CLoadingScreens::AreActive()')!=[34946] or types[indices[34946]]!=([],['i32']) or hashlib.sha256(bodies[34946-imported]).hexdigest()!=LOADING_HASH:raise ValueError('Loading-state reader pin changed')
    for name,index,want in SESSION_READERS:
        if names.get(name)!=[index] or types[indices[index]]!=([],['i32']) or hashlib.sha256(bodies[index-imported]).hexdigest()!=want:raise ValueError('Session observation reader pin changed')
    import memory_filename
    memory_hook=memory_filename.pin(types,indices,names,bodies,imported)
    memory_hook['slot']=minimum+1
    memory_call=b''.join(b'\x20'+b.leb(i) for i in range(len(memory_hook['params'])))
    bodies[memory_hook['index']-imported]=b'\x00'+memory_call+(b'\x42' if flags&4 else b'\x41')+b.sleb(memory_hook['slot'])+b'\x11'+b.leb(indices[memory_hook['index']])+b'\x00\x0b'
    import text_fallback
    text_hook=text_fallback.pin(types,indices,names,bodies,imported,derived=digest==LAN)
    text_hook.update(slot=minimum+2,original_index=len(indices),original_export='zema:features:original_text')
    bodies.append(bodies[text_hook['index']-imported])
    bodies[text_hook['index']-imported]=b'\x00\x20\x00'+(b'\x42' if flags&4 else b'\x41')+b.sleb(text_hook['slot'])+b'\x11'+b.leb(indices[text_hook['index']])+b'\x00\x0b'
    import script_bank
    bank_hooks=script_bank.pin(types,indices,names,bodies,imported,derived=digest==LAN)
    for number,bank_hook in enumerate(bank_hooks):
        bank_hook.update(slot=minimum+3+number,original_index=len(indices)+1+number,
                         original_export='zema:features:original_'+bank_hook['field'])
        bodies.append(bodies[bank_hook['index']-imported])
        bank_call=b''.join(b'\x20'+b.leb(i) for i in range(len(bank_hook['params'])))
        bodies[bank_hook['index']-imported]=b'\x00'+bank_call+(b'\x42' if flags&4 else b'\x41')+b.sleb(bank_hook['slot'])+b'\x11'+b.leb(indices[bank_hook['index']])+b'\x00\x0b'
    import gamer_tags
    tag_hook=gamer_tags.pin(types,indices,names,bodies,imported,derived=digest==LAN)
    tag_hook.update(slot=minimum+5,original_index=len(indices)+3,original_export='zema:features:original_gamer_tag_render')
    bodies.append(bodies[tag_hook['index']-imported])
    bodies[tag_hook['index']-imported]=b'\x00'+(b'\x42' if flags&4 else b'\x41')+b.sleb(tag_hook['slot'])+b'\x11'+b.leb(indices[tag_hook['index']])+b'\x00\x0b'
    import blip_sprites
    blip_hook=blip_sprites.pin(types,indices,names,bodies,imported,derived=digest==LAN)
    blip_hook.update(slot=minimum+6,original_index=len(indices)+4,original_export='zema:features:original_blip_asset_name')
    bodies.append(bodies[blip_hook['index']-imported])
    bodies[blip_hook['index']-imported]=b'\x00\x20\x00'+(b'\x42' if flags&4 else b'\x41')+b.sleb(blip_hook['slot'])+b'\x11'+b.leb(indices[blip_hook['index']])+b'\x00\x0b'
    body=bodies[10454-imported]
    tail=b'\x20\x00\x10'+b.leb(10456)+b'\x0b'
    if hashlib.sha256(body).hexdigest()!=PAD_HASH or not body.endswith(tail):raise ValueError('Pinned pad body changed')
    hook={'field':'pad_update','params':['i64'],'results':[],'slot':minimum}
    call=b'\x20\x00'+(b'\x42' if flags&4 else b'\x41')+b.sleb(minimum)+b'\x11'+b.leb(indices[10454])+b'\x00'
    bodies[10454-imported]=body[:-len(tail)]+call+tail
    r=b.gate.Reader(sections[7]);count=r.count();old_exports=r.take(len(sections[7])-r.pos)
    check=b.gate.Reader(sections[7]);check.count()
    for _ in range(count):
        name=check.text();check.byte();check.uint()
        if name.startswith('zema:features:'):raise ValueError('Features already installed')
    additions=[b.string('zema:features:'+alias)+b'\0'+b.leb(row[0]) for alias,row in EXPORTS.items()]
    additions.append(b.string(text_hook['original_export'])+b'\0'+b.leb(text_hook['original_index']))
    additions.extend(b.string(h['original_export'])+b'\0'+b.leb(h['original_index']) for h in [*bank_hooks,tag_hook,blip_hook])
    # Name section pin for TLS, never infer it from an unrelated global.
    tls=[]
    for kind,raw in parts:
        if kind!=0:continue
        r=b.gate.Reader(raw)
        if r.text()!='name':continue
        while r.pos<len(raw):
            sub=r.byte();sr=b.gate.Reader(r.take(r.uint()))
            if sub!=7:continue
            for _ in range(sr.count()):
                index,name=sr.uint(),sr.text()
                if name=='__tls_base':tls.append(index)
    if tls!=[1]:raise ValueError('TLS global pin changed')
    additions.append(b.string('zema:features:tls-base')+b'\x03'+b.leb(1))
    start=None
    if 8 in sections:
        r=b.gate.Reader(sections[8]);start=r.uint();r.finish()
        additions.append(b.string('zema:features:start')+b'\0'+b.leb(start))
    output=bytearray(data[:8])
    for kind,raw in parts:
        if kind==3:
            r=b.gate.Reader(raw);function_count=r.count();raw=b.leb(function_count+5)+r.take(len(raw)-r.pos)+b''.join(b.leb(indices[h['index']]) for h in [text_hook,*bank_hooks,tag_hook,blip_hook])
        elif kind==4:raw=b'\x01\x70'+b.leb(flags)+b.leb(minimum+7)+(b.leb(maximum+7) if maximum is not None else b'')
        elif kind==7:raw=b.leb(count+len(additions))+old_exports+b''.join(additions)
        elif kind==8:continue
        elif kind==10:raw=b.leb(len(bodies))+b''.join(b.leb(len(v))+v for v in bodies)
        output.extend(b.section(kind,raw))
    output=bytes(output);newtypes,newindices,_=b.gate.module_abi(output)
    if newtypes!=types or newindices[:len(indices)]!=indices or newindices[len(indices):]!=[indices[h['index']] for h in [text_hook,*bank_hooks,tag_hook,blip_hook]]:raise ValueError('Original ABI indices moved')
    metadata={'format':'zema-browser-features-v1','engine_sha256':ORIGINAL,'input_sha256':digest,
      'patched_sha256':hashlib.sha256(output).hexdigest(),'pad_body_sha256':PAD_HASH,'table64':bool(flags&4),
      'loading_state':{'address':19473636,'function_index':34946,'body_sha256':LOADING_HASH},
      'session_observation':SESSION_OBSERVATION,'session_restart':session_restart.CONTRACT,
      'hook':hook,'memory_file_name':memory_hook,'text_fallback':text_hook,'script_bank':bank_hooks,'gamer_tag':tag_hook,'blip_sprites':blip_hook,'auxiliary_wasm':list(b.auxiliary([hook,memory_hook,text_hook,*bank_hooks,tag_hook,blip_hook])),'deferred_start':start is not None,
      'exports':{alias:{'index':i,'params':p,'results':r} for alias,(i,p,r) in EXPORTS.items()},
      'runtime_verified':False,'physical_controller_verified':False,'trainer_effects_verified':False}
    metadata['exports']['original_text']={'index':text_hook['original_index'],'params':['i32'],'results':['i64']}
    for h in [*bank_hooks,tag_hook,blip_hook]:metadata['exports']['original_'+h['field']]={'index':h['original_index'],'params':h['params'],'results':h['results']}
    return output,metadata

def offline_patch(name,data,mode,gamer_tags=True,blip_sprites=False):
    from serve_browser import offline_worker
    text=offline_worker(name,data,mode).decode()
    prefix="importScripts(new URL('session-restart.js',self.location.href).href,new URL('blip_sprites.js',self.location.href).href,new URL('gamer_tags.js',self.location.href).href,new URL('script_bank.js',self.location.href).href,new URL('text_fallback.js',self.location.href).href,new URL('memory_filename.js',self.location.href).href,new URL('browser-features.js',self.location.href).href,new URL('browser-trainer.js',self.location.href).href,new URL('browser-features-module.js',self.location.href).href);\n"
    if not blip_sprites:prefix=prefix.replace("new URL('blip_sprites.js',self.location.href).href,",'')
    if not gamer_tags:prefix=prefix.replace("new URL('gamer_tags.js',self.location.href).href,",'')
    if name=='game.js':
        text=english_worker(text)
        text=once(text,'wasmMemory=msgData.wasmMemory;','self.__zemaFeaturesContext=msgData.zemaFeaturesContext;wasmMemory=msgData.wasmMemory;')
        text=once(text,'worker.postMessage({cmd:1,handlers,wasmMemory,wasmModule})','worker.postMessage({cmd:1,handlers,wasmMemory,wasmModule,zemaFeaturesContext:self.__zemaFeaturesContext})')
        text=once(text,'new WebAssembly.Instance(wasmModule,getWasmImports())','ZemaBrowserFeatures.instance(wasmModule,getWasmImports(),self.__zemaFeaturesContext)')
        text=prefix+text
    elif name=='loader.js':
        text=once(text,"'use strict';","'use strict';\n"+prefix)
        text=once(text,'\tconst m = ev.data;','\tconst m = ev.data;\n\tself.__zemaFeaturesContext=m.features;')
        text=once(text,'WebAssembly.instantiate(bytes, imports)','ZemaBrowserFeatures.instantiate(bytes,imports,m.features)')
        text=once(text,'WebAssembly.instantiateStreaming(res, imports)','ZemaBrowserFeatures.instantiateStreaming(res,imports,m.features)')
    return text.encode()

def english_worker(text):
    # Exact boot-time game language query, not a browser/global locale override.
    return once(text,'stringToUTF8(typeof navigator!=="undefined"&&navigator.language?navigator.language:"en-US",$0,$1)',
        'stringToUTF8("en-US",$0,$1)')

def renderer(data):
    if hashlib.sha256(data).hexdigest()!=GPU_HASH:raise ValueError('Reviewed GPU worker source changed')
    import minimap_gpu, browser_gpu
    return browser_gpu.apply(minimap_gpu.apply(data.decode())).encode()

def stage(engine,lan_stage,output):
    from stage_browser import ROOT, APP
    output=output.absolute()
    if output.parent!=APP.absolute()/'Build' or output.exists() or '..' in output.parts or any(p.is_symlink() for p in (output,*output.parents)):raise ValueError('New isolated Build output required')
    original=engine.read_bytes();lan=(lan_stage/'game.engine-lan.wasm').read_bytes()
    offline,offline_meta=transform(original);online,online_meta=transform(lan)
    old_meta=json.loads((lan_stage/'engine-lan-module.json').read_text());old=json.loads((lan_stage/'browser-stage.json').read_text())
    for name,want in old['staged_hashes'].items():
        if not re.fullmatch('[A-Za-z0-9_.-]+',name) or hashlib.sha256((lan_stage/name).read_bytes()).hexdigest()!=want:raise ValueError('Prior LAN stage changed: '+name)
    if old_meta['patched_sha256']!=LAN:raise ValueError('Prior LAN metadata changed')
    # Preserve the exact historical online input and unchanged offline output;
    # only the feature-enabled LAN image receives the new shutdown trampoline.
    online,close_hook=b.append_socket_close(online)
    import local_save_gamer
    online,save_hook=local_save_gamer.append(online)
    import save_worker_probe
    online,save_worker_hooks=save_worker_probe.append(online)
    import online_wasm
    old_meta['hooks'].append(close_hook)
    old_meta['hooks'].append(save_hook)
    old_meta['hooks'].extend(save_worker_hooks)
    old_meta['auxiliary_wasm']=list(online_wasm.auxiliary(old_meta['hooks'],old_meta['social']))
    online_meta['socket_lifecycle']={'before_sha256':b.FEATURE_LAN_BEFORE_CLOSE,'hook':close_hook}
    online_meta['local_save_gamer']=save_hook
    online_meta['save_worker_diagnostics']=save_worker_hooks
    online_meta['inline_member_save']=True
    online_meta['patched_sha256']=hashlib.sha256(online).hexdigest()
    output.mkdir(mode=0o700)
    copied={}
    for name in old['staged_hashes']:
        if name in ('game.js','loader.js','engine-lan-browser.js'):continue
        copied[name]=(lan_stage/name).read_bytes()
        if name=='io_worker.js':
            import ui_asset_refresh
            if ui_asset_refresh.MARK not in copied[name].decode():copied[name]=ui_asset_refresh.apply(copied[name].decode()).encode()
    # LAN source already carries the original online/shared-profile wiring.
    game=english_worker((lan_stage/'game.js').read_text());loader=(lan_stage/'loader.js').read_text()
    prefix="importScripts(new URL('session-restart.js',self.location.href).href,new URL('blip_sprites.js',self.location.href).href,new URL('gamer_tags.js',self.location.href).href,new URL('script_bank.js',self.location.href).href,new URL('text_fallback.js',self.location.href).href,new URL('memory_filename.js',self.location.href).href,new URL('browser-features.js',self.location.href).href,new URL('browser-trainer.js',self.location.href).href);\n"
    copied['game.js']=(prefix+game).encode();copied['loader.js']=once(loader,"'use strict';","'use strict';\n"+prefix).encode()
    copied['engine-lan-browser.js']=(ROOT/'browser.js').read_bytes()
    for name in ('session-restart.js','network-worker.js','browser-features.js','browser-trainer.js','online.js','profile-rpc.js','profile-worker.js','memory_filename.js','text_fallback.js','script_bank.js','gamer_tags.js','blip_sprites.js'):copied[name]=(ROOT/name).read_bytes()
    copied['engine-lan-browser.js']=(ROOT/'browser.js').read_bytes()
    old_meta.update(patched_sha256=online_meta['patched_sha256'],features=online_meta)
    copied['engine-lan-module.js']=('globalThis.ZemaEngineLanModule='+json.dumps(old_meta)+';\n').encode()
    copied['browser-features-module.js']=('globalThis.ZemaBrowserFeaturesModule='+json.dumps(offline_meta)+';\n').encode()
    copied['game.features.offline.wasm']=offline
    copied['wgpu_worker.js']=renderer((engine.parent/'wgpu_worker.js').read_bytes())
    for name,data in copied.items():(output/name).write_bytes(data)
    (output/'game.engine-lan.wasm').write_bytes(online)
    (output/'engine-lan-module.json').write_text(json.dumps(old_meta)+'\n')
    (output/'browser-features-offline.json').write_text(json.dumps(offline_meta)+'\n')
    old.update(staged_hashes={name:hashlib.sha256(data).hexdigest() for name,data in copied.items()},features_ready=True,runtime_verified=False)
    (output/'browser-stage.json').write_text(json.dumps(old,indent=2)+'\n')
    return {'output':str(output),'offline':offline_meta['patched_sha256'],'lan':online_meta['patched_sha256'],'runtime_verified':False}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--engine',type=Path,required=True);p.add_argument('--lan-stage',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(stage(a.engine,a.lan_stage,a.output)))
