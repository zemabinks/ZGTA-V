"""Native-only allocator wrappers; original engine ABI and C bodies are pinned.

Only the host's memory-pressure policy requests reclamation. Browser WASM and
all protocol/content/save functions remain unchanged.
"""
from pathlib import Path
import hashlib,json,re,sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'app/Scripts'))
import inspect_engine_lan as gate
PINS=json.loads((ROOT/'resource-reclaim-pins.json').read_text())
INCLUDE='#include "../Source/NativeResourceReclaim.h"\n'

def function(text,index):
    matches=list(re.finditer(r'(?ms)^\w+ w2c_game_f'+str(index)+r'\([^\n]*\) \{\n.*?^\}',text))
    if len(matches)!=1:raise ValueError('Missing/duplicate resource allocator function '+str(index))
    return matches[0]

def wrapper(index):
    if index==3038:return '''u64 w2c_game_f3038(w2c_game* instance, u64 var_p0, u64 var_p1, u64 var_p2, u32 var_p3) {
  u64 result=pg_original_resource_allocate(instance,var_p0,var_p1,var_p2,var_p3);
  if(result && pg_resource_reclaim_has_pages(var_p0)) {
    u64 size=w2c_game_f3046(instance,var_p0,result);
    if(size<var_p1)size=var_p1;
    if(!pg_resource_reclaim_reuse(var_p0,result,size,instance->w2c_env_memory->size))wasm_rt_trap(WASM_RT_TRAP_UNREACHABLE);
  }
  return result;
}'''
    if index==3039:return '''void w2c_game_f3039(w2c_game* instance, u64 var_p0, u64 var_p1) {
  if(pg_resource_reclaim_wants(var_p0,var_p1)) {
    u64 size=w2c_game_f3046(instance,var_p0,var_p1);
    pg_resource_reclaim_free(var_p0,var_p1,size,instance->w2c_env_memory->size);
  }
  pg_original_resource_free(instance,var_p0,var_p1);
}'''
    raise ValueError('Unreviewed wrapper')

def transform(text):
    for row in reversed(PINS['hooks']):
        m=function(text,row['index'])
        if hashlib.sha256(m[0].encode()).hexdigest()!=row['generated_sha256']:raise ValueError('Original allocator C body changed')
        if row['index']==3046:continue
        name='allocate' if row['index']==3038 else 'free'
        original=m[0].replace('w2c_game_f'+str(row['index'])+'(', 'pg_original_resource_'+name+'(',1)
        text=text[:m.start()]+'static '+original+'\n\n'+wrapper(row['index'])+text[m.end():]
    return INCLUDE+text

def stage(generated,engine):
    gate.inspect(engine,PINS)
    p=generated/'game_15.c';text=p.read_text()
    if text.startswith(INCLUDE):verify(generated,engine);return
    p.write_text(transform(text))
    verify(generated,engine)

def verify(generated,engine):
    gate.inspect(engine,PINS)
    text=(generated/'game_15.c').read_text()
    # Check untouched original bodies and exact wrappers independently; no
    # provenance claim is inferred merely from a name being present.
    for row in PINS['hooks']:
        index=row['index']
        if index==3046:body=function(text,index)[0]
        else:
            if function(text,index)[0]!=wrapper(index):raise ValueError('Resource wrapper differs')
            name='allocate' if index==3038 else 'free'
            m=re.search(r'(?ms)^static (\w+) pg_original_resource_'+name+r'\([^\n]*\) \{\n.*?^\}',text)
            if not m:raise ValueError('Original resource implementation missing')
            body=m[0][7:].replace('pg_original_resource_'+name+'(','w2c_game_f'+str(index)+'(',1)
        if hashlib.sha256(body.encode()).hexdigest()!=row['generated_sha256']:raise ValueError('Original resource body differs')
