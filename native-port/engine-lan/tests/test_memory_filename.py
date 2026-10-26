"""Exact original module inspection and typed synthetic callback behavior."""
import json
from pathlib import Path
from public_test_inputs import game_file
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import memory_filename as fix

ORIGINAL=game_file('b/8b0b5899ed/game.wasm')


class MemoryFilename(unittest.TestCase):
    def test_exact_original_engine_name_abi_and_body(self):
        self.assertEqual(fix.inspect(ORIGINAL.read_bytes()),fix.HOOK)

    def test_unreviewed_engine_refused(self):
        with self.assertRaisesRegex(ValueError,'Unreviewed engine'):
            fix.inspect(b'not the reviewed game')

    def test_typed_callback_format_narrowing_and_bounds(self):
        with tempfile.TemporaryDirectory(prefix='zema-memory-filename-') as directory:
            auxiliary=Path(directory)/'aux.json'
            auxiliary.write_text(json.dumps(list(fix.b.auxiliary([fix.HOOK]))))
            result=subprocess.run(['node',str(ROOT/'tests/memory_filename_fixture.cjs'),str(ROOT),str(auxiliary)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('MEMORY_FILENAME_TYPED_ADDRESS_AND_BOUNDS_PASS',result.stdout)
            self.assertIn('"graphicsVerified":false',result.stdout)


if __name__=='__main__':unittest.main()
