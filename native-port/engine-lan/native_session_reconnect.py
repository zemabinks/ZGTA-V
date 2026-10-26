"""Promote reviewed Settings reconnect navigation into the normal candidate pipeline.

Only the canonical menu opener and acknowledged input edges are used. The flow
stops at GTA's Find New Session handoff: Public and confirmation remain manual.
The internal compile gate is retained for deterministic disabled-path fixtures.
"""
from pathlib import Path
import hashlib
PATCHES = {'engine': [('#include "ZemaExperimental.h"\n\n',
             '#include "ZemaExperimental.h"\n'
             '#if defined(ZGTA_NATIVE_RECOVERY_QA) && ZGTA_NATIVE_RECOVERY_QA\n'
             '#include "ZemaNativeRecoveryQAEngine.h"\n'
             '#endif\n'
             '\n'),
            ('  if (pad == 12840656) {\n    pg_next_aircraft_weapon(instance);\n',
             '  if (pad == 12840656) {\n'
             '#if defined(ZGTA_NATIVE_RECOVERY_QA) && ZGTA_NATIVE_RECOVERY_QA\n'
             '    ZemaNativeRecoveryQAPrimary(instance, pad);\n'
             '#endif\n'
             '    pg_next_aircraft_weapon(instance);\n'),
            ('    pg_log(message);\n    return NULL;\n',
             '    pg_log(message);\n'
             '#if defined(ZGTA_NATIVE_RECOVERY_QA) && ZGTA_NATIVE_RECOVERY_QA\n'
             '    ZemaNativeRecoveryQAEngineMainEnded(&env.game);\n'
             '#endif\n'
             '    return NULL;\n'),
            ('  if(ZemaLabEnabled()&&!ZemaLabAttach(&env.game)){pg_log("Engine LAN startup refused: typed '
             'host unavailable.");return NULL;}\n'
             '  uint32_t actual = w2c_game_htons(&env.game, 0x1234);\n',
             '  if(ZemaLabEnabled()&&!ZemaLabAttach(&env.game)){pg_log("Engine LAN startup refused: typed '
             'host unavailable.");return NULL;}\n'
             '#if defined(ZGTA_NATIVE_RECOVERY_QA) && ZGTA_NATIVE_RECOVERY_QA\n'
             '  if(ZemaLabEnabled()&&!ZemaNativeRecoveryQABindEngineMainThread(&env.game)){pg_log("Recovery '
             'QA refused: engine-main binding changed.");return NULL;}\n'
             '#endif\n'
             '  uint32_t actual = w2c_game_htons(&env.game, 0x1234);\n'),
            ('  uint32_t result=w2c_game_0x5F_main_argc_argv(&env.game,argc,argv);\n'
             '  snprintf(message, sizeof(message), "Game entry point returned %u", result);\n',
             '  uint32_t result=w2c_game_0x5F_main_argc_argv(&env.game,argc,argv);\n'
             '#if defined(ZGTA_NATIVE_RECOVERY_QA) && ZGTA_NATIVE_RECOVERY_QA\n'
             '  ZemaNativeRecoveryQAEngineMainEnded(&env.game);\n'
             '#endif\n'
             '  snprintf(message, sizeof(message), "Game entry point returned %u", result);\n')],
 'controller': [('        })\n'
                 '        controller.gameModeChanged = { [weak self] in '
                 'self?.launchChoice.offlineModeChanged(); self?.refreshModeChoice() }\n',
                 '        })\n'
                 '#if ZGTA_NATIVE_RECOVERY_QA\n'
                 '        if engineStarted, ZemaLabEnabled() != 0 {\n'
                 '            controller.navigationItem.prompt = '
                 'SettingsReconnectIntent.shared.statusText()\n'
                 '            let reconnect = UIBarButtonItem(title: "Reconnect", image: UIImage(systemName: '
                 '"arrow.clockwise"), primaryAction: UIAction { [weak self] _ in\n'
                 '                guard let self, self.engineStarted, !self.engineFailed, self.worldReadyAt '
                 '!= nil else { return }\n'
                 '                ZemaEngineLANUI.shared.reconnectFromSettings(from: self) { [weak self] '
                 'message in\n'
                 '                    guard let self else { return }\n'
                 '                    if let navigation = self.presentedViewController as? '
                 'UINavigationController {\n'
                 '                        navigation.topViewController?.navigationItem.prompt = message\n'
                 '                    } else if self.presentedViewController == nil { '
                 'self.showCheatToast(message) }\n'
                 '                }\n'
                 '            })\n'
                 '            reconnect.isEnabled = !engineFailed && worldReadyAt != nil\n'
                 '            controller.navigationItem.rightBarButtonItem = reconnect\n'
                 '        }\n'
                 '#endif\n'
                 '        controller.gameModeChanged = { [weak self] in '
                 'self?.launchChoice.offlineModeChanged(); self?.refreshModeChoice() }\n')],
 'generated': [('#include "game-impl.h"\n',
                '#include "game-impl.h"\n'
                '#if defined(ZGTA_NATIVE_RECOVERY_QA) && ZGTA_NATIVE_RECOVERY_QA\n'
                '#include "ZemaNativeRecoveryQAEngine.h"\n'
                '#endif\n'),
               ('void w2c_game_f37308(w2c_game* instance, u32 var_p0, u64 var_p1, u64 var_p2, u32 var_p3) {',
                '#if defined(ZGTA_NATIVE_RECOVERY_QA) && ZGTA_NATIVE_RECOVERY_QA\n'
                '#define w2c_game_f37308 ZemaNativeRecoveryQAOriginal_f37308\n'
                '#endif\n'
                'void w2c_game_f37308(w2c_game* instance, u32 var_p0, u64 var_p1, u64 var_p2, u32 var_p3) {'),
               ('\n}\n\nu32 w2c_game_f37309(',
                '\n'
                '}\n'
                '#if defined(ZGTA_NATIVE_RECOVERY_QA) && ZGTA_NATIVE_RECOVERY_QA\n'
                '#undef w2c_game_f37308\n'
                'void w2c_game_f37308(w2c_game* instance, u32 var_p0, u64 var_p1, u64 var_p2, u32 var_p3) {\n'
                '  ZemaNativeRecoveryQAFrontend(instance,var_p0,var_p1,var_p2,var_p3);\n'
                '}\n'
                '#endif\n'
                '\n'
                'u32 w2c_game_f37309(')]}
ORIGINAL_GENERATED_SHA256 = "926e66347404fe425fef4f4db9d7ca19b563fdde9ce9c6e57ba5bb3c5166a8d0"
C_FILES = ["RecoveryCore.c", "RecoveryObserver.c", "ReconnectPlan.c", "ZemaNativeRecoveryQA.c"]
FLAG = "-DZGTA_NATIVE_RECOVERY_QA=1"
def patch(kind,text,undo=False):
    if kind=="generated" and not undo and hashlib.sha256(text.encode()).hexdigest()!=ORIGINAL_GENERATED_SHA256:
        raise ValueError("Reconnect generated21 baseline changed")
    for before,after in reversed(PATCHES[kind]) if undo else PATCHES[kind]:
        if undo:before,after=after,before
        if text.count(before)!=1:raise ValueError("Reconnect source anchor changed: "+kind)
        text=text.replace(before,after)
    if kind=="generated" and undo and hashlib.sha256(text.encode()).hexdigest()!=ORIGINAL_GENERATED_SHA256:
        raise ValueError("Reconnect original callback changed")
    return text

def stage_generated(generated):
    path=Path(generated)/"game_21.c"
    path.write_text(patch("generated",path.read_text()))

def verify_generated(generated):
    path=Path(generated)/"game_21.c"
    restored=patch("generated",path.read_text(),undo=True)
    if patch("generated",restored)!=path.read_text():raise ValueError("Reconnect callback overlay differs")

def configure(spec):
    target=spec["targets"]["PlayGTA5Native"];sources=target["sources"]
    index=sources.index("Source");sources[index]={"path":"Source","excludes":["EngineHost.c"]}
    sources.append({"path":"Source/EngineHost.c","compilerFlags":FLAG})
    generated=next(x for x in sources if isinstance(x,dict) and x.get("path")=="Generated")
    generated["excludes"].append("game_21.c")
    sources.append({"path":"Generated/game_21.c","compilerFlags":generated["compilerFlags"]+" "+FLAG})
    index=sources.index("EngineLAN");sources[index]={"path":"EngineLAN","excludes":list(C_FILES)}
    for name in C_FILES:sources.append({"path":"EngineLAN/"+name,"compilerFlags":FLAG})
    settings=target["settings"]["base"]
    if "SWIFT_ACTIVE_COMPILATION_CONDITIONS" in settings:raise ValueError("Review existing Swift conditions")
    settings["SWIFT_ACTIVE_COMPILATION_CONDITIONS"]=["$(inherited)","ZGTA_NATIVE_RECOVERY_QA"]
