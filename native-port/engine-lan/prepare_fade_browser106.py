"""Rebuild scoped draw-time fade lifetime, retaining every earlier phase pin.

Only the fade lifetime changes relative to Build104; the GPU worker is unchanged.
No mirror mutation, game execution, network protocol change or relaxed input pin.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import browser_features as features
import browser_wasm as b
import engine_safety
import local_save_gamer
import online_wasm
import open_rpf
import package_portable
import prepare_session_browser
import prepare_vehicle_browser
import render_hooks
import reproduce_browser102 as historical
import prepare_fade_browser104 as prior
import save_worker_probe

OUTPUTS = {
    'game.engine-lan.wasm': '0166c50acc3a9800a6d3ff2efb909dab377b9f75faa30d46f5f943a77b8a6507',
    'game.features.offline.wasm': '438210e58f21854a0fc5aa5c53e2a444610c37345f0e1209f889b4fec38cb0b8',
}
WORKER = 'eb37e248e5ec3dd9579ec12a82c64032e18c32b1dd1ff95a8647c44481a9454f'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def source_modules(original, contract):
    if sha(original) != features.ORIGINAL:
        raise ValueError('Unreviewed original engine')
    base, _ = online_wasm.feature_base(original, contract)
    output, proofs = {}, []
    for mode in ('lan', 'offline'):
        data = base if mode == 'lan' else original
        before = data
        phases = []
        def record(name, value, historical_pin=True):
            nonlocal data
            data = value[0] if isinstance(value, tuple) else value
            digest = sha(data)
            if historical_pin and digest != historical.EXPECTED[mode][len(phases)]:
                raise ValueError('Earlier phase changed: ' + mode + '/' + name)
            phases.append({'phase': name, 'sha256': digest})
        record('base', data)
        record('features', features.transform(data))
        if mode == 'lan':
            record('socket_close', b.append_socket_close(data))
            record('local_save_gamer', local_save_gamer.append(data))
            record('save_worker', save_worker_probe.append(data))
        record('engine_safety', engine_safety.transform(data))
        record('vehicle_query_exports', prepare_vehicle_browser.transform(data))
        if mode == 'lan':
            record('direct_session_exports', prepare_session_browser.transform(data))
        record('open_rpf', open_rpf.transform(data))
        data, hook_receipt = render_hooks.append(data)
        record('draw_fade_lifetime106', data, False)
        filename = 'game.engine-lan.wasm' if mode == 'lan' else 'game.features.offline.wasm'
        output[filename] = (data, hook_receipt)
        proofs.append({'mode': mode, 'phases': phases,
                       'body_proof': historical.body_proof(before, data, mode == 'lan', [r['index'] for r in render_hooks.LIFETIME_PINS])})
    return output, proofs

def stage(previous, engine, worker, output):
    previous, output = Path(previous).absolute(), Path(output).absolute()
    app = Path(__file__).resolve().parents[1] / 'app'
    if output.parent != app.absolute() / 'Build' or output.exists():
        raise ValueError('A distinct new local Build stage is required')
    if any(p.is_symlink() for p in (previous, output, *output.parents)):
        raise ValueError('Regular stage paths required')
    proof = package_portable.checked_runtime(previous)
    metadata = json.loads((previous / 'engine-lan-module.json').read_text())
    offline = json.loads((previous / 'browser-features-module.js').read_text()
                         .removeprefix('globalThis.ZemaBrowserFeaturesModule=').removesuffix(';\n'))
    if metadata['patched_sha256'] != prior.OUTPUTS['game.engine-lan.wasm'] or offline['patched_sha256'] != prior.OUTPUTS['game.features.offline.wasm']:
        raise ValueError('Expected reviewed Build104/105 module pair')
    modules, phases = source_modules(Path(engine).read_bytes(), json.loads(b.gate.CONTRACT.read_text()))
    for name, (data, _) in modules.items():
        if sha(data) != OUTPUTS.get(name):
            raise ValueError('New fade module output differs: ' + name)
    worker_data = Path(worker).read_bytes()
    if sha(worker_data) != WORKER:
        raise ValueError('New fade GPU worker output differs')
    output.mkdir(mode=0o700)
    names = set(proof['staged_hashes']) | {'engine-lan-module.js', 'engine-lan-module.json', 'browser-stage.json'}
    for name in names:
        shutil.copy2(previous / name, output / name)
    (output / 'wgpu_worker.js').write_bytes(worker_data)
    for name, (data, receipt) in modules.items():
        (output / name).write_bytes(data)
        target = metadata['features'] if name == 'game.engine-lan.wasm' else offline
        target.update(patched_sha256=sha(data), render_hooks=receipt)
    metadata['patched_sha256'] = metadata['features']['patched_sha256']
    (output / 'engine-lan-module.json').write_text(json.dumps(metadata) + '\n')
    (output / 'engine-lan-module.js').write_text('globalThis.ZemaEngineLanModule=' + json.dumps(metadata) + ';\n')
    (output / 'browser-features-module.js').write_text('globalThis.ZemaBrowserFeaturesModule=' + json.dumps(offline) + ';\n')
    record = json.loads((output / 'browser-stage.json').read_text())
    record['staged_hashes'] = {name: sha((output / name).read_bytes()) for name in record['staged_hashes']}
    record['runtime_verified'] = False
    record['fade_lifetime106'] = {'format': 'zgta-draw-fade-lifetime106-v1', 'phases': phases,
        'same_network_protocol': True, 'owner_visual_acceptance': 'PENDING'}
    (output / 'browser-stage.json').write_text(json.dumps(record, indent=2) + '\n')
    checked = package_portable.checked_runtime(output)
    return {'output': str(output), 'runtime': checked, 'phases': phases,
            'actual_gameplay': 'NOT_TESTED', 'source_input_pins_relaxed': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'engine', 'worker', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.previous, args.engine, args.worker, args.output), indent=2))
