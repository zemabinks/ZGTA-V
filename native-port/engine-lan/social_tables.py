"""Typed Social Club host-slot dispatch. Original indirect-call checks stay on.

Four reserved interface role indices resolve to a signature-correct table entry
BEFORE the ordinary type check. Ordinary engine indices are never translated.
No function hash is forged and no C call uses the wrong prototype.
"""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'app/Scripts'))
import inspect_engine_lan as gate
C={'i32':'u32','i64':'u64','f32':'f32','f64':'f64','v128':'v128'}

def roles(params,results):
    result=results[0] if results else None
    return [params==['i64','i64','i64'] and result in ('i32','i64'),True,
            params==['i64'] and result in ('i32','i64'),
            params==['i64','i64'] and result in ('i32','i64')]

def model(types,base):
    entries=[];mapping=[]
    for n,(params,results) in enumerate(types):
        row=[]
        for role,allowed in enumerate(roles(params,results)):
            if allowed:
                row.append(base+4+len(entries));entries.append({'type':n,'role':role,'params':params,'results':results})
            else:row.append(base+role)
        mapping.append(row)
    return {'base':base,'entries':entries,'mapping':mapping,'types':types,'count':4+len(entries)}

def native(types,base=89368):
    plan=model(types,base);functions=[];init=[];rows=[]
    for n,e in enumerate(plan['entries']):
        params=e['params'];results=e['results'];result=C[results[0]] if results else 'void'
        args=', '.join(['void* instance']+[C[t]+f' a{i}' for i,t in enumerate(params)])
        unused='(void)instance;'+''.join(f'(void)a{i};' for i in range(len(params)))
        zero={'i32':'0','i64':'0','f32':'0.0f','f64':'0.0','v128':'(v128){0}'}
        body=unused
        if e['role']==0:body+='if(a2)write64(instance,a2,0);return 0x80004002u;'
        elif e['role']==2:body+='return 1;'
        elif e['role']==3:body+='if(!sign_info(instance,a1))return 0x80004003u;return 0;'
        elif results:body+='return '+zero[results[0]]+';'
        functions.append(f'static {result} social_{n}({args})'+'{'+body+'}')
        init.append(f'  table->data[{base+4+n}]=(wasm_rt_funcref_t){{.func_type=types[{e["type"]}],.func=(wasm_rt_function_ptr_t)social_{n},.module_instance=instance}};')
    for n,(params,results) in enumerate(types):
        enums=','.join('WASM_RT_'+t.upper() for t in params+results)
        rows.append(f'  types[{n}]=wasm2c_game_get_func_type({len(params)},{len(results)}'+(','+enums if enums else '')+');')
    header='''#ifndef ZEMA_SOCIAL_H
#define ZEMA_SOCIAL_H
#include "game.h"
u64 ZemaSocialResolve(wasm_rt_funcref_table_t*,wasm_rt_func_type_t,u64);
int ZemaSocialInstall(w2c_game*);
int ZemaSocialPrepare(void*);
u64 ZemaEngineAllocate(void*,u64);
void ZemaEngineRelease(void*,u64);
#endif
'''
    source='''/* Generated typed dispatch, not an unchecked-call compatibility flag. */
#include "ZemaSocial.h"
#include "ZemaProfile.h"
#include <simde/wasm/simd128.h>
typedef simde_v128_t v128;
#include <pthread.h>
#include <string.h>
extern uint8_t* mugoat_memory_data(void*,uint64_t*);
extern u64 w2c_game_f91000(w2c_game*,u64);
extern void w2c_game_f91002(w2c_game*,u64);
u64 ZemaEngineAllocate(void* i,u64 n){return w2c_game_f91000(i,n);}
void ZemaEngineRelease(void* i,u64 p){w2c_game_f91002(i,p);}
static int write64(void* i,u64 p,u64 v){u64 n=0;uint8_t* m=mugoat_memory_data(i,&n);if(!m||p>n||8>n-p)return 0;memcpy(m+p,&v,8);return 1;}
static int sign_info(void* i,u64 p){u64 n=0;uint8_t* m=mugoat_memory_data(i,&n);if(!m||p>n||33>n-p)return 0;u64 id=ZemaProfileId();memcpy(m+p+8,&id,8);return ZemaProfileName(m+p+16,17)>=0;}
'''+ '\n'.join(functions)+f'''
static wasm_rt_func_type_t types[{len(types)}];
static const u32 mapping[{len(types)}][4]={{
'''+',\n'.join('{'+','.join(str(x) for x in row)+'}' for row in plan['mapping'])+'''};
static pthread_once_t once=PTHREAD_ONCE_INIT;
static u32 lookup[4096];
static u32 hash_type(wasm_rt_func_type_t t){u32 h;memcpy(&h,t,4);return h&4095;}
static void initialize(void){
'''+ '\n'.join(rows)+f'''
  for(u32 n=0;n<{len(types)};n++){{if(!types[n])continue;u32 at=hash_type(types[n]);while(lookup[at])at=(at+1)&4095;lookup[at]=n+1;}}
}}
u64 ZemaSocialResolve(wasm_rt_funcref_table_t* table,wasm_rt_func_type_t type,u64 index){{
  if(index>UINT32_MAX)return table->size; /* existing slow check takes a u32 */
  if(index<{base}||index>={base+4}||!type||table->size<{base+plan['count']})return index;
  u32 at=hash_type(type);for(u32 n=0;n<4096&&lookup[at];n++,at=(at+1)&4095){{u32 t=lookup[at]-1;if(!memcmp(type,types[t],32))return mapping[t][index-{base}];}}return index;
}}
int ZemaSocialInstall(w2c_game* instance){{
  pthread_once(&once,initialize);wasm_rt_funcref_table_t* table=w2c_game_0x5F_indirect_function_table(instance);
  if(table->size!={base}||wasm_rt_grow_funcref_table(table,{plan['count']},wasm_rt_funcref_null_value)!={base})return 0;
  for(u32 n=0;n<{len(types)};n++)if(!types[n])return 0;
  for(u32 n={base};n<{base+4};n++)table->data[n].module_instance=instance;
'''+ '\n'.join(init)+f'''
  return 1;
}}
static pthread_mutex_t object_lock=PTHREAD_MUTEX_INITIALIZER;
static int prepared;
int ZemaSocialPrepare(void* instance){{
  if(!ZemaProfileReady())return 0;pthread_mutex_lock(&object_lock);if(prepared){{pthread_mutex_unlock(&object_lock);return 1;}}
  u64 size=0;uint8_t* m=mugoat_memory_data(instance,&size);if(!m||size<15211688){{pthread_mutex_unlock(&object_lock);return 0;}}
  u64 block=ZemaEngineAllocate(instance,1040);m=mugoat_memory_data(instance,&size);
  if(!block||block>size||1040>size-block){{pthread_mutex_unlock(&object_lock);return 0;}}
  u64 profile=block,other=block+8,pt=block+16,ot=block+528;
  write64(instance,profile,pt);write64(instance,other,ot);
  for(u32 n=0;n<64;n++){{write64(instance,pt+n*8,n==0?{base}:n==1?{base+2}:n==3?{base+3}:{base+1});write64(instance,ot+n*8,n==0?{base}:{base+1});}}
  for(u32 offset=88;offset<216;offset+=8)write64(instance,15211472+offset,offset==96?profile:other);
  prepared=1;pthread_mutex_unlock(&object_lock);return 1;
}}
'''
    return header,source,plan

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--engine',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    contract=json.loads(gate.CONTRACT.read_text());data=a.engine.read_bytes();gate.inspect(data,contract);types,_,names=gate.module_abi(data)
    if names.get('emscripten_builtin_malloc')!=[91000] or names.get('emscripten_builtin_free')!=[91002]:raise ValueError('Allocator ABI pin changed')
    if a.output.exists() or any(x.is_symlink() for x in (a.output,*a.output.parents)):raise ValueError('New non-symlink output required')
    h,c,plan=native(types);a.output.mkdir(mode=0o700)
    (a.output/'ZemaSocial.h').write_text(h);(a.output/'ZemaSocial.c').write_text(c);(a.output/'social-tables.json').write_text(json.dumps(plan,indent=2)+'\n')
    print(json.dumps({'types':len(types),'table_entries':plan['count'],'output':str(a.output)}))
