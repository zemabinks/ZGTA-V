"""Sidecar coverage and publication failure tests (no game or Metal device)."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zlib
import hashlib

SCRIPT = Path(__file__).resolve().parents[1] / 'Scripts/prepare_stipple_shaders.py'
spec = importlib.util.spec_from_file_location('stipple_packer', SCRIPT)
packer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packer)


class StippleSources(unittest.TestCase):
    def test_independent_record_roundtrip_and_exact_fragment_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reflection = root / 'reflection.jsonl'
            reflection.write_text('\n'.join(json.dumps(v) for v in [
                {'h': 'vertex', 'st': 'vs'}, {'h': 'one', 'st': 'ps'}, {'h': 'two', 'st': 'ps'}]))
            sources = root / 'sources.jsonl'
            values = [{'h': name, 'source': 'constant uint x [[function_constant(0)]]; fragment void s_' + name + '_stipple() {}'} for name in ('one', 'two')]
            sources.write_text('\n'.join(json.dumps(v) for v in values))
            result = packer.pack(sources, reflection, root / 'out')
            self.assertEqual(result['fragment_programs'], 2)
            self.assertEqual(result['metal_compilation'], 'REQUIRES_RUNTIME_DEVICE_CHECK')
            manifest = json.loads((root / 'out/shader-stipple-index.json').read_text())
            blob = (root / 'out/shader-stipple-sources.bin').read_bytes()
            for item in values:
                offset, size, raw_size, _ = manifest['shaders'][item['h']]
                raw = zlib.decompress(blob[offset:offset + size])
                self.assertEqual(raw.decode(), item['source'])
                self.assertEqual(len(raw), raw_size)
            self.assertEqual(packer.verify(reflection, root / 'out')['fragment_programs'], 2)
            # Even if someone updates the blob hash, unindexed trailing data
            # fails closed instead of being accepted as a complete source pair.
            changed = blob + b'unindexed'
            (root / 'out/shader-stipple-sources.bin').write_bytes(changed)
            manifest['blob_sha256'] = hashlib.sha256(changed).hexdigest()
            (root / 'out/shader-stipple-index.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'trailing/unindexed'):
                packer.verify(reflection, root / 'out')

    def test_incomplete_or_duplicate_does_not_replace_existing_resources(self):
        for duplicate in (False, True):
            with self.subTest(duplicate=duplicate), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                reflection = root / 'reflection.jsonl'
                reflection.write_text('{"h":"one","st":"ps"}\n{"h":"two","st":"ps"}\n')
                item = {'h': 'one', 'source': '[[function_constant(0)]] s_one_stipple('}
                sources = root / 'sources.jsonl'
                sources.write_text(json.dumps(item) + ('\n' + json.dumps(item) if duplicate else ''))
                out = root / 'out'
                out.mkdir()
                (out / 'shader-stipple-sources.bin').write_bytes(b'previous verified pair')
                with self.assertRaises(ValueError):
                    packer.pack(sources, reflection, out)
                self.assertEqual((out / 'shader-stipple-sources.bin').read_bytes(), b'previous verified pair')
                self.assertFalse((out / 'shader-stipple-index.json').exists())


if __name__ == '__main__':
    unittest.main()
