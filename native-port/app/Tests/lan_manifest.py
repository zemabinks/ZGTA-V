"""Read-only local-network purpose metadata; never requests permission."""
from pathlib import Path
import plistlib
import unittest

ROOT = Path(__file__).resolve().parents[1]
PURPOSE = 'Connect to your Mac multiplayer server and optional game-file server on the same local network.'

class LANManifestTests(unittest.TestCase):
    def test_checked_in_plist_explains_mac_lan_access_in_english(self):
        self.assertEqual(plistlib.loads((ROOT / 'App/Info.plist').read_bytes())['NSLocalNetworkUsageDescription'], PURPOSE)

    def test_project_generator_preserves_the_same_purpose(self):
        self.assertIn('NSLocalNetworkUsageDescription: "' + PURPOSE + '"', (ROOT / 'project.yml').read_text())

if __name__ == '__main__':
    unittest.main()
