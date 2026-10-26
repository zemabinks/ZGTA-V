"""Typed bridge to wasm2c exports and game-thread multiplayer hooks."""
import json
import re
from pathlib import Path

TAGS = {'u32': 1, 'u64': 2, 'f32': 3, 'f64': 4}

def declarations(header):
    pattern = r"/\* export: '([^']+)' \*/\s*([^;]+);"
    found = {}
    for name, declaration in re.findall(pattern, header):
        m = re.fullmatch(r'(\w+)(\*)?\s+(\w+)\(w2c_game\*(?:\s+instance)?(?:,\s*(.*))?\)', declaration.strip())
        if not m: continue
        result, pointer, symbol, params = m.groups()
        found[name] = (result + (pointer or ''), symbol, [p.strip() for p in params.split(',')] if params else [])
    return found

def generate(header, metadata):
    exports = declarations(header)
    names = [name for name in metadata['exports'] if name.startswith('mp:')] + ['emscripten_stack_get_current', '_emscripten_stack_alloc', '_emscripten_stack_restore']
    info, calls = [], []
    for name in names:
        result, symbol, params = exports[name]
        if result not in TAGS and result != 'void': raise ValueError('Unsupported result: ' + result)
        if any(p not in TAGS for p in params): raise ValueError('Unsupported parameter: ' + name)
        assignments = ''.join(f'p[{i}]={TAGS[t]};' for i, t in enumerate(params))
        info.append(f'if(!strcmp(name,{json.dumps(name)})) {{ if(capacity<{len(params)})return -2; {assignments} *result={TAGS.get(result,0)}; return {len(params)}; }}')
        args = [f'(u32)a[{i}].bits' if t == 'u32' else f'(u64)a[{i}].bits' if t == 'u64' else f'online_{t}(a[{i}].bits)' for i, t in enumerate(params)]
        invocation = f'{symbol}((w2c_game*)instance' + ''.join(',' + a for a in args) + ')'
        checks = ' || '.join(f'a[{i}].type!={TAGS[t]}' for i, t in enumerate(params)) or 'false'
        if result == 'void': body = invocation + '; out->type=0;out->bits=0;'
        elif result in ('u32','u64'): body = f'out->type={TAGS[result]};out->bits={invocation};'
        else: body = f'{result} value={invocation};out->type={TAGS[result]};out->bits=0;memcpy(&out->bits,&value,sizeof value);'
        calls.append(f'if(!strcmp(name,{json.dumps(name)})) {{ if(count!={len(params)} || ({checks}))return false; {body} return true; }}')
    tls_type, tls_symbol, tls_params = exports['mugoat:tls-base']
    if tls_type != 'u64*' or tls_params: raise ValueError('Unexpected TLS export')
    aliases = []
    for name, index in metadata.get('indices', {}).items():
        if name in exports:
            result, symbol, params = exports[name]
            param_defs = ', '.join([f'{t} a{i}' for i, t in enumerate(params)])
            param_names = ''.join([f', a{i}' for i in range(len(params))])
            full_params = f'w2c_game *instance' + (f', {param_defs}' if param_defs else '')
            call_args = f'instance{param_names}'
            ret = 'return ' if result != 'void' else ''
            aliases.append(f'{result} w2c_game_f{index}({full_params}) {{ {ret}{symbol}({call_args}); }}')
    source = '''#include "HostInternal.h"
#include "MugoatOnline.h"
#include <string.h>
static f32 online_f32(uint64_t bits){f32 v;uint32_t b=(uint32_t)bits;memcpy(&v,&b,4);return v;}
static f64 online_f64(uint64_t bits){f64 v;memcpy(&v,&bits,8);return v;}
int mugoat_command_info(const char *name,uint32_t *p,uint32_t capacity,uint32_t *result){
'''+ '\n'.join(info) + '''
return -1;}
bool mugoat_command_call(void *instance,const char *name,const MugoatValue *a,uint32_t count,MugoatValue *out){
'''+ '\n'.join(calls) + '''
return false;}
uint8_t *mugoat_memory_data(void *instance,uint64_t *size){
 struct w2c_env *host=(struct w2c_env*)((uint8_t*)instance - offsetof(struct w2c_env,game));
 extern wasm_rt_shared_memory_t *w2c_env_memory(struct w2c_env*);
 wasm_rt_shared_memory_t *memory=w2c_env_memory(host);
 *size=memory->size;return (uint8_t*)(void*)memory->data;
}
''' + '\n'.join(aliases) + '\n'
    return source, tls_symbol

def patch_hook(source, index, injection):
    m = re.search(r'\n(?:void|u32|u64|f32|f64) w2c_game_f' + str(index) + r'\([^\n]+\) \{\n', source)
    if not m: return None
    # Keep local declarations intact and run within the engine's stack guard.
    prologue = source.index('  FUNC_PROLOGUE;', m.end()) + len('  FUNC_PROLOGUE;')
    if source.find('\n}', m.end()) < prologue: raise ValueError('Invalid hook function')
    return source[:prologue] + '\n  ' + injection + source[prologue:]

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    generated = root / 'Generated'
    metadata = json.loads((generated / 'online-game.json').read_text())
    source, tls = generate((generated/'game.h').read_text(), metadata)
    (generated/'MugoatCommands.c').write_text(source)
    injections = {'script': f'mugoat_script_tick(instance,var_p0,*{tls}(instance));',
                  'explosion': 'mugoat_explosion(var_p0);',
                  'timewarp': 'var_p1=mugoat_time_warp(var_p1);'}
    for key, index in metadata['hooks'].items():
        matches = []
        for path in generated.glob('game_*.c'):
            original = path.read_text()
            patched = patch_hook(original, index, injections[key])
            if patched is not None:
                patched = '#include "MugoatOnline.h"\n' + patched
                path.write_text(patched); matches.append(path.name)
        if len(matches) != 1: raise ValueError(f'{key} hook matched {matches}; expected one function')
        print(f'Native online {key}: original f{index} in {matches[0]}')
