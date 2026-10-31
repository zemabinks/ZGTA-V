"""The corrected producer must still authenticate/reverse exact Build103 stages."""
import importlib.util
from pathlib import Path
import hashlib
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import render_hooks as h

class FadeStage104(unittest.TestCase):
    def old(self):
        path=ROOT.parents[2]/'zgta-fade103-20261028/native-port/engine-lan/render_hooks.py'
        self.assertTrue(path.is_file(),'Retained Build103 source required')
        spec=importlib.util.spec_from_file_location('retained_fade103',path)
        value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

    def test_frozen_build103_recipe_and_adapters_are_byte_identical(self):
        old=self.old()
        self.assertEqual((h.BUILD103_HEADER,h.BUILD103_STATE,h.BUILD103_BODIES),
                         (old.NATIVE_HEADER,old.NATIVE_STATE,old.NATIVE_BODIES))
        originals={index:200+j for j,index in enumerate(h.HOOKS)}
        self.assertEqual(h.wrappers(originals,(40,41,42,43),300,legacy103=True),
                         old.wrappers(originals,(40,41,42,43),300))

    def test_exact_build103_migration_rejects_tampering_before_writes(self):
        old=self.old();source=ROOT.parents[2]/'gta-intel-multiplayer-build-20261016/native-port/app/Generated'
        originals={};parts={}
        for name in h.native_files():
            raw=(source/name).read_bytes();originals[name]=raw
            rows=[r for r in h.PINS['native'] if r['file']==name and r['index'] in h.HOOKS]
            parts[name]=old.transform_native(raw.decode(),rows).encode() if rows else raw
            self.assertEqual(h.undo_native_part(parts[name],name),raw)
        with tempfile.TemporaryDirectory(prefix='zgta-state104-stage-') as folder:
            stage=Path(folder)
            for name,raw in parts.items():(stage/name).write_bytes(raw)
            (stage/'game-render-hooks98.h').write_text(h.BUILD103_HEADER)
            last=sorted(parts)[-1];(stage/last).write_bytes(parts[last]+b'\n/* pg103_unknown */\n')
            digest=lambda:{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()}
            before=digest()
            with self.assertRaises(ValueError):h.stage_native(stage)
            self.assertEqual(before,digest())
            (stage/last).write_bytes(parts[last]);h.stage_native(stage);h.verify_native(stage)
            self.assertEqual((stage/'game-render-hooks98.h').read_text(),h.NATIVE_HEADER)
            for name,raw in originals.items():self.assertEqual(h.undo_native_part((stage/name).read_bytes(),name),raw)
            before=digest();h.stage_native(stage);self.assertEqual(before,digest())

if __name__=='__main__':unittest.main()
