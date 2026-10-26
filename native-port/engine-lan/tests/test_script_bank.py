"""Pinned failed-bank adaptation; synthetic typed calls, no game instance."""
import json
from pathlib import Path
from public_test_inputs import game_file
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import script_bank as fix
ORIGINAL=game_file('b/8b0b5899ed/game.wasm')


class ScriptBank(unittest.TestCase):
    def test_exact_original_names_abis_and_bodies(self):self.assertEqual(fix.inspect(ORIGINAL.read_bytes()),fix.HOOKS)

    def test_unreviewed_engine_refused(self):
        with self.assertRaisesRegex(ValueError,'Unreviewed engine'):fix.inspect(b'not reviewed')

    def test_failed_bank_scope_nested_exceptions_and_typed_abi(self):
        with tempfile.TemporaryDirectory(prefix='zema-script-bank-') as directory:
            p=Path(directory)/'aux.json';p.write_text(json.dumps(list(fix.b.auxiliary(fix.HOOKS))))
            result=subprocess.run(['node',str(ROOT/'tests/script_bank_fixture.cjs'),str(ROOT),str(p)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('SCRIPT_BANK_SCOPED_FAILURE_TYPED_PASS',result.stdout)
            self.assertIn('"gameplayVerified":false',result.stdout)


if __name__=='__main__':unittest.main()
