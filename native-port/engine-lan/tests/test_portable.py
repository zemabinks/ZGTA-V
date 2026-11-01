"""Portable setup contracts; actual Windows/Android execution remains a device test."""
import hashlib
import json
from pathlib import Path
from public_test_inputs import game_file
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import portable_launcher as launcher
import portable_security as security
import package_portable
import verify_portable

class Portable(unittest.TestCase):
    def fixture_stage(self,stage):
        stage.mkdir()
        worker=b'verified fixture worker';(stage/'wgpu_worker.js').write_bytes(worker)
        engine=b'verified fixture engine';(stage/'game.engine-lan.wasm').write_bytes(engine)
        metadata={'format':'zema-browser-engine-lan-v1','features':{'format':'zema-browser-features-v1'},'patched_sha256':hashlib.sha256(engine).hexdigest()}
        (stage/'engine-lan-module.json').write_text(json.dumps(metadata)+'\n')
        (stage/'engine-lan-module.js').write_text('globalThis.ZemaEngineLanModule='+json.dumps(metadata)+';\n')
        (stage/'browser-stage.json').write_text(json.dumps({'format':'zema-browser-engine-lan-stage-v1','staged_hashes':{'wgpu_worker.js':hashlib.sha256(worker).hexdigest()}})+'\n')
        return worker

    def test_archive_keeps_shared_icon_delta_and_correct_release_number(self):
        import zipfile
        with tempfile.TemporaryDirectory(prefix='zgta-portable-package-') as folder:
            root=Path(folder);stage=root/'stage';worker=self.fixture_stage(stage)
            (stage/'unrelated-proof.txt').write_text('not runtime')
            result=package_portable.build(stage,root/'output','Android-Termux',revision='63',allow_dirty=True)
            with zipfile.ZipFile(result['archive']) as archive:
                self.assertIsNone(archive.testzip())
                manifest=json.loads(archive.read('ZGTA-V/portable-manifest.json'))
                self.assertEqual(manifest['build'],63)
                self.assertEqual(manifest['browser_revision'],'63')
                self.assertRegex(manifest['source_revision'],r'^[0-9a-f]{40}$')
                for target,record in manifest['source_files'].items():
                    self.assertEqual(manifest['files'][target],record['sha256'])
                    self.assertEqual(hashlib.sha256((package_portable.SOURCE_ROOT/record['source']).read_bytes()).hexdigest(),record['sha256'])
                self.assertEqual(manifest['runtime_provenance'],package_portable.checked_runtime(stage))
                self.assertFalse(manifest['game_files_included'])
                for rel,sha in manifest['files'].items():
                    self.assertEqual(hashlib.sha256(archive.read('ZGTA-V/'+rel)).hexdigest(),sha,rel)
                delta='native-port/app/Resources/modern-map-icons.json'
                self.assertEqual(archive.read('ZGTA-V/'+delta),(ROOT.parent/'app/Resources/modern-map-icons.json').read_bytes())
                self.assertIn('native-port/app/Resources/ModernBlips/README.txt',manifest['files'])
                catalog='native-port/app/Resources/vehicle-catalog.json'
                self.assertEqual(archive.read('ZGTA-V/'+catalog),(ROOT.parent/'app/Resources/vehicle-catalog.json').read_bytes())
                for name in ['vehicle-ui.js','vehicle-catalog.js','browser-trainer.js','trainer-ui.js']:
                    self.assertEqual(archive.read('ZGTA-V/native-port/engine-lan/'+name),(ROOT/name).read_bytes())
                for name in ['solo-card.png','friends-card.png','los-santos-map.jpg','zplay-gta-green.svg','zplay-gta-green-32.png','zplay-gta-green-180.png','favicon.ico']:
                    self.assertEqual(archive.read('ZGTA-V/native-port/engine-lan/'+name),(ROOT/name).read_bytes())
                self.assertFalse(any(name.startswith(('data/','Game/')) for name in manifest['files']))
                self.assertEqual(archive.read('ZGTA-V/Runtime/wgpu_worker.js'),worker)
                self.assertNotIn('Runtime/unrelated-proof.txt',manifest['files'])
                self.assertNotIn('Python/python.exe',manifest['files'])

    def test_source_snapshot_download_block_is_not_the_obsolete_build91_index(self):
        root=package_portable.SOURCE_ROOT
        index=json.loads((root/'scripts/release-index.json').read_text())
        self.assertGreaterEqual(index['latest_ios_build'],101)
        block=(root/'README.md').read_text().split('<!-- current-build:start -->',1)[1].split('<!-- current-build:end -->',1)[0]
        self.assertRegex(block,r'\bBuild\s*'+str(index['latest_ios_build'])+r'\b')  # Product labels are separate from the internal build counter.
        self.assertIn('/releases/tag/'+index['installer_proof']['tag'],block)
        self.assertNotIn('Newest iPhone installer: [Build 91]',block)
        # SOURCE_VERSION is intentionally historical, not a mutable download index.

    def test_source_channel_is_exact_and_does_not_advertise_unknown_remotes(self):
        private='https://github.com/zemabinks/ZGTA-V-Private-Development'
        public='https://github.com/zemabinks/ZGTA-V'
        for remote in [private,private+'.git','git@github.com:zemabinks/ZGTA-V-Private-Development.git']:
            self.assertEqual(package_portable.source_channel(remote),{'source_repository':private,'release_channel':'private-development'})
        self.assertEqual(package_portable.source_channel(public+'.git'),{'source_repository':public,'release_channel':'public'})
        for remote in ['https://example.com/private.git',private+'.git/extra','https://github.com/another/ZGTA-V.git','https://user:secret@example.com/repo.git']:
            self.assertEqual(package_portable.source_channel(remote),{'source_repository':None,'release_channel':'unspecified'})

    def test_non_windows_runtime_provenance_and_private_candidate_update_channel(self):
        import zipfile
        for platform,python_source in [('Android-Termux','EXISTING_TERMUX_PYTHON'),('Browser-Mac-Linux','SYSTEM_PYTHON')]:
            with self.subTest(platform=platform),tempfile.TemporaryDirectory(prefix='zgta-portable-channel-') as folder:
                root=Path(folder);stage=root/'stage';self.fixture_stage(stage)
                original=package_portable.subprocess.run
                def run(args,**kwargs):
                    if args==['git','remote','get-url','origin']:
                        return Mock(stdout='https://github.com/zemabinks/ZGTA-V-Private-Development.git\n')
                    return original(args,**kwargs)
                with patch.object(package_portable.subprocess,'run',side_effect=run):
                    result=package_portable.build(stage,root/'output',platform,revision='101',allow_dirty=True)
                with zipfile.ZipFile(result['archive']) as archive:
                    manifest=json.loads(archive.read('ZGTA-V/portable-manifest.json'))
                    guide=archive.read('ZGTA-V/START HERE.txt').decode()
                    self.assertEqual(manifest['python_source'],python_source)
                    self.assertEqual(manifest['release_channel'],'private-development')
                    self.assertEqual(manifest['source_repository'],'https://github.com/zemabinks/ZGTA-V-Private-Development')
                    self.assertIn('Private development candidate',guide)
                    self.assertIn('owner gameplay acceptance is still pending',guide)
                    self.assertIn('Source and candidate updates: '+manifest['source_repository'],guide)
                    self.assertNotIn('Source and updates: https://github.com/zemabinks/ZGTA-V\n',guide)

    def test_packaging_rejects_changed_runtime_before_writing_output(self):
        with tempfile.TemporaryDirectory(prefix='zgta-portable-bad-stage-') as folder:
            root=Path(folder);stage=root/'stage';self.fixture_stage(stage)
            (stage/'wgpu_worker.js').write_bytes(b'unreviewed worker')
            with self.assertRaisesRegex(ValueError,'Staged browser bytes changed'):
                package_portable.build(stage,root/'output','Android-Termux',revision='63')
            self.assertFalse((root/'output').exists())

    def test_packaging_refuses_runtime_symlink_and_invalid_revision(self):
        with tempfile.TemporaryDirectory(prefix='zgta-portable-stage-') as folder:
            root=Path(folder);stage=root/'stage';worker=self.fixture_stage(stage)
            (root/'worker.js').write_bytes(worker);(stage/'wgpu_worker.js').unlink();(stage/'wgpu_worker.js').symlink_to(root/'worker.js')
            with self.assertRaisesRegex(ValueError,'Staged browser bytes changed'):
                package_portable.build(stage,root/'output','Android-Termux',revision='63')
            for revision in ['../63','0','63/bad','']:
                with self.assertRaisesRegex(ValueError,'Invalid release revision'):
                    package_portable.build(stage,root/'output','Android-Termux',revision=revision)

    def test_bad_windows_runtime_archive_is_not_downloaded_or_extracted(self):
        with tempfile.TemporaryDirectory(prefix='zgta-portable-windows-') as folder:
            root=Path(folder);stage=root/'stage';self.fixture_stage(stage)
            archive=root/'wrong-python.zip';archive.write_bytes(b'wrong')
            with patch.object(package_portable.urllib.request,'urlopen',side_effect=AssertionError('no network')):
                with self.assertRaisesRegex(ValueError,'Official Python archive checksum mismatch'):
                    package_portable.build(stage,root/'output','Windows-x64',archive,revision='63',allow_dirty=True)
            self.assertFalse((root/'output/ZGTA-V/Python').exists())

    def test_dirty_release_source_refused_before_output_is_created(self):
        with tempfile.TemporaryDirectory(prefix='zgta-portable-freeze-') as folder:
            root=Path(folder);stage=root/'stage';self.fixture_stage(stage)
            original=package_portable.subprocess.run
            def run(args,**kwargs):
                if args[:3]==['git','status','--porcelain=v1']:return Mock(stdout=' M native-port/engine-lan/vehicle-ui.js\n')
                return original(args,**kwargs)
            with patch.object(package_portable.subprocess,'run',side_effect=run):
                with self.assertRaisesRegex(ValueError,'Commit the frozen source'):
                    package_portable.build(stage,root/'output','Android-Termux',revision='63')
            self.assertFalse((root/'output').exists())

    def test_windows_acl_checks_use_sids_and_reject_shared_access(self):
        private={'user':'S-1-5-21-123','owner':'S-1-5-21-123','allow':['S-1-5-21-123','S-1-5-18','S-1-5-32-544']}
        self.assertTrue(security.valid_acl(private))
        for change in [{'owner':'S-1-5-18'},{'allow':[]},{'allow':['S-1-1-0']},{'allow':['S-1-5-21-123','S-1-5-32-545']}]:self.assertFalse(security.valid_acl(dict(private,**change)))
        run=Mock(return_value=Mock(stdout=json.dumps(private).encode()))
        with patch.object(security.subprocess,'run',run):security.windows_private(Path('a folder'),new=False)
        args=run.call_args[0][0];self.assertNotIn('-ExecutionPolicy',args);self.assertNotIn('Set-Acl',args[-1]);self.assertEqual(run.call_args.kwargs['env']['ZGTA_PRIVATE_PATH'],'a folder')

    def test_integrity_refuses_changed_and_escaping_package_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            r=Path(folder);(r/'ok.py').write_text('pass\n');manifest={'format':'zgta-portable-v1','files':{'ok.py':hashlib.sha256((r/'ok.py').read_bytes()).hexdigest()}}
            def save():(r/'portable-manifest.json').write_text(json.dumps(manifest))
            save();launcher.verify_package(r)
            (r/'ok.py').write_text('changed')
            with self.assertRaisesRegex(ValueError,'changed'):launcher.verify_package(r)
            for rel in ['../outside','/outside','a\\b']:
                manifest['files']={rel:'a'*64};save()
                with self.assertRaisesRegex(ValueError,'path'):launcher.verify_package(r)

    def test_integrity_refuses_unlisted_helper_and_parent_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);code=root/'native-port/engine-lan';code.mkdir(parents=True)
            good=code/'ok.py';good.write_text('pass\n')
            manifest={'format':'zgta-portable-v1','files':{'native-port/engine-lan/ok.py':hashlib.sha256(good.read_bytes()).hexdigest()}}
            (root/'portable-manifest.json').write_text(json.dumps(manifest));launcher.verify_package(root)
            (code/'shadow.py').write_text('pass\n')
            with self.assertRaisesRegex(ValueError,'Unlisted launcher file'):launcher.verify_package(root)
            (code/'shadow.py').unlink();code.rename(root/'actual-code');code.symlink_to(root/'actual-code')
            with self.assertRaisesRegex(ValueError,'Incomplete package'):launcher.verify_package(root)

    def test_published_source_match_checks_revision_bytes_and_complete_mapping(self):
        sha='a'*64;revision='b'*40;target='native-port/engine-lan/example.py'
        manifest={'source_revision':revision,'build':63,'source_worktree_dirty':False,'files':{target:sha},'source_files':{target:{'source':target,'sha256':sha}}}
        reference={'format':'zgta-source-manifest-v1','original_source_revision':revision,'build':63,'files':{target:sha}}
        verify_portable.source_match(manifest,reference)
        for change in [{'original_source_revision':'c'*40},{'build':62},{'files':{target:'d'*64}}]:
            with self.assertRaises(ValueError):verify_portable.source_match(manifest,dict(reference,**change))
        for change in [{'source_worktree_dirty':True},{'source_files':{}},{'files':{target:sha,'native-port/unmapped.py':sha}}]:
            with self.assertRaises(ValueError):verify_portable.source_match(dict(manifest,**change),reference)
        with self.assertRaises(ValueError):verify_portable.source_match(dict(manifest,source_files=dict(manifest['source_files'],ghost={})),reference)

    def test_mirror_selection_never_creates_or_downloads_game_files(self):
        with tempfile.TemporaryDirectory() as folder:
            r=Path(folder)
            with self.assertRaisesRegex(ValueError,'mirror folder'):launcher.validate_mirror(r)
            self.assertEqual(list(r.iterdir()),[])
        mirror=game_file('')
        self.assertEqual(launcher.validate_mirror(mirror),mirror.resolve())

    def test_existing_launcher_check_requires_own_service_marker(self):
        import io
        response=Mock();response.open.return_value=io.BytesIO(b'{"service":"other"}')
        with patch.object(launcher.urllib.request,'build_opener',return_value=response):self.assertFalse(launcher.existing_launcher())
        response.open.return_value=io.BytesIO(b'{"service":"zgta-browser-launcher"}')
        with patch.object(launcher.urllib.request,'build_opener',return_value=response):self.assertTrue(launcher.existing_launcher())

    def test_existing_launcher_validates_bounded_identity_and_legacy_hosts(self):
        import io
        manifest={'build':101,'browser_revision':'101','source_revision':'a'*40,
                  'runtime_provenance':{'stage_manifest_sha256':'b'*64,'module_metadata_sha256':'c'*64}}
        identity=launcher.package_identity(manifest)
        for payload,want in [
            ({'service':'zgta-browser-launcher','identity':identity},identity),
            ({'service':'zgta-browser-launcher'},None),
            ({'service':'zgta-browser-launcher','identity':dict(identity,source_revision='/private/path')},None)]:
            opener=Mock();opener.open.return_value=io.BytesIO(json.dumps(payload).encode())
            with patch.object(launcher.urllib.request,'build_opener',return_value=opener):
                self.assertEqual(launcher.existing_launcher(),{'service':'zgta-browser-launcher','identity':want})
        for payload in [[],{'service':'other'},'zgta-browser-launcher']:
            opener=Mock();opener.open.return_value=io.BytesIO(json.dumps(payload).encode())
            with patch.object(launcher.urllib.request,'build_opener',return_value=opener):
                self.assertIsNone(launcher.existing_launcher())

    def test_local_gpu_probe_and_fast_setup_preserve_identity(self):
        code='''const assert=require('node:assert/strict'),P=require(process.argv[1]);(async()=>{let options;const r=await P.inspect({gpu:{requestAdapter:async o=>{options=o;return {features:new Set(['texture-compression-bc']),info:{description:'Test GPU'}};}}},WebAssembly,true);assert.equal(options.powerPreference,'high-performance');assert.equal(r.adapter,'Test GPU');assert.equal(r.bc,true);let old={room:'KEEP',player:'KEEP',fps:30};assert.equal(P.faster(old).fps,60);assert.equal(P.faster(old).room,'KEEP');assert.equal(old.fps,30);assert.equal((await P.inspect({},WebAssembly,true)).webgpu,false);})();'''
        result=subprocess.run(['node','-e',code,str(ROOT/'browser-performance.js')],capture_output=True,text=True,timeout=10);self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
