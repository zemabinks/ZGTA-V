"""A changed source/header must never reuse a prior native object."""
from pathlib import Path
import hashlib
import shlex
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reuse_generated import dependencies, matching_dependencies, unit_flags, retained_unit, scoped_input_key, same_generated_compiler_settings


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ObjectDependencyReuse(unittest.TestCase):
    def test_only_reviewed_swift_gate_may_change_without_global_c_settings(self):
        import copy
        old = {'settings': {'base': {'GCC_OPTIMIZATION_LEVEL': '2'}},
               'targets': {'PlayGTA5Native': {'settings': {'base': {'PRODUCT_BUNDLE_IDENTIFIER': 'same'}}}}}
        new = copy.deepcopy(old)
        self.assertTrue(same_generated_compiler_settings(old, new))
        base = new['targets']['PlayGTA5Native']['settings']['base']
        base['SWIFT_ACTIVE_COMPILATION_CONDITIONS'] = ['$(inherited)', 'ZGTA_NATIVE_RECOVERY_QA']
        self.assertTrue(same_generated_compiler_settings(old, new))
        base['OTHER_CFLAGS'] = '-DUNREVIEWED'
        self.assertFalse(same_generated_compiler_settings(old, new))
        base.pop('OTHER_CFLAGS')
        base['SWIFT_ACTIVE_COMPILATION_CONDITIONS'].append('ANOTHER_FLAG')
        self.assertFalse(same_generated_compiler_settings(old, new))
        base.pop('SWIFT_ACTIVE_COMPILATION_CONDITIONS')
        new['settings']['base']['GCC_OPTIMIZATION_LEVEL'] = '0'
        self.assertFalse(same_generated_compiler_settings(old, new))

    def test_header_alias_is_scoped_and_links_or_escapes_are_refused(self):
        with tempfile.TemporaryDirectory(prefix='zgta-reuse-alias-') as temp:
            root=Path(temp);app=root/'AppRoot';(app/'Generated').mkdir(parents=True);(app/'Source').mkdir()
            (app/'Source/guard.h').write_text('guard')
            self.assertEqual(scoped_input_key(app,'Generated/../Source/guard.h'),'Source/guard.h')
            for path in ['../AppRoot/Source/guard.h',str((app/'Source/guard.h').resolve())]:
                with self.assertRaisesRegex(ValueError,'escapes'):scoped_input_key(app,path)
            (app/'Generated/link').symlink_to(app/'Source',target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'symbolic link'):scoped_input_key(app,'Generated/link/guard.h')

    def test_retained_object_alias_still_requires_matching_manifest_and_bytes(self):
        with tempfile.TemporaryDirectory(prefix='zgta-reuse-retained-') as temp:
            builds=Path(temp).resolve();previous=builds/'Previous';origin=builds/'Older/AppRoot'
            (origin/'Generated').mkdir(parents=True);(origin/'Source').mkdir();(previous/'AppRoot').mkdir(parents=True)
            source=origin/'Generated/game_1.c';source.write_text('source')
            header=origin/'Generated/../Source/guard.h';header.write_text('guard')
            folder=builds/'Older/DerivedData/Build/Intermediates.noindex/PlayGTA5Native.build/Release-iphoneos/PlayGTA5Native.build/Objects-normal/arm64';folder.mkdir(parents=True)
            obj=folder/'game_1.o';obj.write_bytes(b'preserved object');dep=obj.with_suffix('.d')
            dep.write_text('dependencies: '+shlex.join([str(source),str(header)])+'\n')
            entry={'source':'game_1.c','object':str(obj),'object_sha256':digest(obj),'dependencies_sha256':digest(dep),'app_inputs':{'Generated/game_1.c':digest(source),'Generated/../Source/guard.h':digest(header)}}
            record={'generated_object_reuse':{'reused_units':[entry]},'input_hashes':{'Generated/game_1.c':digest(source),'Source/guard.h':digest(header)}}
            self.assertEqual(retained_unit(previous,record,'game_1',builds,digest),(obj,dep,origin))
            record['input_hashes']['Source/guard.h']='0'*64
            with self.assertRaisesRegex(ValueError,'not attested'):retained_unit(previous,record,'game_1',builds,digest)
            record['input_hashes']['Source/guard.h']=digest(header);obj.write_bytes(b'changed object')
            with self.assertRaisesRegex(ValueError,'integrity'):retained_unit(previous,record,'game_1',builds,digest)

    def test_per_file_optimization_change_requires_a_fresh_object(self):
        def spec(sources):
            return {'targets': {'PlayGTA5Native': {'sources': sources}}}
        old = spec([{'path': 'Generated', 'compilerFlags': '-w', 'excludes': ['game_0.c']},
                    {'path': 'Generated/game_0.c', 'compilerFlags': '-w -O0'}])
        new = spec([{'path': 'Generated', 'compilerFlags': '-w', 'excludes': ['*.h']}])
        self.assertNotEqual(unit_flags(old, 'game_0'), unit_flags(new, 'game_0'))
        self.assertEqual(unit_flags(old, 'game_1'), unit_flags(new, 'game_1'))
        with self.assertRaises(ValueError):
            unit_flags(spec([{'path': 'Generated', 'excludes': ['game_*.c']}]), 'game_1')
    def test_source_and_every_recorded_app_header_must_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); old = root / 'old'; new = root / 'new'
            for app in (old, new):
                app.mkdir(); (app / 'game.c').write_text('source'); (app / 'header.h').write_text('ABI')
            paths = [old / 'game.c', old / 'header.h']
            self.assertTrue(matching_dependencies(paths, old, new, digest))
            (new / 'game.c').write_text('new source')
            self.assertFalse(matching_dependencies(paths, old, new, digest))
            (new / 'game.c').write_text('source'); (new / 'header.h').write_text('new ABI')
            self.assertFalse(matching_dependencies(paths, old, new, digest))
            (new / 'header.h').unlink()
            self.assertFalse(matching_dependencies(paths, old, new, digest))

    def test_xcode_dependency_escaping_and_external_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); dep = root / 'unit.d'
            dep.write_text('dependencies: \\\n  /tmp/old/game.c \\\n  /tmp/old/a\\ header.h\n')
            self.assertEqual(dependencies(dep), [Path('/tmp/old/game.c'), Path('/tmp/old/a header.h')])
            with self.assertRaises(ValueError):
                matching_dependencies([root / 'unrelated.h'], root / 'old', root / 'new', digest)
            dep.write_text('other: /tmp/old/game.c')
            with self.assertRaises(ValueError):
                dependencies(dep)


if __name__ == '__main__':
    unittest.main()
