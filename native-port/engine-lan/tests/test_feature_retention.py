"""Source and staged-route regressions against the preserved English app."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT.parent/'app'
REPO=ROOT.parents[1]
BASE='e3198c6557c3552333d2e96aa924290e703f9797'
sys.path.insert(0,str(ROOT))
import prepare_experimental as prepare

def functions(text):return set(re.findall(r'\bfunc\s+(\w+)\s*\(',text))
def original(name):return subprocess.check_output(['git','show',BASE+':native-port/app/App/'+name],cwd=REPO,text=True)

class FeatureRetention(unittest.TestCase):
    def test_original_swift_files_and_function_entries_retained(self):
        names=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,'native-port/app/App'],cwd=REPO,text=True).splitlines()
        for path in names:
            if not path.endswith('.swift'):continue
            name=str(Path(path).relative_to('native-port/app/App'));current=(APP/'App'/name).read_text()
            staged=prepare.controller_patch(current) if name=='NativePortViewController.swift' else prepare.app_patch(Path(name).name,current)
            # The owner requested replacing the standalone SwiftUI Trainer with
            # Mod Manager. Its search/spawn view helpers moved to that screen.
            removed={'matchesSearch','spawnVehicle'} if name=='CheatMenu.swift' else set()
            self.assertTrue(functions(original(name))-removed <= functions(staged),name)
            if name=='CheatMenu.swift':
                manager=(APP/'App/ModManagerViewController.swift').read_text()
                self.assertIn('COMMON_VEHICLES.map',manager)
                self.assertIn('return CHEAT_LIST.filter',manager)
                self.assertIn('private func spawnVehicle(named model: String)',manager)
                self.assertIn('cheatHandler(code, mode)',manager)
    def test_home_tools_and_settings_sections_are_retained(self):
        home=prepare.app_patch('HomeView.swift',(APP/'App/HomeView.swift').read_text())
        self.assertEqual(set(re.findall(r'let (\w+Button) =',original('HomeView.swift')))-{'cheatButton'},set(re.findall(r'let (\w+Button) =',home)))
        settings=prepare.app_patch('SettingsViewController.swift',(APP/'App/SettingsViewController.swift').read_text())
        old=original('SettingsViewController.swift')
        for begin,end in [('    override func tableView(_ tableView: UITableView, numberOfRowsInSection','    override func tableView(_ tableView: UITableView, titleForHeaderInSection')]:
            current=settings[settings.index(begin):settings.index(end)]
            self.assertEqual(current.count('case .device: return 6'),1)
            expected=old[old.index(begin):old.index(end)].replace('case .cheat: return isOnline ? 1 : 2','case .cheat: return 1')
            self.assertEqual(expected,current.replace('case .device: return 6','case .device: return 5'))
    def test_legacy_setup_and_configuration_are_reachable_without_two_backends(self):
        text=prepare.controller_patch((APP/'App/NativePortViewController.swift').read_text())
        for route in ['private func showOnline()', 'private func showEngineLAN()', 'private func showLegacyOnline()', 'OnlineSettingsViewController(running: engineStarted)', 'launchChoice.selectLegacyBridge()', 'guard launchChoice.isLAN || (launchChoice.legacyBridgeSelected ? OnlineSettings.configure(mode: mode)']:
            self.assertIn(route,text)
        self.assertIn('''if launchChoice.isLAN && !ZemaEngineLANUI.shared.ready {
            if !ZemaEngineLANUI.shared.playConfigured(from: self, play: { [weak self] in self?.startEngine() }) { home.showMultiplayerSetupHint() }
            return
        }''',text)
        self.assertIn('if launchChoice.legacyBridgeSelected && OnlineSettings.enabled && OnlineSettings.server.isEmpty { showLegacyOnline(); return }',text)
        name='OnlineSettingsViewController.swift'
        self.assertEqual(prepare.app_patch(name,(APP/'App'/name).read_text()),original(name))
    def test_staged_touch_input_changes_only_online_detection_and_explicit_guard(self):
        source=(APP/'App/TouchControlsView.swift').read_text();staged=prepare.app_patch('TouchControlsView.swift',source)
        marker='    override func touchesBegan('
        guard='        if let message = EngineLanFeaturePolicy.unavailableMessage(button: button.name, engineLAN: ZemaLabEnabled() != 0) {\n            DispatchQueue.main.async { self.unavailableAction?(message) }\n            return\n        }\n'
        self.assertEqual(staged.count(guard),1)
        self.assertIn('let spkOn = EngineVoice.isSpeakerEnabled()',staged)
        self.assertIn('let micOn = EngineVoice.isMicEnabled()',staged)
        normal=staged.replace(guard,'').replace('(ZemaGameIsOnline() != 0)','MugoatOnlineEnabled()')
        for a,b in [('EngineVoice.isMicEnabled()', 'MugoatVoiceIsMicEnabled()'),('EngineVoice.isSpeakerEnabled()', 'MugoatVoiceIsSpeakerEnabled()'),('EngineVoice.setMicEnabled(', 'MugoatVoiceSetMicEnabled('),('EngineVoice.setSpeakerEnabled(', 'MugoatVoiceSetSpeakerEnabled(')]:normal=normal.replace(a,b)
        self.assertEqual(normal[normal.index(marker):],source[source.index(marker):])
    def test_feature_policy_does_not_block_gameplay_or_legacy_actions(self):
        with tempfile.TemporaryDirectory(prefix='zema-feature-policy-') as d:
            path=Path(d).resolve();binary=path/'test'
            result=subprocess.run(['/usr/bin/swiftc','-warnings-as-errors','-module-cache-path',str(path/'cache'),str(ROOT/'EngineLanFeaturePolicy.swift'),str(ROOT/'tests/feature_policy.swift'),'-o',str(binary)],capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('ONLY_LEGACY_ROLE_ACTIONS_REPORT_UNAVAILABLE_ON_LAN_PASS',subprocess.check_output([str(binary)],text=True))

if __name__=='__main__':unittest.main()
