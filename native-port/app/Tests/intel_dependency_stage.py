"""Disposable integrity/preservation regressions; no real Intel inputs copied."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Scripts'))
import stage_intel_dependencies as stage


class DependencyStageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gta-dependency-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'original/Tools'
        self.source.mkdir(parents=True)
        self.app = self.root / 'candidate/app'
        self.app.mkdir(parents=True)
        self.rows = []
        for source, destination, data, executable in [
                ('wabt/runtime.c', 'wabt/share/runtime.c', b'existing runtime', False),
                ('tool', 'tool', b'fixture executable', True)]:
            p = self.source / source
            p.parent.mkdir(exist_ok=True)
            p.write_bytes(data)
            self.rows.append({'path': destination, 'source': source, 'bytes': len(data),
                              'sha256': hashlib.sha256(data).hexdigest(), 'executable': executable})

    def test_stage_materializes_independent_files_and_is_idempotent(self):
        self.assertEqual(stage.stage(self.source, self.app, self.rows), 'STAGED')
        self.assertEqual(stage.stage(self.source, self.app, self.rows), 'REUSED')
        for row in self.rows:
            original, copied = self.source / row['source'], self.app / 'Tools' / row['path']
            self.assertEqual(original.read_bytes(), copied.read_bytes())
            self.assertNotEqual(original.stat().st_ino, copied.stat().st_ino)
            self.assertEqual(copied.stat().st_nlink, 1)
        (self.app / 'Tools/wabt/share/runtime.c').write_bytes(b'candidate edit')
        self.assertEqual((self.source / 'wabt/runtime.c').read_bytes(), b'existing runtime')

    def test_original_app_and_nested_destination_are_refused(self):
        for target in [self.source.parent, self.source, self.source / 'nested']:
            with self.assertRaises(stage.CacheError):
                stage.stage(self.source, target, self.rows)
        self.assertFalse((self.source / 'Tools').exists())

    def test_traversal_absolute_duplicates_and_bad_bounds_are_refused(self):
        for value in ['../escape', '/absolute', 'a/../escape', 'a//b', '.git/config', 'a\\b']:
            rows = [dict(self.rows[0], path=value)]
            with self.assertRaises(stage.CacheError):
                stage.stage(self.source, self.app, rows)
        for rows in [self.rows + self.rows[:1], [dict(self.rows[0], bytes=-1)],
                     [dict(self.rows[0], sha256='wrong')]]:
            with self.assertRaises(stage.CacheError):
                stage.stage(self.source, self.app, rows)
        self.assertFalse((self.app / 'Tools').exists())

    def test_corrupt_source_stops_before_any_destination_write(self):
        (self.source / 'tool').write_bytes(b'bad')
        with self.assertRaises(stage.CacheError):
            stage.stage(self.source, self.app, self.rows)
        self.assertEqual(list(self.app.iterdir()), [])

    def test_symlink_inputs_and_destination_are_refused(self):
        (self.source / 'tool').unlink()
        (self.root / 'outside').write_bytes(b'fixture executable')
        (self.source / 'tool').symlink_to(self.root / 'outside')
        with self.assertRaises(stage.CacheError):
            stage.stage(self.source, self.app, self.rows)
        alias = self.root / 'alias'
        alias.symlink_to(self.app, target_is_directory=True)
        with self.assertRaises(stage.CacheError):
            stage.stage(self.source, alias, self.rows)

    def test_partial_or_unexpected_existing_tools_are_preserved(self):
        tools = self.app / 'Tools'
        tools.mkdir()
        (tools / 'prior').write_bytes(b'preserve')
        with self.assertRaises((stage.CacheError, OSError)):
            stage.stage(self.source, self.app, self.rows)
        self.assertEqual((tools / 'prior').read_bytes(), b'preserve')

    def test_failed_copy_cleans_only_owned_staging(self):
        with patch.object(stage.shutil, 'copyfile', side_effect=OSError('fixture failure')):
            with self.assertRaises(OSError):
                stage.stage(self.source, self.app, self.rows)
        self.assertEqual(list(self.app.iterdir()), [])
        self.assertEqual((self.source / 'tool').read_bytes(), b'fixture executable')

    def test_truncated_copy_is_never_published(self):
        def truncate(source, destination):
            Path(destination).write_bytes(b'bad')
        with patch.object(stage.shutil, 'copyfile', side_effect=truncate):
            with self.assertRaises(stage.CacheError):
                stage.stage(self.source, self.app, self.rows)
        self.assertFalse((self.app / 'Tools').exists())

    def test_hardlinked_staged_file_is_refused(self):
        import os
        stage.stage(self.source, self.app, self.rows)
        p = self.app / 'Tools/tool'
        p.unlink()
        os.link(self.source / 'tool', p)
        with self.assertRaises(stage.CacheError):
            stage.verify_files(self.app / 'Tools', self.rows, exact=True)

    def test_actual_manifest_is_bounded_and_hash_pinned(self):
        manifest = stage.load_manifest()
        self.assertEqual(len(manifest['files']), 546)
        self.assertEqual(sum(row['bytes'] for row in manifest['files']), 14444373)

    def test_generated_tool_outputs_do_not_replace_verified_baseline_inputs(self):
        stage.stage(self.source, self.app, self.rows)
        (self.app / 'Tools/wasm2c-native').write_bytes(b'newly built tool, not baseline')
        self.assertEqual(stage.stage(self.source, self.app, self.rows), 'REUSED')
        self.assertEqual((self.app / 'Tools/wasm2c-native').read_bytes(), b'newly built tool, not baseline')

    def test_corrupt_receipt_is_not_reported_as_verified(self):
        stage.stage(self.source, self.app, self.rows)
        (self.app / 'Tools' / stage.RECEIPT).write_text('{}')
        with self.assertRaises(stage.CacheError):
            stage.verify_staged(self.app / 'Tools', self.rows)


if __name__ == '__main__':
    unittest.main()
