"""Pinned access to GTA's original Public Session transition, without menu input."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTRACT = {
    'program_hash': 1392012650, 'code_size': 889405, 'statics': 1544, 'argument_cells': 4,
    'entry': 15844, 'end': 21033,
    'entry_sha256': '5c6be1369a9ff41d9ccfa3f0beea3e0a68c374a5ccb17ea200515c0121fcbd64',
    'route_static': 1399, 'route_count': 4, 'category': 14, 'subcategory': 0,
    'stack_capacity': 4096,
}
COMMANDS = [
 ('SessionRequestScript','script_commands::RequestScriptWithNameHash(int)',59357,['i32'],[]),
 ('SessionScriptLoaded','script_commands::HasScriptWithNameHashLoaded(int)',59361,['i32'],['i32']),
 ('SessionGetProgram','rage::scrProgram::GetProgram(rage::scrProgramId)',16934,['i32'],['i64']),
 ('SessionCreateTask','CTheScripts::GtaStartNewThreadWithProgramId(rage::scrProgramId, void const*, int, int, char const*)',63763,['i32','i64','i32','i32','i64'],['i32']),
 ('SessionGetTask','rage::scrThread::GetThread(rage::scrThreadId)',16981,['i32'],['i64']),
 ('SessionKillTask','rage::scrThread::KillThread(rage::scrThreadId)',16999,['i32'],[]),
]

def validate_abi(types, indices, names):
    for alias,name,index,params,results in COMMANDS:
        if names.get(name) != [index] or types[indices[index]] != (params,results):
            raise ValueError('Session restart engine ABI changed: '+alias)


def write_contract():
    return json.dumps(CONTRACT,sort_keys=True,separators=(',',':'))
