"""Contact/map-help text keeps the script's inserted values and controller glyphs."""
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

APP = Path(__file__).resolve().parents[2] / 'app'
CATALOG = APP / 'Source/TextLabels.json'


class ContactLabels(unittest.TestCase):
    def test_observed_prompts_keep_contact_and_input_slots(self):
        labels = dict(json.loads(CATALOG.read_text()))
        self.assertEqual(labels['DLCC_TRIG_H'], '~INPUT_CONTEXT~ Contact ~a~')
        self.assertEqual(labels['DLCC_HEIST_PH'], 'Visit ~a~~s~ for details about Heists.')
        self.assertIn('~INPUT_FRONTEND_LEFT~', labels['DLCC_TRIG_H2'])
        self.assertEqual(labels['DLCC_HEIST_CT'], 'Lester Crest')
        self.assertEqual(labels['DLCC_HEIST_PR'], 'High-End Apartment')

    def test_all_contact_formatting_contracts(self):
        # These are the ordered argument/glyph contracts in the pinned reference
        # a41fa82b10d1c49cee82b2a07671e8deeec8b4ce, not its prose. A changed
        # contact string must not consume a different script argument or glyph.
        expected = {key: ['~a~', '~s~'] for key in (
            'DLCC_AFTER_PH', 'DLCC_ARENA_PH', 'DLCC_BIKER_PH', 'DLCC_BTY24_PH',
            'DLCC_CONTR_PH', 'DLCC_FAIFA_PH', 'DLCC_GUNRU_PH', 'DLCC_HEIST_PH',
            'DLCC_LOSSA_PH', 'DLCC_LOWRI_PH', 'DLCC_PREMI_PH', 'DLCC_SAL23_PH',
            'DLCC_SMR23_PH', 'DLCC_SMUGG_PH', 'DLCC_ULPAP_PH')}
        expected.update({
            'DLCC_BLIP_H1': ['~BLIP_HEIST_DIAMOND~', '~HUD_COLOUR_YELLOW~', '~BLIP_ARMENIAN_FAMILY~', '~s~'],
            'DLCC_BLIP_H2': ['~HUD_COLOUR_PINKLIGHT~', '~BLIP_RACE_LAND~', '~s~', '~HUD_COLOUR_PINKLIGHT~', '~BLIP_ADVERSARY_BUNKER~', '~s~'],
            'DLCC_CASHT_PH': ['~BLIP_HEIST_DIAMOND~'],
            'DLCC_CASHT_PH2': ['~BLIP_HEIST_DIAMOND_UNAVAILABLE~'],
            'DLCC_DOOMS_PH': ['~BLIP_HEIST_DOOMSDAY~'],
            'DLCC_DOOMS_PH2': ['~BLIP_HEIST_DOOMSDAY_UNAVAILABLE~'],
            'DLCC_ISLAN_PH': ['~BLIP_HEIST_ISLAND~'],
            'DLCC_ISLAN_PH2': ['~BLIP_HEIST_ISLAND_UNAVAILABLE~'],
            'DLCC_KORTZ_PH': ['~BLIP_HEIST_ART~'],
            'DLCC_KORTZ_PH2': ['~BLIP_HEIST_ART_UNAVAILABLE~'],
            'DLCC_TRIG_H': ['~INPUT_CONTEXT~', '~a~'],
            'DLCC_TRIG_H2': ['~INPUT_CONTEXT~', '~a~', '~n~', '~INPUT_FRONTEND_LEFT~'],
        })
        actual = {key: re.findall(r'~[^~]+~', value)
                  for key, value in json.loads(CATALOG.read_text())
                  if key.startswith('DLCC_') and '~' in value}
        self.assertEqual(actual, expected)

    def test_expanded_catalog_remains_bounded_and_rejects_collision(self):
        spec = importlib.util.spec_from_file_location('generate_contact_test', APP / 'Scripts/generate_text_labels.py')
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        with tempfile.TemporaryDirectory(prefix='zgta-contact-catalog-') as temporary:
            path = Path(temporary) / 'TextLabels.json'
            with patch.object(generator, 'CATALOG', path):
                path.write_text(json.dumps([['TEST_LABEL_' + str(i), 'caption'] for i in range(2049)]))
                with self.assertRaisesRegex(ValueError, 'Bounded'):
                    generator.outputs(native_only=True)
                path.write_text(json.dumps([['DUPLICATE', 'first'], ['DUPLICATE', 'second']]))
                with self.assertRaisesRegex(ValueError, 'Duplicate label/hash'):
                    generator.outputs(native_only=True)
                path.write_text(json.dumps([['OVERSIZED', 'a' * 513]]))
                with self.assertRaisesRegex(ValueError, 'Invalid fallback'):
                    generator.outputs(native_only=True)


if __name__ == '__main__':
    unittest.main()
