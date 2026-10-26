"""Acknowledged menu recovery regression checks; never operate a game/device."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import native_session_reconnect as recovery
import prepare_experimental as prepare
FIXTURE=ROOT/'tests/reconnect'
BUILD=ROOT.parent/'app/Build'
GENERATED=BUILD/'Phone-VehicleAvailability-20261023-v67-r2/AppRoot/Generated'
WABT=BUILD/'Phone-VehicleAvailability-20261023-v67-r2/AppRoot/Tools/wabt-1.0.42/share/wabt/wasm2c'

class NativeReconnect(unittest.TestCase):
    def fixture(self,names,extra=()):
        with tempfile.TemporaryDirectory(prefix='zgta-reconnect-') as tmp:
            exe=Path(tmp)/'fixture'
            command=['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-pedantic','-I'+str(ROOT),*extra,*[str(p) for p in names],'-o',str(exe)]
            result=subprocess.run(command,capture_output=True,text=True,timeout=40)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    def test_fifteen_planner_cases_stop_before_public(self):
        self.fixture([ROOT/'RecoveryCore.c',ROOT/'ReconnectPlan.c',FIXTURE/'ReconnectPlanFixture.c'])
    def test_nineteen_core_cases(self):
        self.fixture([ROOT/'RecoveryCore.c',FIXTURE/'RecoveryCoreFixture.c'])
    def test_default_gate_off_has_no_engine_calls(self):
        self.fixture([ROOT/'ZemaNativeRecoveryQA.c',FIXTURE/'DisabledFixture.c'])
    def test_nineteen_thread_admission_bridge_cases(self):
        if not GENERATED.exists():self.skipTest('Retained generated ABI inputs unavailable')
        self.fixture([ROOT/'RecoveryCore.c',ROOT/'ReconnectPlan.c',ROOT/'RecoveryObserver.c',ROOT/'ZemaNativeRecoveryQA.c',FIXTURE/'BridgeFixture.c'],
          ['-DZGTA_NATIVE_RECOVERY_QA=1','-Dclock_gettime=ZemaQAFixtureClock','-I'+str(GENERATED),'-I'+str(WABT)])
    def test_generated_original_preserved_and_wrong_pin_rejected(self):
        if not GENERATED.exists():self.skipTest('Retained generated inputs unavailable')
        source=(GENERATED/'game_21.c').read_text();patched=recovery.patch('generated',source)
        self.assertEqual(recovery.patch('generated',patched,undo=True),source)
        with self.assertRaises(ValueError):recovery.patch('generated',source+'\n')
        with self.assertRaises(ValueError):recovery.patch('generated',patched)
    def test_project_changes_only_selected_generated_flags(self):
        spec={'targets':{'PlayGTA5Native':{'sources':['Source',{'path':'Generated','excludes':[],'compilerFlags':'-w'},'EngineLAN'],'settings':{'base':{'PRODUCT_BUNDLE_IDENTIFIER':'com.zemabinks.gtamp.enginelanlab'}}}}}
        recovery.configure(spec);target=spec['targets']['PlayGTA5Native']
        self.assertEqual(target['settings']['base']['PRODUCT_BUNDLE_IDENTIFIER'],'com.zemabinks.gtamp.enginelanlab')
        self.assertEqual(next(x for x in target['sources'] if isinstance(x,dict) and x['path']=='Generated')['excludes'],['game_21.c'])
        self.assertEqual(len([x for x in target['sources'] if isinstance(x,dict) and 'compilerFlags' in x]),7)
    def test_ui_preserves_admission_and_manual_handoff(self):
        source=(ROOT/'SettingsReconnectIntent.swift').read_text()
        self.assertIn('guard let self, self.intent == token',source)
        self.assertIn('dismissSettings {',source)
        self.assertIn('In GTA, select Public Session',source)
        self.assertNotIn('asyncAfter',source)
        planner=(ROOT/'ReconnectPlan.c').read_text()
        for command in ['Q_PUBLIC_VISIBLE','Q_BIND_VISIBLE_QUIT','Q_CONFIRM_BOUND_QUIT']:
            self.assertNotIn('enqueue(r,q,'+command,planner)
        # The reviewed planner remains a research fixture, never a shipping menu driver.
        ui=(ROOT/'EngineLanLabUI.swift').read_text()
        self.assertNotIn('SettingsReconnectIntent',ui)
        self.assertNotIn('ZemaNativeRecoveryReconnectStart',ui)
        self.assertIn('Reconnect network',ui)
        for name in ['prepare_experimental.py','build_experimental.py']:
            self.assertNotIn('native_session_reconnect',(ROOT/name).read_text())

if __name__=='__main__':unittest.main()
