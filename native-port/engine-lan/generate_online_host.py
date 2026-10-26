"""Generate strictly typed original/callback routing from the pinned hook ABI.

Writes only the explicit new online-host source directory, never game C/IPA.
No game execution, unchecked indirect calls, dependency resolution or network.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTRACT = ROOT.parent/'app/Tests/glue5_engine_lan_contract.json'
TYPES = {'i32':'uint32_t','i64':'uint64_t','f32':'float','f64':'double'}

def generate():
    contract=json.loads(CONTRACT.read_text())
    hooks=[h for h in contract['hooks'] if h['group']!='vnet']
    assert len(hooks)==52
    fields=[]; declarations=[]; adapters=[]; assignments=[]; requires=[]
    for h in hooks:
        result=TYPES[h['results'][0]] if h['results'] else 'void'
        params=['void* instance']+[TYPES[t]+f' a{i}' for i,t in enumerate(h['params'])]
        args=['instance']+[f'a{i}' for i in range(len(h['params']))]
        signature=', '.join(params);field=h['field']
        fields.append(f'  {result} (*{field})({signature});')
        declarations.append(f'{result} ZemaOnline_{field}({signature});')
        cp=['w2c_game* instance']+[{'i32':'u32','i64':'u64','f32':'f32','f64':'f64'}[t]+f' a{i}' for i,t in enumerate(h['params'])]
        cr={'uint32_t':'u32','uint64_t':'u64','float':'f32','double':'f64','void':'void'}[result]
        original=f'w2c_game_f{h["index"]}_zema_lan_original'
        invoke=f'{original}((w2c_game*)instance'+''.join(','+a for a in args[1:])+')'
        adapters.append(f'static {result} original_{field}({signature}) {{ '+('return ' if result!='void' else '')+invoke+'; }')
        adapters.append(f'static {cr} callback_{field}('+', '.join(cp)+') { '+('return ' if result!='void' else '')+f'ZemaOnline_{field}('+', '.join(['(void*)instance']+args[1:])+'); }')
        assignments.append(f'  originals->{field}=original_{field}; hooks->{field}=callback_{field};')
        requires.append(f'host->originals.{field}')
    header='''/* Generated from the exact pinned glue5 engine contract. */
#ifndef ZEMA_ONLINE_HOST_H
#define ZEMA_ONLINE_HOST_H
#include <stdint.h>
#include <stddef.h>
typedef struct ZemaOnlineOriginals {
'''+ '\n'.join(fields)+'''
} ZemaOnlineOriginals;
typedef struct {
  uint32_t version;
  uint8_t* (*memory)(void*,uint64_t*);
  uint64_t (*allocate)(void*,uint64_t);
  void (*release)(void*,uint64_t);
  /* Must install signature-correct Social Club tables before returning 1.
   * A missing/unverified table must return 0; no generic function-pointer cast. */
  int (*prepare_interfaces)(void*);
  /* Synchronous atomic persistence of the whole isolated profile. Failure
   * must retain the previous disk snapshot and return 0. */
  int (*commit_profile)(void*);
  ZemaOnlineOriginals originals;
} ZemaOnlineHost;
int ZemaOnlineInstallHost(const ZemaOnlineHost*,size_t);
int ZemaOnlineConfigured(void);
int ZemaOnlineInterfacesReady(void);
'''+ '\n'.join(declarations)+ '\n#endif\n'
    binding='''/* Typed native adapters. Not linked into the existing app target. */
#include "ZemaOnlineHost.h"
#include "ZemaEngineLAN.h"
'''+ '\n'.join(adapters)+'''
void ZemaOnlineBindOriginals(ZemaOnlineOriginals* originals,ZemaEngineLANHooks* hooks) {
'''+ '\n'.join(assignments)+'\n}\n'
    check='/* Generated completeness check. */\n#define ZEMA_ONLINE_COMPLETE(host) (' + ' && '.join(requires) + ')\n'
    return {'ZemaOnlineHost.h':header,'OnlineBindings.c':binding,'OnlineComplete.h':check}

if __name__=='__main__':
    for name,text in generate().items():
        target=ROOT/name
        if target.is_symlink():raise ValueError('Refuse symlinked output')
        target.write_text(text)
