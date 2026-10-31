"""Actual ordered source producers, never historical cached intermediate inputs."""
import json
import os
from pathlib import Path
import sys
import unittest
from public_test_inputs import game_file

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import browser_features
import online_wasm
import reproduce_browser102

class ProducerPhase102(unittest.TestCase):
    def test_base_phase_excludes_only_later_exports(self):
        from browser_world_exports import EXPORTS
        import session_restart
        self.assertEqual(set(EXPORTS)-set(browser_features.EXPORTS),
                         {'IsModelInCdImage','IsModelAVehicle'})
        self.assertFalse({row[0] for row in session_restart.COMMANDS} & browser_features.EXPORTS.keys())

    def test_reject_changed_contract_phase_before_transform(self):
        for hooks in ([],[{'field':'socket_close','index':184}]*61):
            with self.assertRaisesRegex(ValueError,'hook phase changed'):
                online_wasm.feature_base(b'',{'hooks':hooks})

    def test_authenticated_original_rebuilds_both_exact_retained_runtimes(self):
        retained = Path(os.environ.get('ZGTA_RETAINED_BROWSER102',str(
            ROOT.parent/'app/Build/Browser-System-Audit-20261028-v102')))
        proof = reproduce_browser102.reproduce(game_file('b/8b0b5899ed/game.wasm').read_bytes(),
            json.loads(online_wasm.g.CONTRACT.read_text()),retained)
        self.assertEqual(len(proof['results']),2)
        self.assertTrue(all(row['byteIdentical'] for row in proof['results']))

if __name__ == '__main__': unittest.main()
