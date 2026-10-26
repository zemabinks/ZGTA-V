"""DLC help/mail keeps GTA's glyph and layout arguments instead of showing keys."""
import json
from pathlib import Path
import re
import subprocess
import unittest

CATALOG = Path(__file__).resolve().parents[2] / 'app/Source/TextLabels.json'


class MailLabels(unittest.TestCase):
    def test_observed_mail_families_have_help_body_and_subject(self):
        labels = dict(json.loads(CATALOG.read_text()))
        for stem, suffixes in {
            'TFLOW_MAIL': ('', '_H', '_SUB'),
            'SKYDIVEMAIL': ('_HELP', '_TXT', '_TXT_SUB'),
            'SUM22SCMAIL': ('_HLP', '_TXT', '_TXT_SUB'),
        }.items():
            for suffix in suffixes:
                value = labels[stem + suffix]
                self.assertTrue(value.strip())
                self.assertNotIn('missing', value.lower())
                self.assertNotIn('(null)', value.lower())
        self.assertIn('Cypress Flats', labels['TFLOW_MAIL_H'])
        self.assertIn('Junk Energy', labels['SKYDIVEMAIL_HELP'])
        self.assertIn('2x:', labels['SUM22SCMAIL_TXT'])
        self.assertIn('3x:', labels['SUM22SCMAIL_TXT'])
        self.assertLessEqual(len(labels['SUM22SCMAIL_TXT'].encode()), 512)

    def test_mail_and_help_preserve_all_ordered_formatting_contracts(self):
        # Token-only contracts from pinned reference blob
        # a41fa82b10d1c49cee82b2a07671e8deeec8b4ce. Prose is authored separately.
        expected = {
            'SKYDIVEMAIL_HELP': ['~BLIP_JUNK_SKYDIVE~'],
            'SKYDIVEMAIL_TXT': ['~n~', '~n~'],
            'SUM22SCMAIL_TXT': ['~n~'] * 12,
            'TFLOW_CARLIST': ['~BLIP_AUTO_SHOP_PROPERTY~'],
            'TFLOW_CMEET_H': ['~BLIP_CAR_MEET_ORGANISER~'],
            'TFLOW_CUSCAR1': ['~BLIP_AUTO_SHOP_PROPERTY~'],
            'TFLOW_CUSCAR2': ['~BLIP_AUTO_SHOP_PROPERTY~'],
            'TFLOW_MAIL': ['~n~', '~n~', '~n~'],
            'TFLOW_MAIL_H': ['~BLIP_CAR_MEET~'],
            'TFLOW_PREP_H': ['~BLIP_CAR_ROBBERY_BOARD~'],
            'TFLOW_PROB_H': ['~BLIP_AUTO_SHOP_PROPERTY~'],
            'TFLOW_RFRSH_H1': ['~BLIP_AUTO_SHOP_PROPERTY~'],
            'TFLOW_RFRSH_H2': ['~BLIP_CAR_ROBBERY_BOARD~'],
            'TFLOW_SHOP_H1': ['~BLIP_AUTO_SHOP_PROPERTY~'],
        }
        actual = {
            key: re.findall(r'~[^~]+~', value)
            for key, value in json.loads(CATALOG.read_text())
            if key.startswith(('TFLOW_', 'SKYDIVEMAIL', 'SUM22SCMAIL')) and '~' in value
        }
        self.assertEqual(actual, expected)

    def test_observed_contact_hash_resolves_without_rewriting_existing_names(self):
        # Hash 0xa14fc366 was missing in the actual Build59 LS Car Meet mail.
        # The pinned reference maps it to CELL_LSCMNAME, not a guessed sender.
        helper=CATALOG.parents[2]/'engine-lan/text_fallback.js'
        script=r"""
const a=require('node:assert/strict'),api=require(process.argv[1]);
const memory=new WebAssembly.Memory({initial:1}),decoder=new TextDecoder();let next=256;
const fallback=api.callback(memory,hash=>hash===0x11111111?128n:0n,n=>{const p=next;next+=Number(n);return BigInt(p);});
const p=fallback(0xa14fc366);a.ok(p>0n);const bytes=new Uint8Array(memory.buffer,Number(p),32);a.equal(decoder.decode(bytes.subarray(0,bytes.indexOf(0))),'LS Car Meet');
a.equal(fallback(0xa14fc366),p,'Resolved name allocation is cached');
a.equal(fallback(0x11111111),128n,'Existing engine strings retain priority');
a.equal(fallback(0),0n,'Do not relabel a null/unknown sender');
"""
        result=subprocess.run(['node','-e',script,str(helper)],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_verified_gun_van_input_and_starter_pack_caption(self):
        labels = dict(json.loads(CATALOG.read_text()))
        self.assertEqual(re.findall(r'~[^~]+~', labels['GUN_VAN_HELP']), ['~BLIP_GUN_VAN~'])
        self.assertEqual(re.findall(r'~[^~]+~', labels['GS_BROWSE_GV']), ['~a~'])
        self.assertIn('Starter Pack', labels['CESP_AVAIL'])
        # An obscured screenshot does not authorize inventing alternate keys or
        # substituting a guessed contact sender for a null display name.
        self.assertNotIn('CEOD_AVAIL', labels)
        self.assertNotIn('GUNVANMAIL_HLP', labels)
        self.assertNotIn('(null)', labels)


if __name__ == '__main__':
    unittest.main()
