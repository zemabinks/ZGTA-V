"""Stage a side-by-side Intel experiment; never update the source build/IPA.

Uses APFS copy-on-write clones of verified precompiled inputs. All patches and
project generation are confined to a new private app Build child.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parent;APP=ROOT.parent/'app'
sys.path.insert(0,str(APP/'Scripts'))
import prepare_engine_lan_adapter as adapter
import inspect_engine_lan as gate
from prepare_shaders import verify_pair,digest_file
from prepare_ui_assets import FILES as UI_FILES
from stage_intel_dependencies import verify_staged,load_manifest
from app_branding import icon_properties
import social_tables
import native_script_bank
import world_commands
import gamer_tags
import prepare_text_fallback
import prepare_blip_sprites
import generate_text_labels
import generate_vehicle_catalog

def once(text,old,new):
    if text.count(old)!=1:raise ValueError('Reviewed source anchor changed: '+old[:100])
    return text.replace(old,new)

def engine_patch(text):
    text=once(text,'#include "MugoatOnline.h"','#include "MugoatOnline.h"\n#include "ZemaExperimental.h"')
    text=once(text,'void PGSetBackBufferSize(int width,int height){',
        'void PGSetBackBufferSize(int width,int height){\n  if(ZemaLabEnabled()){pg_log("Engine LAN: back-buffer size is fixed for this session; resolution changes apply next launch.");return;}')
    text=once(text,'  wasm2c_game_instantiate(&env.game, &env, &wasi);','  wasm2c_game_instantiate(&env.game, &env, &wasi);\n  if(ZemaLabEnabled()&&!ZemaLabAttach(&env.game)){pg_log("Engine LAN startup refused: typed host unavailable.");return NULL;}')
    text=once(text,'  if (!strcmp(key, "lowMemory")) return 1;','  if (!strcmp(key, "lowMemory")) return 1;\n  if(ZemaLabEnabled()&&!strcmp(key,"keepThreads"))return fallback|6;')
    text=once(text,'for(unsigned i=0;i<sizeof base/sizeof *base;i++)options[optionCount++]=base[i];','for(unsigned i=0;i<sizeof base/sizeof *base;i++)if(!ZemaLabEnabled()||strcmp(base[i],"-nonetwork"))options[optionCount++]=base[i];\n  if(ZemaLabEnabled()){const char* lan[]={"-lan","-StraightIntoFreemode","-netMpSkipCloudFileRequirements","-sc_noOnlinePolicy","-netshoptransactionnull","-netGameTransactionsNoToken","-nocatalog","-wasmstartchoice=1","-disableDebugPadButtons","-disallowdebugpad"};for(unsigned i=0;i<10;i++)options[optionCount++]=lan[i];}')
    text=once(text,'const char *options[64];unsigned optionCount=0;','const char *options[128];unsigned optionCount=0;')
    text=once(text,'int PGWorldToolsMode(void) { return MugoatOnlineEnabled() ? 0 : 1; }',
        'int PGWorldToolsMode(void) { return ZemaLabEnabled() ? 2 : (MugoatOnlineEnabled() ? 0 : 1); }')
    return text.replace('MugoatOnlineEnabled()', 'ZemaGameIsOnline()')

def controller_patch(text):
    text=once(text,'    private var thermalScale = 1.0',
        '    private var thermalScale = 1.0\n    private var lanThermalGraphics = EngineLanThermalGraphics()')
    text=once(text,'        bootedBackend = MugoatOnlineEnabled() ? "legacy-bridge" : "offline"',
        '        bootedBackend = ZemaLabEnabled() != 0 ? "engine-lan" : MugoatOnlineEnabled() ? "legacy-bridge" : "offline"')
    text=once(text,'        bootedPreset = GameSettings.shared.graphicsPreset',
        '        bootedPreset = GameSettings.shared.graphicsPreset\n        lanThermalGraphics.begin(frameRateCap: GameSettings.shared.frameRateCap)')
    text=once(text,'            let state = ProcessInfo.processInfo.thermalState',
        '            if ZemaLabEnabled() != 0 { self.updateLanThermalGraphics(); return }\n            let state = ProcessInfo.processInfo.thermalState')
    text=once(text,'    private func applyLiveResolution() {\n        guard engineStarted else { return }',
        '    private func updateLanThermalGraphics() {\n        guard engineStarted, !engineFailed, ZemaLabEnabled() != 0 else { return }\n        if let limit = lanThermalGraphics.nextLimit(thermalState: ProcessInfo.processInfo.thermalState.rawValue, ready: worldReadyAt != nil, now: CACurrentMediaTime()) {\n            requestedFrameInterval = limit\n            PGSetFrameLimit(limit)\n            PGSetPresentPacing(limit > 0 ? Double(limit) / 60.0 : 0)\n            appendLog("Engine LAN thermal protection: frame limit interval \\(limit); startup resolution retained.")\n        }\n    }\n    private func applyLiveResolution() {\n        guard engineStarted else { return }\n        if ZemaLabEnabled() != 0 {\n            appendLog("Engine LAN: resolution saved for next launch; live device reset deferred.")\n            showCheatToast("Resolution saved. Restart this lab app to apply it.")\n            return\n        }')
    text=once(text,'        let now = CACurrentMediaTime()\n        if now - lastFPSLabelUpdate',
        '        updateLanThermalGraphics()\n        let now = CACurrentMediaTime()\n        if now - lastFPSLabelUpdate')
    text=once(text,'HomeView(modes: GameMode.allCases.map { ($0.title, $0 == .story ? "book.fill" : "map.fill") }, log: output)',
        'HomeView(modes: GameMode.allCases.map { ($0 == .sandbox ? "Free Roam" : $0.title, $0 == .story ? "book.fill" : "map.fill") } + [("Multiplayer", "network")], log: output)')
    text=once(text,'    private var engineStarted = false','    private var engineStarted = false\n    private var launchChoice = EngineLanLaunchChoice()')
    text=once(text,'            GameSettings.shared.gameMode = GameMode.allCases[index]',
        '            if index == 2 { _ = self.launchChoice.select(index: 2); self.refreshModeChoice(); return }\n            if let raw = self.launchChoice.select(index: index), let mode = GameMode(rawValue: raw) {\n                GameSettings.shared.gameMode = mode\n                ZemaEngineLANUI.shared.leaveBeforeOfflineLaunch()\n            }')
    text=once(text,'home.setMode(choice.flatMap { GameMode.allCases.firstIndex(of: $0) }, detail: choice?.detail ?? L10n.text("Choose Story mode or Sandbox to play."), enabled: !engineStarted)',
        'home.setMode(launchChoice.selectedIndex(savedMode: choice?.rawValue), detail: launchChoice.isLAN ? ZemaEngineLANUI.shared.connectionDetail : launchChoice.legacyBridgeSelected ? (OnlineSettings.enabled ? "Existing multiplayer bridge selected. Use its server, role and PvP settings; it is separate from Engine LAN." : "The existing bridge is disabled. Story or Free Roam will start offline.") : choice?.detail ?? L10n.text("Choose Story mode or Sandbox to play."), enabled: !engineStarted)')
    text=once(text,'visible: choice == .sandbox, enabled: !engineStarted','visible: !launchChoice.isLAN && choice == .sandbox, enabled: !engineStarted')
    text=once(text,'        if OnlineSettings.enabled && OnlineSettings.server.isEmpty { showOnline(); return }','        if launchChoice.isLAN && !ZemaEngineLANUI.shared.ready {\n            if !ZemaEngineLANUI.shared.playConfigured(from: self, play: { [weak self] in self?.startEngine() }) { home.showMultiplayerSetupHint() }\n            return\n        }\n        if launchChoice.legacyBridgeSelected && OnlineSettings.enabled && OnlineSettings.server.isEmpty { showLegacyOnline(); return }')
    text=once(text,'        if GameSettings.shared.gameModeChoice == nil &&','        if !launchChoice.isLAN && GameSettings.shared.gameModeChoice == nil &&')
    text=once(text,'        let mode = GameSettings.shared.gameMode\n        guard OnlineSettings.configure(mode: mode) else {',
        '        let mode = GameMode(rawValue: Int(launchChoice.engineMode(savedMode: GameSettings.shared.gameModeChoice?.rawValue))) ?? .sandbox\n        if !launchChoice.legacyBridgeSelected { setenv("MUGUET_PVP", "0", 1) }\n        if launchChoice.isLAN { unsetenv("MUGUET_SERVER") }\n        // Do not latch the legacy backend during a LAN admission attempt.\n        guard launchChoice.isLAN || (launchChoice.legacyBridgeSelected ? OnlineSettings.configure(mode: mode) : MugoatOnlineConfigure("", "", "", Int32(mode.rawValue))) else {')
    text=once(text,'        metalView.isPaused = true\n        metalView.delegate = nil',
        '        guard ZemaLabSelectMode(launchChoice.isLAN ? 1 : 0) == 1 else {\n            showWhenFree(title: "Game mode", message: "LAN is not ready, or a different mode already started. Reconnect or restart this lab app.")\n            return\n        }\n        if !launchChoice.isLAN { ZemaEngineLANUI.shared.leaveBeforeOfflineLaunch() }\n        metalView.isPaused = true\n        metalView.delegate = nil')
    text=once(text,'        let controller = OnlineSettingsViewController(running: engineStarted)\n        let navigation = UINavigationController(rootViewController: controller)\n        Theme.styleNavigation(navigation); present(navigation, animated: true)',
        '        if engineStarted {\n            if ZemaLabEnabled() != 0 { showEngineLAN() }\n            else if MugoatOnlineEnabled() { showLegacyOnline() }\n            else { showWhenFree(title: "Multiplayer", message: "This game started offline. Restart this lab app to choose a multiplayer backend; your saves are preserved.") }\n            return\n        }\n        ZemaEngineLANUI.shared.presentChoices(from: self) { [weak self] in\n            guard let self else { return }\n            _ = self.launchChoice.select(index: 2)\n            self.refreshModeChoice()\n        }\n    }\n    private func showEngineLAN() {\n        guard presentedViewController == nil else { return }\n        if engineStarted && ZemaLabEnabled() == 0 {\n            showWhenFree(title: "Engine LAN", message: "Restart this lab app to change multiplayer backends; your saves are preserved.")\n            return\n        }\n        if !engineStarted { _ = launchChoice.select(index: 2); refreshModeChoice() }\n        ZemaEngineLANUI.shared.present(from: self, running: engineStarted)\n    }\n    private func showLegacyOnline() {\n        guard presentedViewController == nil else { return }\n        if engineStarted && ZemaLabEnabled() != 0 {\n            showWhenFree(title: "Multiplayer", message: "Restart this lab app to change multiplayer backends; your saves are preserved.")\n            return\n        }\n        if !engineStarted {\n            launchChoice.selectLegacyBridge()\n            ZemaEngineLANUI.shared.leaveBeforeOfflineLaunch()\n            refreshModeChoice()\n        }\n        let controller = OnlineSettingsViewController(running: engineStarted)\n        controller.changed = { [weak self] in self?.refreshModeChoice() }\n        let navigation = UINavigationController(rootViewController: controller)\n        Theme.styleNavigation(navigation); present(navigation, animated: true)')
    text=once(text,'        let controller = SettingsViewController(engineRunning: engineStarted, runningMode: bootedMode)',
        '        let controller = SettingsViewController(engineRunning: engineStarted, runningMode: bootedMode)\n        if engineStarted && ZemaLabEnabled() != 0 { controller.reconnectSession = { [weak self] in self?.dismiss(animated: true) { [weak self] in guard let self else { return }; ZemaEngineLANUI.shared.reconnectSession(from: self) } } }\n        controller.navigationItem.leftBarButtonItem = UIBarButtonItem(title: "Multiplayer", image: UIImage(systemName: "network"), primaryAction: UIAction { [weak self] _ in\n            self?.dismiss(animated: true) { [weak self] in self?.showOnline() }\n        })')
    text=once(text,'controller.gameModeChanged = { [weak self] in self?.refreshModeChoice() }',
        'controller.gameModeChanged = { [weak self] in self?.launchChoice.offlineModeChanged(); self?.refreshModeChoice() }')
    text=once(text,'        output.isEditable = false', '        ZemaEngineLANUI.shared.log = { [weak self] line in self?.appendLog(line) }\n        ZemaEngineLANUI.shared.changed = { [weak self] in self?.refreshModeChoice() }\n        home.configureMultiplayerActions()\n        home.multiplayerAction = { [weak self] role in\n            guard let self, !self.engineStarted else { return }\n            ZemaEngineLANUI.shared.presentSetup(from: self, role: role, selected: { [weak self] in\n                guard let self else { return }; _ = self.launchChoice.select(index: 2); self.refreshModeChoice()\n            })\n        }\n        home.multiplayerPlayButton.addAction(UIAction { [weak self] _ in\n            guard let self, !self.engineStarted, !self.engineFailed, ZemaEngineLANUI.shared.ready else { return }\n            _ = self.launchChoice.select(index: 2)\n            self.refreshModeChoice()\n            self.startEngine()\n        }, for: .touchUpInside)\n        output.isEditable = false')
    text=once(text,'        touchControls.onVoiceMicChanged = { [weak self] enabled in self?.handleVoiceMicChanged(enabled) }',
        '        touchControls.onVoiceMicChanged = { [weak self] enabled in self?.handleVoiceMicChanged(enabled) }\n        touchControls.unavailableAction = { [weak self] message in self?.showCheatToast(message) }')
    text=once(text,'        launchButton.isEnabled = !engineStarted && !engineFailed',
        '        launchButton.isEnabled = !engineStarted && !engineFailed\n        home.setMultiplayerState(role: ZemaEngineLANUI.shared.selectedRole, detail: ZemaEngineLANUI.shared.launchDetail, ready: ZemaEngineLANUI.shared.ready, enabled: !engineStarted && !engineFailed)')
    # The solo button always uses the saved offline choice, even after visiting multiplayer.
    text=once(text,'launchButton.addTarget(self, action: #selector(startEngine), for: .touchUpInside)',
        'launchButton.addAction(UIAction { [weak self] _ in\n            guard let self, !self.engineStarted else { return }\n            _ = self.launchChoice.select(index: GameSettings.shared.gameModeChoice == .story ? 0 : 1)\n            self.refreshModeChoice()\n            self.startEngine()\n        }, for: .touchUpInside)')
    return app_patch('NativePortViewController.swift',text)


def app_patch(name,text):
    if name=='SettingsViewController.swift':
        text=once(text,'            var text = L10n.text("Resolution changes apply right away. ")',
            '            var text = engineRunning && ZemaLabEnabled() != 0 ? "Engine LAN resolution changes apply after restarting the app. Thermal protection reduces FPS without resizing the game, then waits for 30 seconds of steady cooling before restoring a faster cap. " : L10n.text("Resolution changes apply right away. ")')
        text=once(text,'content.secondaryText = currentSizeText() + L10n.text(" · changes right away")',
            'content.secondaryText = currentSizeText() + (engineRunning && ZemaLabEnabled() != 0 ? " · applies after restart" : L10n.text(" · changes right away"))')
    if name=='TouchControlsView.swift':
        text=once(text,'    var onVoiceMicChanged: ((Bool) -> Void)?', '    var onVoiceMicChanged: ((Bool) -> Void)?\n    var unavailableAction: ((String) -> Void)?')
        text=once(text,'    private func press(_ button: ControlButton, touch: UITouch, at point: CGPoint) {',
            '    private func press(_ button: ControlButton, touch: UITouch, at point: CGPoint) {\n        if let message = EngineLanFeaturePolicy.unavailableMessage(button: button.name, engineLAN: ZemaLabEnabled() != 0) {\n            DispatchQueue.main.async { self.unavailableAction?(message) }\n            return\n        }')
        text=once(text,'            let spkOn = MugoatVoiceIsSpeakerEnabled()', '            let spkOn = ZemaLabEnabled() == 0 && MugoatVoiceIsSpeakerEnabled()')
        text=once(text,'            let micOn = MugoatVoiceIsMicEnabled()', '            let micOn = ZemaLabEnabled() == 0 && MugoatVoiceIsMicEnabled()')
        text=once(text,'            button.isAccessibilityElement = isShown',
            '            button.isAccessibilityElement = isShown\n            if let message = EngineLanFeaturePolicy.unavailableMessage(button: button.name, engineLAN: ZemaLabEnabled() != 0) { button.accessibilityHint = message }')
    if name=='HomeView.swift':
        text=once(text,'        label.font = Theme.body(15, .semibold)',
            '        label.font = Theme.body(15, .semibold)\n        label.adjustsFontSizeToFitWidth = true\n        label.minimumScaleFactor = 0.65')
    if name=='SettingsViewController.swift':
        text=once(text,'MugoatOnlineEnabled() || OnlineSettings.enabled','(ZemaGameIsOnline() != 0)')
    return text.replace('MugoatOnlineEnabled()', '(ZemaGameIsOnline() != 0)')


def asset_patch(text):
    text='#include "ZemaExperimental.h"\nextern int ZemaBroadcastPatch(uint8_t*,size_t);\n'+text
    marker='static int64_t readAsset(uint32_t id,uint64_t offset,uint8_t *destination,uint32_t length){'
    overlay='''static NSData* zemaConfig;
static int zemaGameconfigOverlay(uint32_t id,uint64_t offset,uint8_t* destination,int64_t count){
  if(!ZemaLabEnabled()||count<=0||![assetFiles[id][0] isEqualToString:@"common/data/gameconfig.xml"])return 1;
  @synchronized([NSNull null]){
    if(!zemaConfig){uint64_t n=[assetFiles[id][1] unsignedLongLongValue];if(n>16*1024*1024)return 0;
      NSMutableData* data=[NSMutableData dataWithLength:(NSUInteger)n];
      if(readAssetImpl(id,0,data.mutableBytes,(uint32_t)n)!=(int64_t)n||!ZemaBroadcastPatch(data.mutableBytes,data.length)){pg_log("Engine LAN gameconfig overlay refused; asset retained.");return 0;}zemaConfig=data;}
    if(offset<zemaConfig.length)memcpy(destination,(const uint8_t*)zemaConfig.bytes+offset,(size_t)MIN((uint64_t)count,zemaConfig.length-offset));
  }return 1;
}
'''
    text=once(text,marker,overlay+marker)
    return once(text,'  envTestMetaOverlay(id,offset,destination,result);','  envTestMetaOverlay(id,offset,destination,result);\n  if(!zemaGameconfigOverlay(id,offset,destination,result))return -1;')

def clone(source,target):
    if source.is_symlink() or target.exists():raise ValueError('Clone requires regular existing input and new output')
    subprocess.run(['/bin/cp','-cRp',str(source),str(target)],check=True)

def verify_ui(folder):
    if set(p.name for p in folder.iterdir())!=set(UI_FILES):raise ValueError('Compiled UI cache entries differ')
    for name,(size,sha) in UI_FILES.items():
        file=folder/name
        if file.stat().st_size!=size or digest_file(file)!=sha:raise ValueError('Compiled UI cache differs: '+name)


def add_ui(spec):
    target=spec['targets']['PlayGTA5Native']
    target['sources'].append({'path':'GeneratedUIAssets','buildPhase':'resources'})
    props=target['info']['properties']
    props.update(icon_properties())


def configure_identity(spec):
    props=spec['targets']['PlayGTA5Native']['info']['properties']
    props.update(CFBundleDisplayName='ZGTA V',CFBundleVersion='88',NSBonjourServices=['_zgtav._tcp'],NSLocalNetworkUsageDescription='Host or join ZGTA V multiplayer on your local network, and access your optional game-file server.')
    return spec


def stage(cached,output,engine):
    for path,text in generate_vehicle_catalog.outputs().items():
        if path.read_text()!=text:raise ValueError('Shared vehicle catalog differs: '+str(path))
    cached=cached.absolute();output=output.absolute()
    if output.parent!=APP.absolute()/'Build' or output.exists() or any(p.is_symlink() for p in (output,*output.parents)):raise ValueError('New isolated Build child required')
    contract=json.loads(gate.CONTRACT.read_text());inspection=gate.inspect(engine.read_bytes(),contract);inspection['generated_c']=gate.inspect_generated(cached/'Generated',inspection['hooks'])
    verify_staged(cached/'Tools',load_manifest()['files']);verify_pair(cached/'GeneratedResources')
    verify_ui(cached/'GeneratedUIAssets')
    output.mkdir(mode=0o700);app=output/'AppRoot';app.mkdir()
    for folder in ['Source','App','Resources','Scripts','IntelInputs']:
        clone(cached/folder,app/folder);shutil.copytree(APP/folder,app/folder,dirs_exist_ok=True)
    for folder in ['Tools','Vendor','Generated','GeneratedResources','GeneratedUIAssets']:clone(cached/folder,app/folder)
    (app/'Build/Online').mkdir(parents=True)
    clone(cached/'Build/Online/libmugoat_online.a',app/'Build/Online/libmugoat_online.a')
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (app/'Generated').glob('game_*.c')}
    groups={}
    for row in inspection['generated_c']['definitions']:groups.setdefault(row['part'],[]).append(row['field'])
    for name,fields in groups.items():
        p=app/'Generated'/name;p.write_bytes(adapter.patch_part(p.read_bytes(),[h for h in inspection['hooks'] if h['field'] in fields],before[name]))
    header,source=adapter.render(inspection['hooks']);(app/'Generated/ZemaEngineLAN.h').write_text(header);(app/'Generated/ZemaEngineLAN.c').write_text(source)
    types,_,names=gate.module_abi(engine.read_bytes())
    if names.get('emscripten_builtin_malloc')!=[91000] or names.get('emscripten_builtin_free')!=[91002]:raise ValueError('Allocator source moved')
    h,c,plan=social_tables.native(types);(app/'Generated/ZemaSocial.h').write_text(h);(app/'Generated/ZemaSocial.c').write_text(c)
    p=app/'Generated/game_0.c';text=p.read_text();text=once(text,'wasm_rt_allocate_funcref_table(&instance->w2c_0x5F_indirect_function_table, 89368, 89368);',f'wasm_rt_allocate_funcref_table(&instance->w2c_0x5F_indirect_function_table, 89368, {89368+plan["count"]});')
    line='  funcref_table_init(&instance->w2c_0x5F_indirect_function_table, elem_segment_exprs_w2c_game_e0, 89367, 1ull, 0, 89367, instance);'
    text=once(text,line,line+'\n  if(!ZemaSocialInstall(instance))wasm_rt_trap(WASM_RT_TRAP_CALL_INDIRECT);');p.write_text(text)
    p=app/'Generated/game-impl.h';text=p.read_text();text=once(text,'#include "game.h"','#include "game.h"\n#include "ZemaSocial.h"');old='#define CALL_INDIRECT(table, t, ft, x, ...) \\\n  (CHECK_CALL_INDIRECT(table, ft, x),       \\\n   DO_CALL_INDIRECT(table, t, x, __VA_ARGS__))'
    text=once(text,old,'#define CALL_INDIRECT(table, t, ft, x, ...) \\\n  (CHECK_CALL_INDIRECT(table, ft, ZemaSocialResolve(&(table),ft,x)), \\\n   DO_CALL_INDIRECT(table, t, ZemaSocialResolve(&(table),ft,x), __VA_ARGS__))');p.write_text(text)
    bank_parts,bank_helpers,bank_receipt=native_script_bank.transform_generated(engine.read_bytes(),app/'Generated')
    for name,data in {**bank_parts,**bank_helpers}.items():(app/'Generated'/name).write_bytes(data)
    (app/'Generated/native-script-bank-plan.json').write_text(json.dumps(bank_receipt,indent=2)+'\n')
    # Record the composed part in the gamer-tag receipt; its verifier preserves this observer.
    prepare_blip_sprites.prepare(app/'Generated')
    tag_receipt=gamer_tags.stage(engine.read_bytes(),app/'Generated')
    for label_path,label_text in generate_text_labels.outputs().items():
        if label_path.read_text()!=label_text:raise ValueError('Shared label table differs: '+str(label_path))
    prepare_text_fallback.prepare(app/'Generated')
    import engine_safety
    safety_receipt=engine_safety.stage_native(app/'Generated')
    import resource_reclaim
    resource_reclaim.stage(app/'Generated',engine.read_bytes())
    import open_rpf
    open_rpf_receipt=open_rpf.stage_native(app/'Generated')
    p=app/'Generated/MugoatCommands.c';p.write_text(world_commands.patch(p.read_text(),engine.read_bytes(),app/'Generated'))
    p=app/'Source/EngineHost.c';p.write_text(engine_patch(p.read_text()))
    p=app/'Source/NativeAssets.m';p.write_text(asset_patch(p.read_text()))
    for p in (app/'App').glob('*.swift'):
        p.write_text(controller_patch(p.read_text()) if p.name=='NativePortViewController.swift' else app_patch(p.name,p.read_text()))
    # New native imports must replace their old fail-fast generated stubs.
    # Regenerate only in this new stage, never in the cached source build.
    subprocess.run([sys.executable,'-B',str(app/'Scripts/generate_imports.py')],cwd=app,check=True)
    if 'env.__syscall_poll\timplemented\n' not in (app/'Build/import-status.tsv').read_text():
        raise ValueError('Native poll import was not implemented in the stage')
    (app/'EngineLAN').mkdir()
    for p in ROOT.iterdir():
        if p.suffix in ('.h','.swift') or p.name in ['EngineLanHost.c','OnlineBindings.c','OnlineCallbacks.c','ExperimentalHost.c','EngineLanMode.c','BroadcastOverlay.c','module.modulemap']:shutil.copy2(p,app/'EngineLAN'/p.name)
    (app/'Source/Native-Bridging-Header.h').open('a').write('\n#include "ZemaExperimental.h"\n')
    yaml=subprocess.check_output(['/usr/bin/ruby','-rjson','-ryaml','-e','puts JSON.generate(YAML.load_file(ARGV[0]))',str(APP/'project.yml')],text=True);spec=json.loads(yaml)
    settings=spec['settings']['base'];settings['HEADER_SEARCH_PATHS']+=['$(SRCROOT)/EngineLAN'];settings['SWIFT_INCLUDE_PATHS']=['$(SRCROOT)/EngineLAN']
    add_ui(spec)
    target=spec['targets']['PlayGTA5Native'];target['sources'].append('EngineLAN')
    for entry in target['sources']:
        if isinstance(entry,dict) and entry.get('path') in ['App','Resources']:entry['excludes']=entry.get('excludes',[])+['Assets.xcassets','*.xcassets','**/*.xcassets']
    target['settings']['base']['PRODUCT_BUNDLE_IDENTIFIER']='com.zemabinks.gtamp.enginelanlab'
    configure_identity(spec)
    # Cached UI catalog is copied unchanged, never regenerated on this Intel Mac.
    specfile=app/'project.experimental.json';specfile.write_text(json.dumps(spec,indent=2)+'\n')
    subprocess.run(['/usr/local/bin/xcodegen','generate','--spec',str(specfile)],cwd=app,check=True)
    receipt={'format':'zema-experimental-stage-v1','app_root':str(app),'original_c_sha256':before,'social_table_entries':plan['count'],'hooks':len(contract['hooks']),'bundle_id':'com.zemabinks.gtamp.enginelanlab','original_source_build_untouched':True,'shaders':'PINNED_INTEL_PAIR_REUSED','runtime_verified':False}
    receipt['native_script_bank']=bank_receipt
    receipt['gamer_tags']=tag_receipt
    receipt['engine_safety']=safety_receipt
    receipt['open_rpf']=open_rpf_receipt
    (output/'stage.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cached-app',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--engine',type=Path,required=True);a=p.parse_args();print(json.dumps(stage(a.cached_app,a.output,a.engine),indent=2))
