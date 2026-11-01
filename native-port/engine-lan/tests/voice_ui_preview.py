"""Stage real production touch controls in a simulator-only, engine-free app."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import prepare_experimental as prepare

def stage(output):
    output.mkdir(parents=True,exist_ok=False)
    for n in ['VirtualPad.swift','TouchControlsView.swift','ControlsLayout.swift','ControlAppearance.swift','DragCamera.swift','GameSettings.swift','GraphicsOptions.swift','LowMemoryGraphics.swift','GyroInput.swift','Localization.swift','Theme.swift']:
        text=(prepare.APP/'App'/n).read_text()
        (output/n).write_text(prepare.app_patch(n,text))
    for n in ['EngineVoice.swift','EngineLanFeaturePolicy.swift','ZemaVoice.c','ZemaVoice.h']:
        shutil.copy2(ROOT/n,output/n)
    for n in ['EngineHost.h','MugoatOnline.h']:
        shutil.copy2(prepare.APP/'Source'/n,output/n)
    shutil.copytree(prepare.APP/'Resources/ControlIcons',output/'ControlIcons')
    shutil.copy2(prepare.APP/'Resources/Localizations.json',output/'Localizations.json')
    shutil.copy2(ROOT/'module.modulemap',output/'module.modulemap')
    for n in ['ZemaLanBackend.h','ZemaProfile.h']:shutil.copy2(ROOT/n,output/n)
    (output/'bridge.h').write_text('#include "EngineHost.h"\n#include "MugoatOnline.h"\n#include "ZemaVoice.h"\nvoid PGSetMemoryProfile(int32_t);\nvoid PGSetPresentPacing(double);\nint ZemaLabEnabled(void);\nint ZemaGameIsOnline(void);\n')
    (output/'Stubs.c').write_text('''#include "bridge.h"
int ZemaLabEnabled(void){return 1;}int ZemaGameIsOnline(void){return 1;}
bool MugoatOnlineEnabled(void){return false;}bool MugoatVoiceIsMicEnabled(void){return false;}bool MugoatVoiceIsSpeakerEnabled(void){return true;}
void MugoatVoiceSetMicEnabled(bool v){}void MugoatVoiceSetSpeakerEnabled(bool v){}void MugoatVoiceSubmitMicAudio(const float*p,uint32_t n){}void MugoatTriggerAmmuBuy(void){}
uint32_t PGCurrentTouchContext(void){return 0;}uint32_t PGGameStatus(void){return 0;}PGControlHints PGReadControlHints(uint32_t c){return (PGControlHints){0};}
void PGNextAircraftWeapon(void){}void PGMouseWheel(int32_t v){}void PGSetMousePosition(int32_t x,int32_t y,int32_t b){}void PGGetRenderSize(int32_t*w,int32_t*h){*w=1280;*h=720;}
void PGSetRadioWheelDirection(float x,float y,bool active){}void PGTouchCameraDrag(double x,double y){}void PGTouchCameraEnabled(bool v){}
void PGSetEngineMemoryMB(int32_t v){}void PGSetMemoryProfile(int32_t v){}void PGSetPresentPacing(double v){}
void PGConfigureEngine(const char*const*q,unsigned n,int w,int h,int limit){}
''')
    (output/'Preview.swift').write_text('''import UIKit
@main final class Preview: UIResponder, UIApplicationDelegate {
 var window: UIWindow?
 func application(_ application: UIApplication, didFinishLaunchingWithOptions options:[UIApplication.LaunchOptionsKey:Any]?) -> Bool {
  ZemaVoiceConfigure(0x0a4d0001);ZemaVoiceConnected(true)
  ZemaVoiceSetMicEnabled(ProcessInfo.processInfo.arguments.contains("--mic-on"))
  ZemaVoiceSetSpeakerEnabled(!ProcessInfo.processInfo.arguments.contains("--speaker-off"))
  let w=UIWindow(frame:UIScreen.main.bounds);w.rootViewController=PreviewController();w.makeKeyAndVisible();window=w;return true
 }
}
final class PreviewController:UIViewController {
 override var supportedInterfaceOrientations:UIInterfaceOrientationMask{.landscape}
 override var prefersStatusBarHidden:Bool{true}
 override func viewDidLoad(){super.viewDidLoad();view.backgroundColor=UIColor(red:0.16,green:0.23,blue:0.29,alpha:1)
  let controls=TouchControlsView();controls.frame=view.bounds;controls.autoresizingMask=[.flexibleWidth,.flexibleHeight];view.addSubview(controls);controls.updateVisibility();controls.updateContext(vehicle:0,pauseMenu:false)
  controls.onVoiceMicChanged={_ in controls.updateVisibility()}
 }
 override func viewDidAppear(_ animated:Bool){super.viewDidAppear(animated);DispatchQueue.main.asyncAfter(deadline:.now()+2){self.capture()}}
 private func capture(){view.layoutIfNeeded();var rows:[[String:Any]]=[]
  func visit(_ v:UIView){if let c=v as? ControlButton,["speaker","mic"].contains(c.name){let r=c.convert(c.bounds,to:view);rows.append(["name":c.name,"label":c.accessibilityLabel ?? "","value":c.accessibilityValue ?? "","x":r.minX,"y":r.minY,"width":r.width,"height":r.height,"visible":c.alpha>0.01])};v.subviews.forEach(visit)}
  visit(view);let docs=FileManager.default.urls(for:.documentDirectory,in:.userDomainMask)[0]
  let image=UIGraphicsImageRenderer(bounds:view.bounds).image{_ in view.drawHierarchy(in:view.bounds,afterScreenUpdates:true)}
  try! image.pngData()!.write(to:docs.appendingPathComponent("voice.png"))
  try! JSONSerialization.data(withJSONObject:["fixture":true,"gameplay":false,"width":view.bounds.width,"height":view.bounds.height,"controls":rows],options:[.prettyPrinted,.sortedKeys]).write(to:docs.appendingPathComponent("voice.json"))
 }
}
''')
    spec={'name':'VoicePreview108','options':{'deploymentTarget':{'iOS':'15.0'}},'targets':{'VoicePreview108':{'type':'application','platform':'iOS','sources':[{'path':p.name} for p in sorted(output.iterdir()) if p.suffix in ('.swift','.c')]+[{'path':'ControlIcons','buildPhase':'resources'},{'path':'Localizations.json','buildPhase':'resources'}],'settings':{'base':{'PRODUCT_BUNDLE_IDENTIFIER':'com.zema.zgta.voicepreview108','SWIFT_VERSION':'5.0','SWIFT_OBJC_BRIDGING_HEADER':'bridge.h','SWIFT_INCLUDE_PATHS':['$(SRCROOT)'],'HEADER_SEARCH_PATHS':['$(SRCROOT)'],'CODE_SIGNING_ALLOWED':'NO','TARGETED_DEVICE_FAMILY':'1,2'}},'info':{'path':'Info.plist','properties':{'CFBundleDisplayName':'ZGTA Voice UI QA','CFBundleVersion':'108','UILaunchScreen':{},'UIRequiresFullScreen':True,'UIStatusBarHidden':True,'UISupportedInterfaceOrientations':['UIInterfaceOrientationLandscapeLeft','UIInterfaceOrientationLandscapeRight']}}}}}
    (output/'project.json').write_text(json.dumps(spec,indent=2)+'\n')
    subprocess.run(['xcodegen','generate','--spec','project.json'],cwd=output,check=True)

if __name__=='__main__':stage(Path(sys.argv[1]).absolute())
