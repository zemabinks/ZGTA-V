import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reuse_generated import retained_unit,matching_dependencies

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
class RetainedUnit(unittest.TestCase):
 def fixture(self,root):
  old=root/'old';previous=root/'previous';app=old/'AppRoot';src=app/'Generated/game_0.c';src.parent.mkdir(parents=True);src.write_text('verified source')
  obj=old/'DerivedData/Build/Intermediates.noindex/PlayGTA5Native.build/Release-iphoneos/PlayGTA5Native.build/Objects-normal/arm64/game_0.o';obj.parent.mkdir(parents=True);obj.write_bytes(b'verified object');deps=obj.with_suffix('.d');deps.write_text('dependencies: '+str(src)+'\n')
  entry={'source':'game_0.c','object':str(obj),'object_sha256':digest(obj),'dependencies_sha256':digest(deps),'app_inputs':{'Generated/game_0.c':digest(src)}}
  record={'generated_object_reuse':{'reused_units':[entry]},'input_hashes':entry['app_inputs'].copy()}
  return previous,obj,deps,app,record
 def test_retained_inputs_and_object_are_attested_again(self):
  with tempfile.TemporaryDirectory() as f:
   root=Path(f).resolve();previous,obj,deps,app,r=self.fixture(root)
   self.assertEqual(retained_unit(previous,r,'game_0',root,digest),(obj,deps,app))
   current=root/'current';(current/'Generated').mkdir(parents=True);(current/'Generated/game_0.c').write_text('changed source')
   self.assertFalse(matching_dependencies([app/'Generated/game_0.c'],app,current,digest))
   obj.write_bytes(b'changed object')
   with self.assertRaisesRegex(ValueError,'integrity'):retained_unit(previous,r,'game_0',root,digest)
 def test_missing_attestation_duplicate_and_changed_source_refused(self):
  with tempfile.TemporaryDirectory() as f:
   root=Path(f).resolve();previous,obj,deps,app,r=self.fixture(root)
   missing=copy.deepcopy(r);missing['input_hashes']={}
   with self.assertRaisesRegex(ValueError,'attested'):retained_unit(previous,missing,'game_0',root,digest)
   duplicate=copy.deepcopy(r);duplicate['generated_object_reuse']['reused_units']*=2
   with self.assertRaises(ValueError):retained_unit(previous,duplicate,'game_0',root,digest)
   (app/'Generated/game_0.c').write_text('changed old source')
   with self.assertRaisesRegex(ValueError,'inputs differ'):retained_unit(previous,r,'game_0',root,digest)
 def test_bundled_compiler_headers_require_matching_previous_copy(self):
  with tempfile.TemporaryDirectory() as f:
   root=Path(f).resolve();previous,obj,deps,app,r=self.fixture(root)
   header=app/'Tools/compiler.h';header.parent.mkdir();header.write_text('verified compiler header')
   prior=previous/'AppRoot/Tools/compiler.h';prior.parent.mkdir(parents=True);prior.write_bytes(header.read_bytes())
   deps.write_text(deps.read_text().strip()+' '+str(header)+'\n');e=r['generated_object_reuse']['reused_units'][0];e['dependencies_sha256']=digest(deps);e['app_inputs']['Tools/compiler.h']=digest(header)
   self.assertEqual(retained_unit(previous,r,'game_0',root,digest),(obj,deps,app))
   prior.write_text('changed compiler header')
   with self.assertRaisesRegex(ValueError,'attested'):retained_unit(previous,r,'game_0',root,digest)
 def test_external_paths_and_symlinks_refused(self):
  with tempfile.TemporaryDirectory() as f:
   root=Path(f).resolve();previous,obj,deps,app,r=self.fixture(root)
   bad=copy.deepcopy(r);bad['generated_object_reuse']['reused_units'][0]['object']='/private/tmp/game_0.o'
   with self.assertRaises(ValueError):retained_unit(previous,bad,'game_0',root,digest)
   link=obj.with_name('copy.o');obj.rename(link);obj.symlink_to(link)
   with self.assertRaises(ValueError):retained_unit(previous,r,'game_0',root,digest)
if __name__=='__main__':unittest.main()
