"""Retry only an exactly reproducible native object archive, preserving evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reuse_generated import materialize_cache


class BuildCacheRetry(unittest.TestCase):
    def test_real_archive_retry_is_identical_and_changed_inputs_are_refused(self):
        with tempfile.TemporaryDirectory(prefix='zgta-cache-retry-') as tmp:
            root=Path(tmp).resolve();obj=root/'unit.o';source=root/'unit.c'
            source.write_text('int zgta_cache_retry_fixture(void) { return 1; }\n')
            subprocess.run(['/usr/bin/clang','-target','arm64-apple-ios15.0','-c',str(source),'-o',str(obj)],check=True,capture_output=True)
            digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            cache=root/'cache';record={'format':'fixture','object_sha256':digest(obj)}
            first=materialize_cache(cache,[str(obj)],record,digest)
            before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in cache.iterdir()}
            self.assertEqual(first,materialize_cache(cache,[str(obj)],record,digest))
            self.assertEqual(before,{p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in cache.iterdir()})
            # A new stage may clone an exactly attested ordered archive without
            # generating a second large archive. Inputs are still checked above.
            members=[{'source':'unit.c','object_sha256':digest(obj)}]
            proven=dict(record,reused_units=members,recompile_units=[])
            attested=materialize_cache(root/'attested',[str(obj)],proven,digest)
            copy=materialize_cache(root/'cloned',[str(obj)],proven,digest,attested)
            self.assertEqual(copy['library_sha256'],attested['library_sha256'])
            self.assertEqual(copy,materialize_cache(root/'cloned',[str(obj)],proven,digest,attested))
            self.assertEqual((root/'cloned/libunchanged_engine.a').read_bytes(),(root/'attested/libunchanged_engine.a').read_bytes())
            with self.assertRaisesRegex(ValueError,'proof differs'):
                materialize_cache(root/'wrong-members',[str(obj)],dict(proven,reused_units=[]),digest,attested)
            # Historical archives use current dates. Keep their exact bytes and
            # receipt while comparing every object, symbol table and other field.
            library=cache/'libunchanged_engine.a';payload=bytearray(library.read_bytes());payload[24:36]=b'1234567890  ';library.write_bytes(payload)
            legacy=dict(first,library_sha256=digest(library));(cache/'verification.json').write_text(json.dumps(legacy))
            before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in cache.iterdir()}
            self.assertEqual(legacy,materialize_cache(cache,[str(obj)],record,digest))
            self.assertEqual(before,{p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in cache.iterdir()})
            source.write_text('int zgta_cache_retry_fixture(void) { return 2; }\n')
            subprocess.run(['/usr/bin/clang','-target','arm64-apple-ios15.0','-c',str(source),'-o',str(obj)],check=True,capture_output=True)
            with self.assertRaisesRegex(ValueError,'preserve'):
                materialize_cache(cache,[str(obj)],dict(record,object_sha256=digest(obj)),digest)
            self.assertEqual(before,{p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in cache.iterdir()})
            self.assertEqual(json.loads((cache/'verification.json').read_text()),legacy)
            # A symlink must not be accepted even when its bytes match.
            alias=root/'alias';alias.symlink_to(cache,target_is_directory=True)
            with self.assertRaises(ValueError):
                materialize_cache(alias,[str(obj)],record,digest)


if __name__=='__main__':unittest.main()
