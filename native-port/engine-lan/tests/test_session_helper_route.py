import tempfile,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from serve_browser import Content
class SessionHelperRoute(unittest.TestCase):
 def test_shared_helper_is_available_to_offline_workers(self):
  with tempfile.TemporaryDirectory()as directory:
   content=object.__new__(Content);content.stage=Path(directory).resolve();content.features=True;content.files=['session-restart.js'];data=b'globalThis.fixture=true;';(content.stage/'session-restart.js').write_bytes(data)
   stream,mime=content.feature_file('session-restart.js')
   with stream:self.assertEqual(stream.read(),data)
   self.assertIn('javascript',mime)
