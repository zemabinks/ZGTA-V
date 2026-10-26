"""Add typed world-tool dispatch to a NEW Intel stage without regenerating shaders.

Every added native is pinned to the original engine's full name, index and ABI.
The existing generated dispatch and all game translation units remain intact.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'app/Scripts'))
import inspect_engine_lan as gate

ENGINE_SHA = '11ca8d2c04c5e843d18ff4aea4899d72c86973c6b031df334e67c446b2ae83e0'
# alias, complete original engine name, index, parameters, result
COMMANDS = [
    ('IsModelInCdImage', 'streaming_commands::IsModelInCdImage(int)', 60347, ['i32'], ['i32']),
    ('IsModelAVehicle', 'streaming_commands::CommandIsThisModelAVehicle(int)', 60349, ['i32'], ['i32']),
    ('NetworkGetThisScriptIsNetworkScript', 'network_commands::CommandNetworkGetThisScriptIsNetworkScript()', 54842, [], ['i32']),
    ('GetFirstBlipInfoId', 'hud_commands::GetFirstBlipInfoId(int)', 51595, ['i32'], ['i32']),
    ('GetBlipInfoIdCoord', 'hud_commands::GetBlipInfoIdCoord(int)', 51596, ['i64', 'i32'], []),
    ('GetGroundZFor3dCoord', 'misc_commands::CommandGetGroundZFor3dCoord(rage::scrVector const&, float&, bool, bool)', 52844, ['i64', 'i64', 'i32', 'i32'], ['i32']),
    ('RequestCollisionAtCoord', 'streaming_commands::RequestCollisionAtPosn(rage::scrVector const&)', 60328, ['i64'], []),
    ('NewLoadSceneStartSphere', 'streaming_commands::CommandNewLoadSceneStartSphere(rage::scrVector const&, float, int)', 60377, ['i64', 'f32', 'i32'], ['i32']),
    ('NewLoadSceneStop', 'streaming_commands::CommandNewLoadSceneStop()', 60378, [], []),
    ('IsNewLoadSceneActive', 'streaming_commands::CommandIsNewLoadSceneActive()', 60379, [], ['i32']),
    ('IsNewLoadSceneLoaded', 'streaming_commands::CommandIsNewLoadSceneLoaded()', 60380, [], ['i32']),
    ('NetworkHasControlOfEntity', 'network_commands::CommandNetworkHasControlOfEntity(int)', 54908, ['i32'], ['i32']),
    ('NetworkGetEntityIsNetworked', 'network_commands::CommandNetworkGetEntityIsNetworked(int)', 54898, ['i32'], ['i32']),
    ('SetModelAsNoLongerNeeded', 'streaming_commands::CommandMarkModelAsNoLongerNeeded(int)', 60327, ['i32'], []),
]
from session_restart import COMMANDS as SESSION_COMMANDS
COMMANDS += SESSION_COMMANDS
C_TYPES = {'i32': 'u32', 'i64': 'u64', 'f32': 'f32'}
TAGS = {'i32': 1, 'i64': 2, 'f32': 3}
INFO = 'int mugoat_command_info(const char *name,uint32_t *p,uint32_t capacity,uint32_t *result){'
CALL = 'bool mugoat_command_call(void *instance,const char *name,const MugoatValue *a,uint32_t count,MugoatValue *out){'


def additions(data, generated):
    if hashlib.sha256(data).hexdigest() != ENGINE_SHA:
        raise ValueError('Unreviewed world-tool engine')
    types, indices, names = gate.module_abi(data)
    parts = [p.read_text() for p in generated.glob('game_*.c')]
    declarations, info, calls = [], [], []
    for alias, name, index, params, results in COMMANDS:
        if names.get(name) != [index] or types[indices[index]] != (params, results):
            raise ValueError('World-tool name/index/ABI changed: ' + alias)
        result = C_TYPES[results[0]] if results else 'void'
        args = ', '.join(C_TYPES[t] + ' var_p' + str(i) for i, t in enumerate(params))
        signature = f'{result} w2c_game_f{index}(w2c_game* instance' + (', ' + args if args else '') + ')'
        if sum(p.count('\n' + signature + ' {\n') for p in parts) != 1:
            raise ValueError('World-tool generated definition changed: ' + alias)
        declarations.append('extern ' + signature + ';')
        key = json.dumps('mp:' + alias)
        assignments = ''.join(f'p[{i}]={TAGS[t]};' for i, t in enumerate(params))
        capacity = f'if(capacity<{len(params)})return -2; ' if params else ''
        info.append(f'if(!strcmp(name,{key})) {{ {capacity}{assignments} *result={TAGS[results[0]] if results else 0}; return {len(params)}; }}')
        checks = ''.join(f' || a[{i}].type!={TAGS[t]}' for i, t in enumerate(params))
        argv = ''.join(',online_f32(a[' + str(i) + '].bits)' if t == 'f32' else ',' + '(' + C_TYPES[t] + ')a[' + str(i) + '].bits' for i, t in enumerate(params))
        invocation = f'w2c_game_f{index}((w2c_game*)instance{argv})'
        body = f'out->type={TAGS[results[0]]};out->bits={invocation};' if results else invocation + ';out->type=0;out->bits=0;'
        calls.append(f'if(!strcmp(name,{key})) {{ if(count!={len(params)}{checks})return false; {body} return true; }}')
    return '\n'.join(declarations), '\n'.join(info), '\n'.join(calls)


def patch(original, data, generated):
    declarations, info, calls = additions(data, generated)
    if any('"mp:' + alias + '"' in original for alias, *_ in COMMANDS):
        raise ValueError('World-tool dispatch already present')
    if original.count(INFO) != 1 or original.count(CALL) != 1:
        raise ValueError('World-tool dispatch anchor changed')
    return original.replace(INFO, declarations + '\n' + INFO + '\n' + info).replace(CALL, CALL + '\n' + calls)
