"""Plan the native counterpart of the reviewed scoped script-bank browser hook.

Reads pinned original WASM and existing generated C; returns patched copies and
new helper files. The optional CLI writes only a new output directory. It never
changes a generated input, app stage, original Intel folder or IPA.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat

import script_bank

ROOT = Path(__file__).resolve().parent
C_PINS = {
    21855: {'part':'game_9.c', 'length':28445,
            'sha256':'6a2bcc35b36c577f1327da23ef7925099798dcbe67ab9da9f8937d297faaad63',
            'signature':'u32 w2c_game_f21855(w2c_game* instance, u32 var_p0, u32 var_p1, u32 var_p2)'},
    7226: {'part':'game_48.c', 'length':1836,
           'sha256':'504b776159beb1dfe677de40028026d58e170f62dcc6c56709b62002ff4c7080',
           'signature':'u32 w2c_game_f7226(w2c_game* instance, u64 var_p0, u32 var_p1)'}
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def patch_part(data, hooks):
    """Rename only exact original definitions; every call site stays unchanged."""
    text = data.decode('utf-8')
    if not hooks:
        raise ValueError('Empty native script-bank patch')
    if len({h['index'] for h in hooks}) != len(hooks):
        raise ValueError('Repeated native script-bank hook')
    for hook in hooks:
        if hook not in script_bank.HOOKS:
            raise ValueError('Unreviewed native script-bank hook')
        index = hook['index']
        pin = C_PINS[index]
        symbol = 'w2c_game_f' + str(index)
        if symbol + '_zema_script_bank_original' in text:
            raise ValueError('Native script-bank C already patched')
        pattern = re.compile(r'(?ms)^u32 ' + symbol + r'\([^\n]*\) \{\n.*?^\}')
        matches = list(pattern.finditer(text))
        if len(matches) != 1:
            raise ValueError('Missing or duplicate native script-bank C definition: ' + symbol)
        match = matches[0]
        original = match[0].encode('utf-8')
        if (not match[0].startswith(pin['signature'] + ' {\n') or
                len(original) != pin['length'] or digest(original) != pin['sha256']):
            raise ValueError('Native script-bank C bytes/ABI changed: ' + symbol)
        renamed = match[0].replace(symbol + '(', symbol + '_zema_script_bank_original(', 1)
        text = text[:match.start()] + renamed + text[match.end():]
    return text.encode('utf-8')


def render():
    header = '''/* Exact generated C ABI; no untyped callback or table patch. */
#ifndef ZEMA_NATIVE_SCRIPT_BANK_H
#define ZEMA_NATIVE_SCRIPT_BANK_H
#include "game.h"
u32 w2c_game_f21855_zema_script_bank_original(w2c_game*,u32,u32,u32);
u32 w2c_game_f7226_zema_script_bank_original(w2c_game*,u64,u32);
#endif
'''
    return {'ZemaNativeScriptBank.h':header.encode('utf-8'),
            'ZemaNativeScriptBank.c':(ROOT/'native_script_bank.c.in').read_bytes()}


def transform_generated(engine_data, generated):
    """Pure staging plan: (modified part copies, helper copies, bounded receipt)."""
    hooks = script_bank.inspect(engine_data)  # Original SHA, names, WASM ABI/body pins.
    inspection = script_bank.b.gate.inspect_generated(Path(generated), hooks)
    groups = {}
    for row in inspection['definitions']:
        hook = next(h for h in hooks if h['field'] == row['field'])
        if row['part'] != C_PINS[hook['index']]['part']:
            raise ValueError('Native script-bank generated part moved')
        groups.setdefault(row['part'], []).append(hook)
    patches, receipts = {}, []
    for part, selected in groups.items():
        original = (Path(generated)/part).read_bytes()
        patches[part] = patch_part(original, selected)
        receipts.append({'part':part, 'before_sha256':digest(original),
                         'after_sha256':digest(patches[part]),
                         'functions':[dict(h, c_body_sha256=C_PINS[h['index']]['sha256']) for h in selected]})
    helpers = render()
    receipt = {'format':'zema-native-script-bank-plan-v1', 'engine_sha256':digest(engine_data),
               'upstream_revision':script_bank.UPSTREAM, 'parts':receipts,
               'helpers':{name:digest(data) for name,data in helpers.items()},
               'scope':'THREAD_LOCAL_NESTED_ORIGINAL_SCRIPT_REQUEST_ONLY',
               'retry':'NONE_SAME_ORIGINAL_REQUEST_STATUS_QUERY',
               'outside_request_status':'UNCHANGED', 'stored_bank_state':'UNCHANGED',
               'runtime_verified':False, 'gameplay_verified':False, 'inputs_modified':False}
    return patches, helpers, receipt


def verify_generated(engine_data, generated):
    """Verify a patched stage using its bounded receipt; never read old stages."""
    hooks = script_bank.inspect(engine_data)
    generated = Path(generated)
    if any(p.is_symlink() for p in (generated,*generated.parents)):
        raise ValueError('Native script-bank generated path must not contain symlinks')
    receipt_path = generated/'native-script-bank-plan.json'
    if receipt_path.is_symlink() or not receipt_path.is_file() or receipt_path.stat().st_size > 262144:
        raise ValueError('Bounded regular native script-bank receipt required')
    receipt = json.loads(receipt_path.read_text())
    if (receipt.get('format') != 'zema-native-script-bank-plan-v1' or
            receipt.get('engine_sha256') != script_bank.ENGINE_SHA256 or
            receipt.get('upstream_revision') != script_bank.UPSTREAM or
            receipt.get('scope') != 'THREAD_LOCAL_NESTED_ORIGINAL_SCRIPT_REQUEST_ONLY' or
            receipt.get('retry') != 'NONE_SAME_ORIGINAL_REQUEST_STATUS_QUERY' or
            receipt.get('outside_request_status') != 'UNCHANGED' or
            receipt.get('stored_bank_state') != 'UNCHANGED' or
            receipt.get('runtime_verified') is not False or
            receipt.get('gameplay_verified') is not False or
            receipt.get('inputs_modified') is not False):
        raise ValueError('Unexpected native script-bank receipt contract')
    expected_helpers = render()
    if receipt.get('helpers') != {name:digest(data) for name,data in expected_helpers.items()}:
        raise ValueError('Native script-bank helper receipt changed')
    for name,expected in expected_helpers.items():
        file = generated/name
        if file.is_symlink() or not file.is_file() or file.read_bytes() != expected:
            raise ValueError('Native script-bank helper bytes changed: '+name)
    rows = receipt.get('parts')
    if not isinstance(rows,list) or len(rows)!=len(C_PINS):
        raise ValueError('Native script-bank receipt parts changed')
    by_part = {row.get('part'):row for row in rows if isinstance(row,dict)}
    if set(by_part) != {pin['part'] for pin in C_PINS.values()}:
        raise ValueError('Native script-bank receipt parts changed')
    # Locate actual definitions across the stage's normal 64 translation units.
    files = sorted(generated.glob('game_*.c'))
    if {p.name for p in files} != {'game_'+str(i)+'.c' for i in range(64)}:
        raise ValueError('Expected complete native script-bank generated stage')
    found = []
    pattern = re.compile(rb'(?m)^(?:static )?\w+ w2c_game_f(21855|7226)(_zema_script_bank_original)?\(')
    for file in files:
        if file.is_symlink() or not file.is_file():
            raise ValueError('Regular generated C required')
        data = file.read_bytes()
        for match in pattern.finditer(data):
            index = int(match[1])
            if not match[2] or file.name != C_PINS[index]['part']:
                raise ValueError('Native script-bank wrapper definition moved or unpatched')
            found.append(index)
        if file.name not in by_part:
            continue
        row = by_part[file.name]
        selected = [h for h in hooks if C_PINS[h['index']]['part']==file.name]
        if row.get('functions') != [dict(h,c_body_sha256=C_PINS[h['index']]['sha256']) for h in selected]:
            raise ValueError('Native script-bank receipt hook pins changed')
        if digest(data) != row.get('after_sha256'):
            raise ValueError('Native script-bank transformed part bytes changed')
        restored = data
        for hook in selected:
            symbol = ('w2c_game_f'+str(hook['index'])).encode()
            original = C_PINS[hook['index']]['signature'].encode()
            renamed = original.replace(symbol,symbol+b'_zema_script_bank_original')
            if restored.count(renamed+b' {\n')!=1:
                raise ValueError('Native script-bank transformed definition changed')
            restored = restored.replace(renamed+b' {\n',original+b' {\n',1)
        if digest(restored) != row.get('before_sha256') or patch_part(restored,selected) != data:
            raise ValueError('Native script-bank original function reconstruction failed')
    if sorted(found) != sorted(C_PINS):
        raise ValueError('Missing or duplicate native script-bank original definitions')
    return receipt


def write_plan(output, patches, helpers, receipt):
    """Write copies only, rejecting existing/symlink output paths."""
    output = Path(output).absolute()
    if output.exists() or any(p.is_symlink() for p in (output,*output.parents)):
        raise ValueError('New non-symlink native script-bank output required')
    if not output.parent.is_dir():
        raise ValueError('Output parent must already exist')
    output.mkdir(mode=0o700)
    for name, data in {**patches, **helpers, 'native-script-bank-plan.json':(json.dumps(receipt,indent=2)+'\n').encode()}.items():
        if Path(name).name != name:
            raise ValueError('Unsafe native script-bank output filename')
        with (output/name).open('xb') as file:
            file.write(data)
        (output/name).chmod(stat.S_IRUSR | stat.S_IWUSR)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine',type=Path,required=True)
    parser.add_argument('--generated',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    patches,helpers,receipt = transform_generated(args.engine.read_bytes(),args.generated)
    write_plan(args.output,patches,helpers,receipt)
    print(json.dumps({'output':str(args.output),'parts':len(patches),'hooks':len(script_bank.HOOKS),'runtime_verified':False}))

if __name__ == '__main__':
    main()
