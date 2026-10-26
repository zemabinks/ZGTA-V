"""Pinned real-engine parser/compile checks and synthetic typed controller host tests.

No GTA instance, browser game, phone or production save is started.
"""
import hashlib
import json
from pathlib import Path
from public_test_inputs import game_file
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import browser_features as features

STAGE=ROOT.parent/'app/Build/EngineLAN-FeaturesBrowser-20261018-v17'
ORIGINAL=game_file('b/8b0b5899ed/game.wasm')
LAN=ROOT.parent/'app/Build/EngineLAN-OnlineBrowser-20261017-v5/game.engine-lan.wasm'


def run(args,timeout=120):
    result=subprocess.run([str(a) for a in args],capture_output=True,text=True,timeout=timeout)
    if result.returncode:raise AssertionError(result.stdout[-4000:]+'\n'+result.stderr[-6000:])
    return result.stdout


class BrowserFeatures(unittest.TestCase):
    def test_typed_shared_pad_targeting_trainer_and_failure_paths(self):
        import memory_filename, text_fallback, script_bank, gamer_tags
        with tempfile.TemporaryDirectory() as tmp:
            spec=Path(tmp)/'adapter.json';hook=dict(memory_filename.HOOK,slot=1);text_hook=dict(text_fallback.HOOK,slot=2,original_export='zema:features:original_text')
            bank_hooks=[dict(h,slot=3+n,original_export='zema:features:original_'+h['field']) for n,h in enumerate(script_bank.HOOKS)]
            gamer_hook=dict(gamer_tags.HOOK,slot=5,original_export='zema:features:original_gamer_tag_render')
            spec.write_text(json.dumps({'hook':hook,'text_hook':text_hook,'bank_hooks':bank_hooks,'gamer_hook':gamer_hook,'aux':list(features.b.auxiliary([{'field':'pad_update','params':['i64'],'results':[]},hook,text_hook,*bank_hooks,gamer_hook]))}))
            out=run(['node',ROOT/'tests/browser_features_fixture.cjs',ROOT,spec])
        self.assertIn('"typedCallbackVerified":true',out)
        self.assertIn('"gtaInstantiated":false',out)

    def test_trainer_regressions(self):
        self.assertIn('"gameplayVerified":false',run(['node',ROOT/'tests/trainer_fixture.cjs',ROOT/'browser-trainer.js']))

    def test_native_frontend_gate(self):
        self.assertIn('NATIVE_LOADING_OBSERVATION_FRONTEND_GATE_PASS',run(['node',ROOT/'tests/loading_fixture.cjs']))

    def test_unreviewed_engine_rejected_before_parsing(self):
        with self.assertRaisesRegex(ValueError,'Unreviewed engine'):
            features.transform(b'not a reviewed game')

    def test_real_pinned_engines_keep_indices_and_exact_other_bodies(self):
        for source,staged_name in [(ORIGINAL,'game.features.offline.wasm'),(LAN,'game.engine-lan.wasm')]:
            with self.subTest(engine=source.name):
                before=source.read_bytes();after,meta=features.transform(before)
                self.assertEqual(hashlib.sha256(before).hexdigest(),meta['input_sha256'])
                self.assertEqual(hashlib.sha256(after).hexdigest(),meta['patched_sha256'])
                # Historical stages predate optional hooks; compare only matching metadata.
                if STAGE.exists():
                    record=STAGE/('browser-features-offline.json' if staged_name=='game.features.offline.wasm' else 'engine-lan-module.json')
                    historical=json.loads(record.read_text())
                    historical=historical.get('features',historical)
                    if historical.get('blip_sprites')==meta.get('blip_sprites'):self.assertEqual(after,(STAGE/staged_name).read_bytes())
                parts0=list(features.b.gate.sections(before));parts1=list(features.b.gate.sections(after))
                self.assertEqual([(k,v) for k,v in parts0 if k not in (3,4,7,8,10)],[(k,v) for k,v in parts1 if k not in (3,4,7,8,10)])
                oldtypes,oldindices,_=features.b.gate.module_abi(before)
                newtypes,newindices,_=features.b.gate.module_abi(after)
                self.assertEqual(newtypes,oldtypes);self.assertEqual(newindices[:len(oldindices)],oldindices);self.assertEqual(newindices[len(oldindices):],[oldindices[i] for i in [77480,21855,7226,35212,35144]])
                old=dict(parts0);new=dict(parts1)
                reader=features.b.gate.Reader(old[3]);defined=reader.count();imported=len(oldindices)-defined
                def bodies(raw):
                    r=features.b.gate.Reader(raw);out=[r.take(r.uint()) for _ in range(r.count())];r.finish();return out
                a,b=bodies(old[10]),bodies(new[10]);self.assertEqual(len(b),len(a)+5);self.assertEqual(b[-5:],[a[i-imported] for i in [77480,21855,7226,35212,35144]])
                changed=[i+imported for i,(x,y) in enumerate(zip(a,b)) if x!=y]
                self.assertEqual(changed,[1652,7226,10454,21855,35144,35212,77480])
                self.assertEqual(meta['session_observation'],features.SESSION_OBSERVATION)
                self.assertEqual(meta['memory_file_name']['slot'],meta['hook']['slot']+1)
                self.assertEqual(meta['gamer_tag']['slot'],meta['hook']['slot']+5)
                self.assertEqual([h['slot'] for h in meta['script_bank']],[meta['hook']['slot']+3,meta['hook']['slot']+4])
                self.assertEqual(hashlib.sha256(a[10454-imported]).hexdigest(),features.PAD_HASH)
                self.assertNotIn(8,new)
                self.assertFalse(meta['runtime_verified']);self.assertFalse(meta['physical_controller_verified'])
                with tempfile.TemporaryDirectory(prefix='zema-features-compile-') as directory:
                    binary=Path(directory)/'reviewed-features.wasm';binary.write_bytes(after)
                    code="""const fs=require('node:fs'),assert=require('node:assert/strict');const bytes=fs.readFileSync(process.argv[1]);assert(WebAssembly.validate(bytes));const module=new WebAssembly.Module(bytes);const e=WebAssembly.Module.exports(module);assert(e.some(v=>v.name==='zema:features:tls-base'&&v.kind==='global'));assert(e.some(v=>v.name==='zema:features:CreateVehicle'&&v.kind==='function'));console.log('PINNED_FEATURE_ENGINE_COMPILED_NOT_INSTANTIATED');"""
                    self.assertIn('PINNED_FEATURE_ENGINE_COMPILED_NOT_INSTANTIATED',run(['node','--wasm-staging','-e',code,binary]))


if __name__=='__main__':unittest.main()
