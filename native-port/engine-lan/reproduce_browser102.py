"""Reproduce both retained engines in memory from a privately supplied original.

No game execution or output WASM. Every phase keeps its existing exact pins.
"""
import argparse
import hashlib
import json
from pathlib import Path
import browser_features as features
import browser_wasm as b
import engine_safety
import local_save_gamer
import online_wasm
import open_rpf
import prepare_session_browser
import prepare_vehicle_browser
import render_hooks
import save_worker_probe

EXPECTED = {
    'lan': [online_wasm.FEATURE_BASE_SHA256,
        '3f6dfdff90454d3943e73e26c523c0820e57a74f2ae55360bf9f8c48ac90971f',
        '9992cec25e2827f56ca7432fa9df3f926401ffc31fe4f3ed65aac0c7ce6c1591',
        '15bbb51347f2fd655d1702534380382b4014696e60f79a0c5aad0c2d05b4e292',
        'b3f22e87030b882ff8131140c21e83c4275322aaaccff46ce529562579c66919',
        '7c46204042a555e8e9e9660ad3f41504757f059f2b187ebd8cfcf31186c2ba35',
        '9b71157daa37dcec25541fe8ab354f34ffc0a6704a94683b95136cfb7f4eb030',
        'ab52643cff5089a0daf4199dec33622f580eadce80bc51995e8c693c57b3b8f2',
        '634b0e312662d48e1c327755175afa7e1eaacbdb142c24111b05e674e9049ca9',
        '397de91f51cf7c7445b44632d0dfb574efbbbfa7c8d50423c8e1628e03e005ef'],
    'offline': [features.ORIGINAL,
        '27b4c33ad62ef12e2c18bb33c081c28511c64c5d7911771565b4d3f92875a0af',
        '5353df47dde7c26b426935ab911dd235362fffbe5576594643125fffbf9ac01e',
        '05c5101804c83bdf808c0de9e23b2a8d0679d310235dd74461bd8077f02af59b',
        '1e41856fee7ec1ad6b373d6a12caa7fd532ea9ea7f1660f8ff70a1070a6d3928',
        '42426109a88ebb3b141b20945c2065bdaa10b0e2f9c031225e370cfa26dd491d']}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def body_proof(before, after, lan, additional_modified=()):
    old, new = dict(b.gate.sections(before)), dict(b.gate.sections(after))
    types, indices, _ = b.gate.module_abi(before)
    new_types, new_indices, _ = b.gate.module_abi(after)
    r = b.gate.Reader(old[3]); defined = r.count()
    imported = len(indices) - defined
    def bodies(raw):
        r = b.gate.Reader(raw)
        result = [r.take(r.uint()) for _ in range(r.count())]
        r.finish()
        return result
    a, z = bodies(old[10]), bodies(new[10])
    allowed = {1652,7226,10454,21855,35144,35212,77480,1194,
               *engine_safety.SELECTED,*render_hooks.HOOKS}
    allowed.update(additional_modified)
    if lan: allowed.update((184,83013,128,45253,2326))
    changed = {n + imported for n, (x,y) in enumerate(zip(a,z)) if x != y}
    if changed != allowed or len(z) != len(a)+(28 if lan else 23):
        raise ValueError('Unexpected function body changes')
    if types != new_types[:len(types)] or indices != new_indices[:len(indices)]:
        raise ValueError('Original type/function prefix changed')
    for section in old.keys() | new.keys():
        if section not in {0,1,3,4,6,7,8,10} and old.get(section) != new.get(section):
            raise ValueError('Unselected section changed: '+str(section))
    return dict(scope=('after authenticated 60-hook LAN base' if lan else 'authenticated original offline engine'),
        baselineSHA256=sha(before), originalDefinedFunctions=len(a), appendedFunctions=len(z)-len(a),
        modifiedOriginalFunctionIndices=sorted(changed),
        unselectedOriginalBodiesByteIdentical=True,
        originalTypeAndFunctionIndicesPreserved=True,
        importsMemoryElementDataSectionsUnchanged=True)

def reproduce(original, contract, retained):
    if sha(original) != features.ORIGINAL:
        raise ValueError('Unreviewed original engine')
    base, _ = online_wasm.feature_base(original, contract)
    results = []
    for mode in ('lan','offline'):
        data = base if mode == 'lan' else original
        before = data
        phases = []
        def record(name, result):
            nonlocal data
            data = result[0] if isinstance(result,tuple) else result
            digest = sha(data)
            if digest != EXPECTED[mode][len(phases)]:
                raise ValueError('Ordered phase digest changed: '+mode+'/'+name)
            phases.append(dict(phase=name, sha256=digest))
        record('base', data)
        data, metadata = features.transform(data)
        if 'session_restart' in metadata or features.LATER_WORLD_EXPORTS & metadata['exports'].keys():
            raise ValueError('Later metadata leaked into feature base')
        record('features', data)
        if mode == 'lan':
            record('socket_close', b.append_socket_close(data))
            record('local_save_gamer', local_save_gamer.append(data))
            record('save_worker', save_worker_probe.append(data))
        record('engine_safety', engine_safety.transform(data))
        record('vehicle_query_exports', prepare_vehicle_browser.transform(data))
        if mode == 'lan':
            record('direct_session_exports', prepare_session_browser.transform(data))
        record('open_rpf', open_rpf.transform(data))
        record('render_hooks', render_hooks.append_legacy98(data))
        filename = 'game.engine-lan.wasm' if mode == 'lan' else 'game.features.offline.wasm'
        retained_bytes = (retained/filename).read_bytes()
        if data != retained_bytes: raise ValueError('Retained runtime changed: '+filename)
        results.append(dict(mode=mode, phases=phases, retainedSHA256=sha(retained_bytes),
            byteIdentical=True, bodyProof=body_proof(before,data,mode == 'lan')))
    return dict(format='zgta-ordered-browser-producer102-v1',
        originalSHA256=sha(original), existingPinsRelaxed=False,
        runtimeFilesWritten=False, results=results)

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine',type=Path,required=True)
    p.add_argument('--retained',type=Path,required=True)
    a = p.parse_args()
    print(json.dumps(reproduce(a.engine.read_bytes(),json.loads(b.gate.CONTRACT.read_text()),a.retained),indent=2))
