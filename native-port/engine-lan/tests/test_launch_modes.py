"""Offline launch-choice and immutable native mode-gate regressions; no game."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT.parent/'app'
sys.path.insert(0,str(ROOT))
import prepare_experimental as prepare

def run(args):
    p=subprocess.run([str(a) for a in args],capture_output=True,text=True,timeout=90)
    if p.returncode:raise AssertionError(p.stdout+'\n'+p.stderr)
    return p.stdout

class LaunchModes(unittest.TestCase):
    def test_mode_gate_offline_without_relay_and_stable_lan(self):
        with tempfile.TemporaryDirectory(prefix='zema-launch-mode-') as d:
            binary=Path(d)/'test'
            run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-I',ROOT,'-I',APP/'Source',ROOT/'EngineLanMode.c',ROOT/'tests/launch_mode.c','-o',binary])
            for mode in ['offline','lan','legacy']:
                self.assertIn('EXPLICIT_LAUNCH_MODE_OFFLINE_NO_RELAY_AND_DISCONNECT_STABILITY_PASS',run([binary,mode]))
    def test_choice_does_not_replace_saved_offline_mode(self):
        with tempfile.TemporaryDirectory(prefix='zema-launch-choice-') as d:
            path=Path(d).resolve();binary=path/'test'
            run(['/usr/bin/swiftc','-warnings-as-errors','-module-cache-path',path/'cache',ROOT/'EngineLanLaunchChoice.swift',ROOT/'tests/launch_choice.swift','-o',binary])
            self.assertIn('LAUNCH_CHOICES_KEEP_OFFLINE_RAW_VALUES_AND_LAN_IS_EXPLICIT_PASS',run([binary]))
    def test_setup_and_final_green_launch_are_separate_in_real_stage(self):
        patched=prepare.controller_patch((APP/'App/NativePortViewController.swift').read_text())
        setup=patched.split('home.multiplayerAction =',1)[1].split('home.multiplayerPlayButton.addAction',1)[0]
        self.assertIn('presentSetup(from: self',setup)
        self.assertNotIn('startEngine()',setup)
        final=patched.split('home.multiplayerPlayButton.addAction',1)[1].split('output.isEditable = false',1)[0]
        self.assertIn('!self.engineFailed, ZemaEngineLANUI.shared.ready',final)
        self.assertLess(final.index('launchChoice.select(index: 2)'),final.index('self.startEngine()'))
        self.assertNotIn('presentQuick(',patched)
        self.assertIn('home.setMultiplayerState(role:',patched)

    def test_real_controller_stage_retains_offline_routes(self):
        patched=prepare.controller_patch((APP/'App/NativePortViewController.swift').read_text())
        self.assertIn('HomeView(modes: GameMode.allCases.map',patched)
        self.assertIn('+ [("Multiplayer", "network")]',patched)
        self.assertIn('if launchChoice.isLAN && !ZemaEngineLANUI.shared.ready',patched)
        self.assertNotIn('GameSettings.shared.gameMode = .story',patched)
        self.assertNotIn('OnlineSettings.enabled =',patched)
        self.assertIn('launchChoice.select(index: index)',patched)
        self.assertNotIn('if index == 2 { self.showOnline(); return }',patched)
        self.assertIn('if index == 2 { _ = self.launchChoice.select(index: 2); self.refreshModeChoice(); return }',patched)
        self.assertIn('playConfigured(from: self',patched)
        self.assertLess(patched.index('guard ZemaLabSelectMode('),patched.index('engineStarted = true'))
        engine=prepare.engine_patch((APP/'Source/EngineHost.c').read_text())
        self.assertIn('if(ZemaLabEnabled()&&!ZemaLabAttach(&env.game))',engine)
        self.assertNotIn('if(!ZemaLabEnabled()||!ZemaLabAttach',engine)

if __name__=='__main__':unittest.main()
