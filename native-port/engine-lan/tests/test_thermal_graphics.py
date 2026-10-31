"""Exercise the actual staged resize/thermal methods without running a game."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT.parent/'app'
sys.path.insert(0,str(ROOT))
import prepare_experimental as prepare

class ThermalGraphics(unittest.TestCase):
    def test_actual_controller_thermal_and_manual_resize_paths(self):
        text=prepare.controller_patch((APP/'App/NativePortViewController.swift').read_text())
        methods=text[text.index('    @objc private func thermalStateChanged()'):text.index('    private func samplePerformanceConditions(')]
        fixture=r'''
import Foundation
import CoreGraphics
enum ProcessInfo {
 enum State:Int {case nominal=0,fair,serious,critical}
 struct Info {var thermalState:State = .nominal}
 static var processInfo=Info()
}
enum DispatchQueue {static let main=Queue();struct Queue {func async(execute:()->Void){execute()}}}
struct Preset {var height=540}
struct GameSettings {static var shared=GameSettings();var renderHeight=0;var matchScreenShape=false}
enum GraphicsConfiguration {static func size(for preset:Preset,renderHeight:Int,screen:CGSize,matchScreenShape:Bool)->(Int,Int){let h=renderHeight>0 ? renderHeight:preset.height;return(h*2,h)}}
var clock=0.0
func CACurrentMediaTime()->Double {clock}
var lan:Int32=1
var resizes:[(Int32,Int32)]=[]
var limits:[Int32]=[]
func ZemaLabEnabled()->Int32 {lan}
func PGSetBackBufferSize(_ w:Int32,_ h:Int32){resizes.append((w,h))}
func PGSetFrameLimit(_ n:Int32){limits.append(n)}
func PGSetPresentPacing(_ t:Double){}
final class Fixture:NSObject {
 var engineStarted=true,engineFailed=false
 var worldReadyAt:Double?=1
 var requestedRenderSize:(width:Int,height:Int)?
 var requestedFrameInterval:Int32=1
 var thermalScale=1.0
 var lanThermalGraphics=EngineLanThermalGraphics()
 var bootedPreset=Preset()
 struct View {var bounds=CGRect(x:0,y:0,width:1170,height:540)}
 var view=View()
 var messages:[String]=[]
 func appendLog(_ s:String){messages.append(s)}
 func showCheatToast(_ s:String){messages.append(s)}
 func notify(){thermalStateChanged()}
 func tick(){updateThermalGraphics()}
 func resize(){applyLiveResolution()}
'''+methods+r'''
}
let fixture=Fixture()
for cap in [0,30,60] {
 fixture.lanThermalGraphics.begin(frameRateCap:cap);limits=[];resizes=[]
 fixture.worldReadyAt=nil;ProcessInfo.processInfo.thermalState = .serious;fixture.notify();assert(limits.isEmpty&&resizes.isEmpty)
 fixture.worldReadyAt=1;fixture.tick();assert(limits==[2]&&resizes.isEmpty)
 fixture.tick();fixture.notify();assert(limits==[2])
 ProcessInfo.processInfo.thermalState = .critical;fixture.notify();assert(limits.last==3&&resizes.isEmpty)
 ProcessInfo.processInfo.thermalState = .fair;fixture.notify();assert(limits.last==3)
 for _ in 0..<29 {clock += 1;fixture.tick();assert(limits.last==3)}
 clock += 1;fixture.tick();let expected:Int32=cap==0 ? 0:cap==30 ? 2:1;assert(limits.last==expected && fixture.requestedFrameInterval==expected)
 GameSettings.shared.renderHeight=720;fixture.resize();assert(resizes.isEmpty&&GameSettings.shared.renderHeight==720)
 fixture.engineFailed=true;ProcessInfo.processInfo.thermalState = .serious;let before=limits.count;fixture.notify();fixture.tick();assert(limits.count==before);fixture.engineFailed=false
}
// A short fair-state dip must not restore 60 FPS; heat returns immediately.
var policy=EngineLanThermalGraphics();policy.begin(frameRateCap:60)
assert(policy.nextLimit(thermalState:2,ready:true,now:0)==2)
for n in 1...20 {assert(policy.nextLimit(thermalState:1,ready:true,now:Double(n))==nil)}
assert(policy.nextLimit(thermalState:2,ready:true,now:21)==nil)
for n in 22...50 {assert(policy.nextLimit(thermalState:1,ready:true,now:Double(n))==nil)}
// Time in background is not observed cooling.
assert(policy.nextLimit(thermalState:1,ready:true,now:100)==nil)
for n in 101...129 {assert(policy.nextLimit(thermalState:0,ready:true,now:Double(n))==nil)}
assert(policy.nextLimit(thermalState:0,ready:true,now:130)==1)
assert(policy.nextLimit(thermalState:3,ready:true,now:130.1)==3)
assert(policy.nextLimit(thermalState:0,ready:true,now:Double.nan)==nil)
assert(policy.nextLimit(thermalState:0,ready:false,now:160)==nil)
assert(policy.nextLimit(thermalState:0,ready:true,now:161)==nil)
// Offline retains safe live resizing and now uses the same temporary thermal FPS policy.
lan=0;limits=[];resizes=[];fixture.lanThermalGraphics.begin(frameRateCap:60);fixture.thermalScale=1;ProcessInfo.processInfo.thermalState = .serious;fixture.notify();assert(resizes.count==1&&resizes[0].1==576&&limits==[2])
print("LAN_THERMAL_FPS_AND_DEFERRED_RESIZE_PASS")
'''
        with tempfile.TemporaryDirectory(prefix='zema-thermal-controller-') as d:
            path=Path(d);(path/'main.swift').write_text(fixture)
            built=subprocess.run(['/usr/bin/swiftc','-warnings-as-errors','-module-cache-path',str(path/'cache'),str(ROOT/'EngineLanThermalGraphics.swift'),str(path/'main.swift'),'-o',str(path/'fixture')],capture_output=True,text=True)
            self.assertEqual(built.returncode,0,built.stderr)
            ran=subprocess.run([str(path/'fixture')],capture_output=True,text=True,timeout=10)
            self.assertEqual(ran.returncode,0,ran.stderr)

    def test_actual_native_back_buffer_api_refuses_lan_live_reset(self):
        text=prepare.engine_patch((APP/'Source/EngineHost.c').read_text())
        body=text[text.index('void PGSetBackBufferSize('):text.index('static void pg_crash_signal_handler')]
        fixture=r'''
#include <stdint.h>
#include <stdatomic.h>
#include <assert.h>
typedef uint64_t u64;
static _Atomic uint64_t inputBlock=1;
static int enabled=1,env;
static uint8_t memory[444];
static int ZemaLabEnabled(void){return enabled;}
static void pg_log(const char* s){}
static uint8_t* pg_pointer(int* e,uint64_t p,uint64_t n){return memory;}
'''+body+r'''
int main(){PGSetBackBufferSize(936,432);if(*(int32_t*)(memory+432)!=0)return 3;
 enabled=0;PGSetBackBufferSize(961,541);assert(*(int32_t*)(memory+432)==960&&*(int32_t*)(memory+436)==540);
 enabled=1;PGSetBackBufferSize(936,432);assert(*(int32_t*)(memory+432)==960);
}
'''
        with tempfile.TemporaryDirectory(prefix='zema-thermal-api-') as d:
            path=Path(d);(path/'fixture.c').write_text(fixture)
            result=subprocess.run(['/usr/bin/clang','-std=c11',str(path/'fixture.c'),'-o',str(path/'fixture')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            subprocess.run([str(path/'fixture')],check=True,capture_output=True,text=True,timeout=10)

    def test_settings_explain_resolution_is_deferred_in_lan(self):
        text=prepare.app_patch('SettingsViewController.swift',(APP/'App/SettingsViewController.swift').read_text())
        self.assertIn('Engine LAN resolution changes apply after restarting the app.',text)
        self.assertIn('engineRunning && ZemaLabEnabled() != 0 ? " · applies after restart"',text)
        self.assertIn('updateThermalGraphics()\n        let now = CACurrentMediaTime()',prepare.controller_patch((APP/'App/NativePortViewController.swift').read_text()))

if __name__=='__main__':unittest.main()
