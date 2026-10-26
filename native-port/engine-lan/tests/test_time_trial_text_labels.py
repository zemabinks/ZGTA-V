"""Time-trial map panels, input prompts and results preserve GTA script slots."""
import json
from pathlib import Path
import re
import unittest

CATALOG = Path(__file__).resolve().parents[2] / 'app/Source/TextLabels.json'


class TimeTrialLabels(unittest.TestCase):
    def test_photographed_map_panel_has_real_title_description_and_par_time(self):
        labels = dict(json.loads(CATALOG.read_text()))
        self.assertEqual(labels['AMTT_BLIP'], 'Time Trial')
        self.assertIn('Great Ocean Highway', labels['AMTT_DESC2'])
        self.assertEqual(labels['PM_PTIME'], 'Par Time')
        self.assertEqual(labels['RC_AMTT_BLIP'], labels['AMRCTT_BLIP'])
        # The pinned family and photographed panel identify one underscore.
        self.assertNotIn('AMTT__BLIP', labels)

    def test_every_route_has_a_readable_title_and_description(self):
        labels = dict(json.loads(CATALOG.read_text()))
        for index in range(32):
            title = labels['AMTT_ROUTE' + str(index)]
            description = labels['AMTT_DESC' + str(index)]
            self.assertTrue(title.strip())
            self.assertTrue(description.strip())
            self.assertNotIn('missing', title.lower())
            self.assertNotIn('missing', description.lower())
            self.assertNotIn('(null)', title.lower())
            self.assertNotIn('(null)', description.lower())
            self.assertLessEqual(len(description.encode()), 512)

    def test_all_time_trial_formatting_contracts(self):
        # Only argument/glyph contracts, not prose, from reference blob
        # a41fa82b10d1c49cee82b2a07671e8deeec8b4ce. Engine scripts insert
        # player names, finishing times and countdowns at these exact slots.
        expected = {
            'AMTT_BEATNO': ['~a~', '~a~'],
            'AMTT_BEATPAR': ['~a~', '~a~'],
            'AMTT_BEATYOU': ['~a~', '~a~'],
            'AMTT_GOTO': ['~y~', '~s~'],
            'AMTT_OUT': ['~1~'],
            'AMTT_PRESS': ['~INPUT_CONTEXT~'],
            'AMTT_QUICKRE': ['~INPUT_VEH_EXIT~'],
            'AMTT_RETURN': ['~b~', '~s~'],
            'AMTT_STARTPAR': ['~a~'],
            'AMTT_TIME': ['~a~'],
        }
        actual = {
            key: re.findall(r'~[^~]+~', value)
            for key, value in json.loads(CATALOG.read_text())
            if key.startswith('AMTT') and '~' in value
        }
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
