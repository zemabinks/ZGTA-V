"""Authenticate original fade data and exact legacy-to-current native migration."""
import ast
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import render_hooks as h
import browser_wasm as b
from test_render_hooks import ORIGINAL_TABLE


class FadeMasks103(unittest.TestCase):
    def test_original_table_matches_authenticated_wasm(self):
        wasm = Path.home() / 'Library/Application Support/ZRemote Controller/Games/playgta5-offline/mirror/playgta5.com/b/8b0b5899ed/game.wasm'
        if not wasm.exists():
            self.skipTest('Owner-supplied pinned original WASM unavailable')
        data = wasm.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), '11ca8d2c04c5e843d18ff4aea4899d72c86973c6b031df334e67c446b2ae83e0')
        r = b.gate.Reader(dict(b.gate.sections(data))[11])
        self.assertEqual(r.count(), 4077)
        for index in range(2638):
            self.assertEqual(r.uint(), 1)  # Passive original data; no target execution.
            segment = r.take(r.uint())
        self.assertEqual(segment[1454:1518], ORIGINAL_TABLE)

    def test_original_predicate_and_complement_all_alphas(self):
        table = struct.unpack('<32H', ORIGINAL_TABLE)
        for alpha in range(256):
            masks = []
            for invert in (0, 1):
                raw = table[alpha >> 3] ^ (65535 if invert else 0)
                # Match actual shader's float4 dot(identity[phase]) >= 1,
                # independently of implementation's integer phase compaction.
                fade = [((raw >> (phase * 4)) & 15) / 15.0 for phase in range(4)]
                pixels = [fade[(x & 1) + 2 * (y & 1)] >= 1.0 for y in range(8) for x in range(8)]
                masks.append(pixels)
            self.assertTrue(all(a != c for a, c in zip(*masks)))
        self.assertEqual([table[a >> 3] for a in (15,16,87,88,159,160,207,208)],
                         [0,15,15,0xf00f,0xf00f,0xf0ff,0xf0ff,65535])

    def test_legacy_wrappers_match_retained_build102_source(self):
        old = ROOT.parents[2] / 'zgta-system-audit102-20261028/native-port/engine-lan/render_hooks.py'
        if not old.exists():
            self.skipTest('Retained Build102 source unavailable')
        values = {}
        for node in ast.parse(old.read_text()).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in ('NATIVE_HEADER','NATIVE_STATE','NATIVE_BODIES'):
                        values[target.id] = ast.literal_eval(node.value)
        self.assertEqual(h.LEGACY_HEADER, values['NATIVE_HEADER'])
        self.assertEqual(h.LEGACY_STATE, values['NATIVE_STATE'])
        self.assertEqual(h.LEGACY_BODIES, values['NATIVE_BODIES'])

    def test_legacy_wasm_recipe_matches_retained_build102_source(self):
        old = ROOT.parents[2] / 'zgta-system-audit102-20261028/native-port/engine-lan/render_hooks.py'
        if not old.exists():
            self.skipTest('Retained Build102 source unavailable')
        spec = importlib.util.spec_from_file_location('reviewed_render_hooks102', old)
        previous = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(previous)
        originals = {index: 200 + j for j, index in enumerate(h.HOOKS)}
        self.assertEqual(h.wrappers(originals, (40,41,42), 300, legacy98=True),
                         previous.wrappers(originals, (40,41,42), 300))

    def test_exact_legacy_stage_migration_and_preflight_rejection(self):
        original_dir = ROOT.parents[2] / 'gta-intel-multiplayer-build-20261016/native-port/app/Generated'
        if not original_dir.exists():
            self.skipTest('Retained original generated inputs unavailable')
        originals = {}
        legacy = {}
        for filename in h.native_files():
            originals[filename] = (original_dir / filename).read_bytes()
            rows = [r for r in h.PINS['native'] if r['file'] == filename and r['index'] in h.HOOKS]
            legacy[filename] = h._transform_native(originals[filename].decode(), rows, h.LEGACY_STATE, h.LEGACY_BODIES).encode() if rows else originals[filename]
            self.assertEqual(h.undo_native_part(legacy[filename], filename), originals[filename])
        with tempfile.TemporaryDirectory(prefix='zgta-fade103-migration-') as td:
            stage = Path(td)
            for filename, data in legacy.items():
                (stage / filename).write_bytes(data)
            header = stage / 'game-render-hooks98.h'
            header.write_text(h.LEGACY_HEADER)
            # Corrupt the last part: earlier staged outputs must remain unwritten.
            last = sorted(legacy)[-1]
            (stage / last).write_bytes(legacy[last].replace(b'pg98_original_9291(', b'unknown_original_9291(', 1))
            before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()}
            with self.assertRaises(ValueError):
                h.stage_native(stage)
            self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()})
            (stage / last).write_bytes(legacy[last])
            # A new header must never bless old wrapper bodies as current.
            header.write_text(h.NATIVE_HEADER)
            with self.assertRaises(ValueError):
                h.verify_native(stage)
            header.write_text(h.LEGACY_HEADER)
            h.stage_native(stage)
            h.verify_native(stage)
            self.assertEqual(header.read_text(), h.NATIVE_HEADER)
            for filename, original in originals.items():
                self.assertEqual(h.undo_native_part((stage / filename).read_bytes(), filename), original)
            before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()}
            h.stage_native(stage)
            self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()})


if __name__ == '__main__':
    unittest.main()
