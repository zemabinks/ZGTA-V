"""Reject incomplete translation and failed recompiles even with old AIR cached."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('shader_build', Path(__file__).resolve().parents[1]/'Scripts/build_metal_shaders.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class ShaderBuildTests(unittest.TestCase):
    def test_reflection_requires_every_hash_and_matching_stage(self):
        entries = [('a', {'stage': 'vs', 'effect': 'water'}), ('b', {'stage': 'ps', 'effect': 'waterTex'})]
        records = [{'h': 'a', 'st': 'vs'}, {'h': 'b', 'st': 'ps'}]
        build.check_reflection(entries, records)
        for bad in [records[:1], records + records[:1], [records[0], {'h': 'b', 'st': 'vs'}], records + [{'h': 'old', 'st': 'ps'}]]:
            with self.assertRaises(ValueError):
                build.check_reflection(entries, bad)

    def test_failed_batch_cannot_fall_through_to_link_cached_air(self):
        with tempfile.TemporaryDirectory() as root:
            cached = Path(root)/'water.air'
            cached.write_bytes(b'old water shader')
            with patch.object(build, 'compile_batch', side_effect=RuntimeError('invalid new shader')):
                with self.assertRaisesRegex(RuntimeError, 'refusing cached AIR'):
                    build.compile_batches('iphoneos', 'metal', ['water.metal'], root)
                    self.fail('A failed recompile was allowed to reach the link step')
            self.assertEqual(cached.read_bytes(), b'old water shader')

    def test_all_batches_complete_before_success(self):
        sources = [str(i) for i in range(101)]
        with patch.object(build, 'compile_batch') as compile_one:
            build.compile_batches('iphoneos', 'metal', sources, 'air')
        self.assertEqual(compile_one.call_count, 3)
        self.assertEqual(sorted(s for c in compile_one.call_args_list for s in c.args[2]), sorted(sources))


if __name__ == '__main__': unittest.main()
