"""Analyze a bounded owner rendering capture without executing the game.

Writes only the explicitly named JSON output. Network addresses, player names,
arbitrary context, original log text and paths are not exported.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re

MAX_INPUT_BYTES = 16 * 1024 * 1024
UINT64_MAX = (1 << 64) - 1
IDENTITY = ('vs', 'ps', 'drawKind', 'vertexBuffer', 'drawArg1', 'drawArg2', 'target', 'depth')
NUMBERS = ('frame', 'snapshotFrame', 'version', 'stipple', 'constantBuffer', 'first', 'num', 'metalIndex')
COUNTERS = ('generation', 'observedDraws', 'constantBufferCopies', 'shadowCopiesUpdated', 'unknownSourceCopies')
METRICS = ('thermalState', 'requestedFrameInterval', 'requestedRenderWidth', 'requestedRenderHeight',
           'thermalScale', 'appFootprintBytes', 'availableMemoryBytes', 'physicalMemoryBytes',
           'metalAllocatedBytes', 'textureAllocatedBytes', 'bufferArenaBytes', 'bufferArenaLiveBytes',
           'bufferArenaRequestedBytes', 'bufferArenaPendingBytes', 'bufferArenaReusableBytes',
           'pendingPipelineCount', 'cpuPipelineWaitMSPerFrame', 'rendererFrameMS', 'rendererP95FrameMS',
           'assetReadErrors', 'textureCreateFailures', 'textureDecodeFailures', 'resourceReclaimFailures')
CAUTIONS = [
    'Only bounded selected observations are available; this is not a complete frame or draw inventory.',
    'Draw signatures are recorded shader/buffer/argument/target proxies, not proof of object identity, material identity or a complementary LOD pair.',
    'Different passes or geometries may legitimately have different masks. Mask variation alone does not prove flicker.',
    'cb2 is only a candidate binding. Some shaders do not read its first float4; disagreement with injected stipple is not automatically a bug.',
    'Bound words come from the CPU-written allocation supplied to Metal, not GPU readback. Encoded draws do not prove final visible pixels.',
    'No producer-time guest mask, Begin/End sequence or reset-origin evidence is included.',
    'An active diagnostic capture is not a clean FPS comparison; requested render dimensions and frame intervals are not GPU readback.',
    'Thermal and frame-interval transitions are observations; this report does not measure hardware clock throttling or establish causation.',
]


def integer(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f'{label}: expected unsigned decimal integer')
    if isinstance(value, str) and not re.fullmatch(r'[0-9]{1,20}', value):
        raise ValueError(f'{label}: invalid integer')
    number = int(value)
    if not 0 <= number <= UINT64_MAX:
        raise ValueError(f'{label}: integer out of range')
    return number


def numeric(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label}: expected finite number')
    return value


def hexword(value, length, label):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-fA-F]{' + str(length) + '}', value):
        raise ValueError(f'{label}: invalid hexadecimal word')
    return value.lower()


def observation(row):
    if not isinstance(row, dict):
        raise ValueError('Observation must be an object')
    result = {}
    for key in IDENTITY + NUMBERS:
        if key not in row:
            raise ValueError(f'Observation missing {key}')
        result[key] = hexword(row[key], 16, key) if key in ('vs', 'ps') else integer(row[key], key)
    if result['stipple'] > 31:
        raise ValueError('Unsupported stipple code')
    for flag in ('encoded', 'shadowValid', 'boundValid'):
        result[flag] = integer(row.get(flag), flag)
        if result[flag] not in (0, 1):
            raise ValueError(f'{flag}: expected 0 or 1')
    for prefix in ('shadow', 'bound'):
        result[prefix] = [hexword(row.get(prefix + str(i)), 8, prefix) for i in range(4)]
    outcome = row.get('outcome')
    if not isinstance(outcome, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', outcome):
        raise ValueError('Invalid draw outcome')
    result['outcome'] = outcome
    return result


def count_rows(counter, field):
    return [{field: key, 'records': value} for key, value in sorted(counter.items())]


def analyze(data, source_sha256, source_bytes):
    if not isinstance(data, dict) or data.get('format') != 'zgta-performance-v2':
        raise ValueError('Unsupported performance report format')
    diagnostic = data.get('renderingDiagnostics')
    if not isinstance(diagnostic, dict) or diagnostic.get('format') != 'zgta-rendering-consumer105-v1':
        raise ValueError('Unsupported rendering consumer schema')
    raw = diagnostic.get('observations')
    if not isinstance(raw, list) or len(raw) > 256:
        raise ValueError('Rendering observation limit exceeded or missing')
    rows = [observation(row) for row in raw]
    counts = diagnostic.get('counters')
    if not isinstance(counts, dict):
        raise ValueError('Missing rendering counters')
    counters = {name: integer(counts.get(name), name) for name in COUNTERS}
    grouped = defaultdict(list)
    shaders = defaultdict(list)
    for row in rows:
        grouped[tuple(row[k] for k in IDENTITY)].append(row)
        shaders[row['ps']].append(row)
    signatures = []
    for signature, members in sorted(grouped.items()):
        masks = Counter((r['stipple'], tuple(r['bound']), tuple(r['shadow'])) for r in members)
        signatures.append({'drawSignature': dict(zip(IDENTITY, signature)), 'records': len(members),
                           'frames': sorted(set(r['frame'] for r in members)),
                           'outcomes': dict(sorted(Counter(r['outcome'] for r in members).items())),
                           'masks': [{'stippleCode': code, 'boundWords': list(bound), 'shadowWords': list(shadow),
                                      'records': n} for (code, bound, shadow), n in sorted(masks.items())]})
    metrics = {}
    conditions = data.get('conditions', {})
    if not isinstance(conditions, dict):
        raise ValueError('Invalid conditions')
    for name in METRICS:
        value = conditions.get(name)
        if value is None:
            continue
        if not isinstance(value, dict):
            raise ValueError(f'Invalid metric {name}')
        metrics[name] = {k: numeric(value[k], name + '.' + k)
                         for k in ('first', 'last', 'minimum', 'maximum', 'delta', 'observations') if k in value}
        if 'counterReset' in value:
            if not isinstance(value['counterReset'], bool):
                raise ValueError(f'Invalid counter-reset flag {name}')
            metrics[name]['counterReset'] = value['counterReset']
    timeline = data.get('timeline', [])
    if not isinstance(timeline, list) or len(timeline) > 4096:
        raise ValueError('Timeline limit exceeded or invalid')
    transitions = []
    previous = {}
    for sample in timeline:
        if not isinstance(sample, dict) or not isinstance(sample.get('conditions', {}), dict):
            raise ValueError('Invalid timeline sample')
        elapsed = numeric(sample.get('elapsedMS'), 'elapsedMS')
        changes = {}
        for name in ('thermalState', 'requestedFrameInterval'):
            if name not in sample['conditions']:
                continue
            current = numeric(sample['conditions'][name], name)
            if name not in previous or previous[name] != current:
                changes[name] = current
            previous[name] = current
        if changes:
            transitions.append({'elapsedMS': elapsed, 'observedValues': changes})
    performance = {name: numeric(data[name], name)
                   for name in ('durationMS', 'averageFPS', 'medianWindowFPS', 'slowestWindowFPS', 'samples') if name in data}
    performance.update(conditions=metrics, timelineEntries=len(timeline), observedTransitions=transitions,
                       diagnosticNotCleanBenchmark=True)
    context = data.get('context', {})
    if not isinstance(context, dict):
        raise ValueError('Invalid context')
    # Deliberate allowlist: do not export raw context or user/network fields.
    safe_context = {}
    for name in ('platform', 'build', 'deviceModel', 'preset', 'memoryProfile', 'fpsCap', 'savedFPSCap', 'renderingCapture'):
        value = context.get(name)
        if value is not None:
            if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9 ,.()+_-]{1,96}', value):
                raise ValueError(f'Invalid allowlisted context field {name}')
            safe_context[name] = value
    valid = [r for r in rows if r['shadowValid'] and r['boundValid']]
    return {'format': 'zgta-rendering-capture-analysis-v1',
            'source': {'sha256': source_sha256, 'bytes': source_bytes, 'reportFormat': data['format'],
                       'consumerFormat': diagnostic['format']},
            'context': safe_context, 'performance': performance, 'counters': counters,
            'observations': {'records': len(rows), 'frames': count_rows(Counter(r['frame'] for r in rows), 'frame'),
                             'outcomes': dict(sorted(Counter(r['outcome'] for r in rows).items())),
                             'encodedRecords': sum(r['encoded'] for r in rows), 'validShadowAndBoundRecords': len(valid),
                             'matchingShadowAndBoundRecords': sum(r['shadow'] == r['bound'] for r in valid),
                             'mismatchingShadowAndBoundRecords': sum(r['shadow'] != r['bound'] for r in valid),
                             'shaderHashes': sorted(shaders), 'drawSignatureCount': len(signatures)},
            'shaders': [{'ps': ps, 'records': len(members),
                         'stippleCodes': count_rows(Counter(r['stipple'] for r in members), 'code')}
                        for ps, members in sorted(shaders.items())],
            'drawSignatures': signatures, 'cautions': CAUTIONS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.report.resolve() == args.output.resolve() or args.output.suffix.lower() != '.json':
        parser.error('Output must be a separate explicit .json file')
    try:
        if args.report.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError('Input exceeds 16 MiB bound')
        with args.report.open('rb') as source:
            raw = source.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError('Input exceeds 16 MiB bound')
        result = analyze(json.loads(raw), hashlib.sha256(raw).hexdigest(), len(raw))
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f'Capture analysis failed: {error}\n')
    print(f'Wrote {len(result["drawSignatures"])} draw-signature summaries to {args.output}')


if __name__ == '__main__':
    main()
