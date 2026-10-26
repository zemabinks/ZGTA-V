#!/usr/bin/env python3
"""Generate an experimental C callback boundary; never enable engine LAN.

Uses glue5's pinned public hook interface with the current wasm2c C ABI.
Outputs only a header, wrappers and an exact-byte patch plan in a new isolated
Build folder. It does not apply that plan, compile, discover peers or run apps.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import inspect_engine_lan as gate

ROOT = Path(__file__).resolve().parents[1]
C_TYPES = {'i32': 'u32', 'i64': 'u64', 'f32': 'f32', 'f64': 'f64'}


def signature(hook):
    if (not re.fullmatch(r'[a-z][a-z0-9_]*', hook['field'])
            or type(hook['index']) is not int or hook['index'] < 0
            or len(hook['results']) > 1):
        raise ValueError('Invalid C hook identity/signature')
    try:
        result = C_TYPES[hook['results'][0]] if hook['results'] else 'void'
        params = ['w2c_game* instance'] + [C_TYPES[t] + ' arg' + str(i)
                                           for i, t in enumerate(hook['params'])]
    except KeyError as error:
        raise ValueError('Unsupported native C hook type') from error
    args = ['instance'] + ['arg' + str(i) for i in range(len(hook['params']))]
    return result, ', '.join(params), ', '.join(args)


def render(hooks):
    if (not hooks or len({h['field'] for h in hooks}) != len(hooks)
            or len({h['index'] for h in hooks}) != len(hooks)):
        raise ValueError('Empty or duplicate adapter hooks')
    fields, declarations, wrappers = [], [], []
    for hook in hooks:
        result, params, args = signature(hook)
        field, name = hook['field'], 'w2c_game_f' + str(hook['index'])
        original = name + '_zema_lan_original'
        fields.append(f'  {result} (*{field})({params});')
        declarations.append(f'{result} {original}({params});')
        returned = 'return ' if result != 'void' else ''
        end = '' if result != 'void' else '\n    return;'
        wrappers.append(f'''{result} {name}({params}) {{
  if (atomic_load_explicit(&installed, memory_order_acquire) == 2 && callbacks.{field}) {{
    {returned}callbacks.{field}({args});{end}
  }}
  {returned}{original}({args});
}}''')
    header = '''/* Generated zema engine-LAN ABI boundary; runtime not enabled.
 * Interface provenance: mempage4k/glue5, pinned by the adjacent patch plan.
 */
#ifndef ZEMA_ENGINE_LAN_H
#define ZEMA_ENGINE_LAN_H
#include "game.h"
typedef struct ZemaEngineLANHooks {
''' + '\n'.join(fields) + '''
} ZemaEngineLANHooks;
/* One immutable installation, before engine workers start. Missing callbacks
 * always delegate to the original game functions. No reset or hot swap. */
int ZemaEngineLANInstall(const ZemaEngineLANHooks* hooks);
''' + '\n'.join(declarations) + '\n#endif\n'
    source = '''/* Generated callback routing only; not a network backend. */
#include "ZemaEngineLAN.h"
#include <stdatomic.h>
static ZemaEngineLANHooks callbacks;
static atomic_int installed = 0;
int ZemaEngineLANInstall(const ZemaEngineLANHooks* hooks) {
  int expected = 0;
  if (!hooks || !atomic_compare_exchange_strong(&installed, &expected, 1)) return 0;
  callbacks = *hooks;
  atomic_store_explicit(&installed, 2, memory_order_release);
  return 1;
}
''' + '\n\n'.join(wrappers) + '\n'
    return header, source


def patch_part(data, hooks, expected):
    """Return planned bytes only; rename definitions, never call sites/indices."""
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Cached generated C bytes changed; refuse patch plan')
    text = data.decode('utf-8')
    if '_zema_lan_original' in text:
        raise ValueError('C input already contains adapter originals')
    for hook in hooks:
        name = 'w2c_game_f' + str(hook['index'])
        pattern = re.compile(r'(?m)^(\w+ )' + name + r'(\(w2c_game\*[^;{}]*\) \{)')
        if len(pattern.findall(text)) != 1:
            raise ValueError('Missing or ambiguous original C definition: ' + name)
        text = pattern.sub(lambda m: m[1] + name + '_zema_lan_original' + m[2], text)
    return text.encode('utf-8')


def patch_plan(generated, inspection):
    hooks = {h['field']: h for h in inspection['hooks']}
    parts = {}
    for row in inspection['generated_c']['definitions']:
        parts.setdefault(row['part'], []).append(row)
    plan = []
    for name, rows in sorted(parts.items()):
        selected = [hooks[row['field']] for row in rows]
        old = (generated / name).read_bytes()
        new = patch_part(old, selected, rows[0]['part_sha256'])
        plan.append({'part': name, 'before_sha256': rows[0]['part_sha256'],
                     'planned_sha256': hashlib.sha256(new).hexdigest(),
                     'fields': [h['field'] for h in selected]})
    return plan


def write_adapter(output, header, source, plan, root=ROOT):
    build = root.absolute() / 'Build'
    output = output.absolute()
    if '..' in output.parts or output.parent != build or output.exists():
        raise ValueError('Use a new immediate child of the isolated app Build folder')
    for path in (output, *output.parents):
        if path.is_symlink():
            raise ValueError('Adapter output paths must not be symlinks')
    build.mkdir(exist_ok=True)
    output.mkdir(mode=0o700)
    for name, content in [('ZemaEngineLAN.h', header), ('ZemaEngineLAN.c', source),
                          ('patch-plan.json', json.dumps(plan, indent=2) + '\n')]:
        with (output / name).open('x') as target:
            target.write(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--generated', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        contract = json.loads(gate.CONTRACT.read_text())
        gate.verify_reference(args.reference, contract)
        result = gate.inspect(args.engine.read_bytes(), contract)
        result['generated_c'] = gate.inspect_generated(args.generated, result['hooks'])
        header, source = render(result['hooks'])
        plan = {'format': 'zema-engine-lan-adapter-plan-v1',
                'upstream_revision': contract['upstream_revision'],
                'engine_sha256': contract['engine_sha256'],
                'parts': patch_plan(args.generated, result), 'plan_applied': False,
                'runtime_enabled': False, 'network_backend_implemented': False,
                'browser_integration': 'NOT_IMPLEMENTED'}
        write_adapter(args.output, header, source, plan)
        print(json.dumps({'output': str(args.output), 'hooks': len(result['hooks']),
                          'parts': len(plan['parts']), 'plan_applied': False,
                          'runtime_enabled': False}))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
