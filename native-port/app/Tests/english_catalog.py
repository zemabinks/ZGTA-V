"""English-only UI and legacy multiplayer identity regression checks."""
import json
from pathlib import Path
import re
import unittest
ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / 'Resources/Localizations.json').read_text())
class EnglishCatalogTests(unittest.TestCase):
    def test_no_vietnamese_translation_shipped(self):
        self.assertEqual(set(CATALOG), {'Dân thường', 'Cảnh sát', 'Bác sĩ', 'Băng đảng', 'Tài xế'})
        for entry in CATALOG.values():
            self.assertEqual(set(entry), {'en'})
            self.assertTrue(entry['en'].strip())
    def test_app_owned_ui_source_is_english(self):
        for path in (ROOT / 'App').glob('*.swift'):
            # Existing wire role IDs must remain compatible, not be rendered directly.
            if path.name == 'OnlinePreferences.swift': continue
            with self.subTest(file=path.name):
                self.assertIsNone(re.search(r'[Ă-ưẠ-ỹ]', path.read_text()))
    def test_language_selector_removed(self):
        for name in ['HomeView', 'SettingsViewController', 'NativePortViewController', 'LocalizationUI']:
            text = (ROOT / 'App' / (name + '.swift')).read_text()
            self.assertNotIn('chooseLanguage', text)
            self.assertNotIn('languageButton', text)
    def test_no_old_brand_in_visible_app_strings(self):
        for path in (ROOT / 'App').glob('*.swift'):
            for match in re.finditer(r'"(?:[^"\\]|\\.)*"',path.read_text()):
                value=match[0]
                # Compatibility keys, ABI names and mod manifest schema are not UI labels.
                if re.fullmatch(r'"(?:Mugoat[A-Za-z]+|_mugoatOverrides)"',value): continue
                self.assertIsNone(re.search(r'\b(?:Mugoat|Muguet|iOSVN)\b',value),f'{path.name}: {value}')
if __name__ == '__main__': unittest.main()
