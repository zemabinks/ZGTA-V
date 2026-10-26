"""Original text-function pin and bounded synthetic typed fallback tests."""
import json
from pathlib import Path
from public_test_inputs import game_file
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import text_fallback as fix
ORIGINAL=game_file('b/8b0b5899ed/game.wasm')


class TextFallback(unittest.TestCase):
    def test_exact_original_name_abi_and_body(self):self.assertEqual(fix.inspect(ORIGINAL.read_bytes()),fix.HOOK)

    def test_unreviewed_engine_refused(self):
        with self.assertRaisesRegex(ValueError,'Unreviewed engine'):fix.inspect(b'not reviewed')

    def test_original_first_typed_fallback_and_bounded_cache(self):
        with tempfile.TemporaryDirectory(prefix='zema-text-fallback-') as directory:
            p=Path(directory)/'aux.json';p.write_text(json.dumps(list(fix.b.auxiliary([fix.HOOK]))))
            result=subprocess.run(['node',str(ROOT/'tests/text_fallback_fixture.cjs'),str(ROOT),str(p)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('TEXT_FALLBACK_ORIGINAL_FIRST_TYPED_CACHE_PASS',result.stdout)
            self.assertIn('"visualVerified":false',result.stdout)


if __name__=='__main__':unittest.main()
