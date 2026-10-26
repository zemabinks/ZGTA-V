"""Browser policy and POSIX package entrypoint checks; no game launch."""
import os,subprocess,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import test_portable
import package_portable,portable_launcher
class BrowserRelease(unittest.TestCase):
 def test_actual_live_room_and_explicit_favorite_policy(self):
  subprocess.run(['node',str(Path(__file__).parent/'browser_lobby_policy.cjs')],check=True,timeout=10)
 def test_posix_archive_command_and_complete_source_mapping(self):
  with tempfile.TemporaryDirectory(prefix='zgta-posix-package-') as tmp:
   root=Path(tmp);stage=root/'stage';test_portable.Portable().fixture_stage(stage)
   result=package_portable.build(stage,root/'out','Browser-Mac-Linux',revision='92',allow_dirty=True)
   with zipfile.ZipFile(result['archive']) as archive:
    info=archive.getinfo('ZGTA-V/Start ZGTA V.command')
    self.assertEqual((info.external_attr>>16)&0o111,0o111)
    self.assertNotIn('Python/python.exe',archive.namelist())
   command=root/'out/ZGTA-V/Start ZGTA V.command'
   subprocess.run(['/bin/sh','-n',str(command)],check=True)
 def test_posix_folder_selection_accepts_spaces_and_preserves_source(self):
  with tempfile.TemporaryDirectory(prefix='zgta-folder-input-') as tmp:
   data=Path(tmp)/'private';data.mkdir()
   expected=Path(tmp)/'game folder';expected.mkdir()
   with patch.dict(os.environ,{'PREFIX':''}),patch('builtins.input',return_value=str(expected)),patch.object(portable_launcher,'validate_mirror',side_effect=lambda p:p if p==expected else (_ for _ in ()).throw(ValueError('unavailable'))):
    self.assertEqual(portable_launcher.load_mirror(data),expected)
   self.assertEqual(list(expected.iterdir()),[])
 def test_noninteractive_missing_folder_is_actionable(self):
  with tempfile.TemporaryDirectory(prefix='zgta-no-folder-') as tmp:
   with patch.dict(os.environ,{'PREFIX':''}),patch('builtins.input',side_effect=EOFError),patch.object(portable_launcher,'validate_mirror',side_effect=ValueError('unavailable')):
    with self.assertRaisesRegex(ValueError,'--mirror'):portable_launcher.load_mirror(Path(tmp))
