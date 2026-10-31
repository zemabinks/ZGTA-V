#!/usr/bin/env python3
"""Pack validated all-fragment MSL variants without replacing baseline shaders.

Run the pinned ShaderTool/stipple-msl translator first. The sidecar stores each
source as an independently compressed record so native startup reads only the
small index and first-use compilation decompresses only the needed program.
Actual Metal compilation is a separate runtime/device check, never implied by
Naga validation or by this packer's success.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import os
import zlib


def verify(reflection, directory):
    """Validate the exact sidecar pair before staging/building/packaging it."""
    reflection, directory = Path(reflection), Path(directory)
    records = [json.loads(line) for line in reflection.read_text().splitlines() if line.strip()]
    expected = {r['h'] for r in records if r['st'] == 'ps'}
    manifest = json.loads((directory / 'shader-stipple-index.json').read_text())
    blob = (directory / 'shader-stipple-sources.bin').read_bytes()
    if manifest.get('version') != 1 or manifest.get('translator') != 'naga-30.0.1':
        raise ValueError('Unsupported stipple sidecar format/translator')
    reflection_sha = hashlib.sha256(reflection.read_bytes()).hexdigest()
    if manifest.get('reflection_sha256') != reflection_sha:
        raise ValueError('Stipple reflection SHA-256 mismatch')
    blob_sha = hashlib.sha256(blob).hexdigest()
    if manifest.get('blob_sha256') != blob_sha:
        raise ValueError('Stipple compressed source SHA-256 mismatch')
    entries = manifest.get('shaders')
    if not isinstance(entries, dict) or set(entries) != expected:
        raise ValueError('Stipple shader coverage does not match reflection')
    ranges = []
    total_raw = 0
    for name, record in entries.items():
        if not isinstance(record, list) or len(record) != 4:
            raise ValueError('Invalid stipple source record: ' + name)
        offset, size, raw_size, digest = record
        if any(type(v) is not int for v in (offset, size, raw_size)) or offset < 0 or size <= 0 or raw_size <= 0 or raw_size > 1024 * 1024 or offset + size > len(blob):
            raise ValueError('Invalid stipple source range: ' + name)
        decoder = zlib.decompressobj()
        raw = decoder.decompress(blob[offset:offset + size], raw_size + 1)
        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or len(raw) != raw_size or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Stipple source decompression/hash failed: ' + name)
        text = raw.decode('utf-8')
        if text.count('[[function_constant(0)]]') != 1 or text.count('s_' + name + '_stipple(') != 1:
            raise ValueError('Stipple function constant/entry point mismatch: ' + name)
        ranges.append((offset, offset + size))
        total_raw += raw_size
    cursor = 0
    for start, end in sorted(ranges):
        if start != cursor:
            raise ValueError('Stipple source records overlap or leave gaps')
        cursor = end
    if cursor != len(blob):
        raise ValueError('Stipple source blob has trailing/unindexed bytes')
    return {'fragment_programs': len(expected), 'raw_source_bytes': total_raw,
            'packed_source_bytes': len(blob), 'blob_sha256': blob_sha,
            'reflection_sha256': reflection_sha,
            'metal_compilation': 'REQUIRES_RUNTIME_DEVICE_CHECK'}


def pack(source, reflection, destination):
    records = [json.loads(line) for line in reflection.read_text().splitlines() if line.strip()]
    expected = {r['h'] for r in records if r['st'] == 'ps'}
    entries = {}
    blob = bytearray()
    for line in source.read_text().splitlines():
        record = json.loads(line)
        name = record['h']
        if name not in expected or name in entries:
            raise ValueError('Unexpected or duplicate fragment source: ' + name)
        raw = record['source'].encode()
        if not raw or len(raw) > 1024 * 1024:
            raise ValueError('Fragment source size outside native bound: ' + name)
        if '[[function_constant(0)]]' not in record['source'] or ('s_' + name + '_stipple(') not in record['source']:
            raise ValueError('Missing specialization or entry point: ' + name)
        compressed = zlib.compress(raw, 9)
        entries[name] = [len(blob), len(compressed), len(raw), hashlib.sha256(raw).hexdigest()]
        blob.extend(compressed)
    if set(entries) != expected:
        raise ValueError('Fragment coverage does not match baseline reflection')
    manifest = {'version': 1, 'translator': 'naga-30.0.1',
                'metal_compilation': 'REQUIRES_RUNTIME_DEVICE_CHECK',
                'reflection_sha256': hashlib.sha256(reflection.read_bytes()).hexdigest(),
                'blob_sha256': hashlib.sha256(blob).hexdigest(), 'shaders': entries}
    # Validate every compressed record, including its independent hash, before
    # producing either resource. The build stage must copy these as a pair.
    for offset, size, raw_size, digest in entries.values():
        raw = zlib.decompress(blob[offset:offset + size])
        if len(raw) != raw_size or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Compressed source validation failed')
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.stipple-', dir=destination.parent) as tmp:
        stage = Path(tmp)
        (stage / 'shader-stipple-sources.bin').write_bytes(blob)
        (stage / 'shader-stipple-index.json').write_text(json.dumps(manifest, separators=(',', ':'), sort_keys=True) + '\n')
        verify(reflection, stage)
        for name in ('shader-stipple-sources.bin', 'shader-stipple-index.json'):
            os.replace(stage / name, destination / name)
    return {'fragment_programs': len(entries), 'raw_source_bytes': sum(v[2] for v in entries.values()),
            'packed_source_bytes': len(blob), 'blob_sha256': manifest['blob_sha256'],
            'reflection_sha256': manifest['reflection_sha256'],
            'metal_compilation': manifest['metal_compilation']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path)
    parser.add_argument('--reflection', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    if not args.verify_only and args.sources is None:
        parser.error('--sources is required unless --verify-only is selected')
    print(json.dumps(verify(args.reflection, args.output) if args.verify_only else pack(args.sources, args.reflection, args.output), indent=2))


if __name__ == '__main__':
    main()
