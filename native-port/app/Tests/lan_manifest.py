"""Read-only local-network purpose metadata; never requests permission."""
from pathlib import Path
import plistlib
import unittest

ROOT = Path(__file__).resolve().parents[1]
PURPOSE = 'Host or join ZGTA V multiplayer on your local network, and access your optional game-file server.'

class LANManifestTests(unittest.TestCase):
    def test_checked_in_plist_explains_mac_lan_access_in_english(self):
        info=plistlib.loads((ROOT / 'App/Info.plist').read_bytes())
        self.assertEqual(info['NSLocalNetworkUsageDescription'], PURPOSE)
        self.assertEqual(info['NSBonjourServices'], ['_zgtav._tcp'])

    def test_project_generator_preserves_the_same_purpose(self):
        project=(ROOT / 'project.yml').read_text()
        self.assertIn('NSLocalNetworkUsageDescription: "' + PURPOSE + '"', project)
        self.assertIn('NSBonjourServices:\n          - _zgtav._tcp', project)

if __name__ == '__main__':
    unittest.main()
