from pathlib import Path
import subprocess,tempfile,unittest,sys
ROOT=Path(__file__).resolve().parents[1];APP=ROOT.parent/'app'
sys.path.insert(0,str(ROOT))
import prepare_experimental as prepare

class ThermalMemory99(unittest.TestCase):
 def run_fixture(self,source,*,swift=False,extra=()):
  with tempfile.TemporaryDirectory(prefix='zgta-thermal99-') as tmp:
   p=Path(tmp);src=p/('main.swift' if swift else 'main.cpp');src.write_text(source)
   command=(['/usr/bin/swiftc','-warnings-as-errors','-module-cache-path',str(p/'cache')] if swift else ['clang++','-std=c++17','-fsanitize=address,undefined','-fno-omit-frame-pointer'])
   result=subprocess.run(command+list(map(str,extra))+[str(src),'-I',str(APP/'Source'),'-I',str(APP/'Source/MetalRenderer'),'-o',str(p/'fixture')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   result=subprocess.run([str(p/'fixture')],capture_output=True,text=True,timeout=30)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_hot_start_actual_graphics_configuration(self):
  source=(APP/'App/GraphicsOptions.swift').read_text().split('enum GraphicsConfiguration {',1)[1]
  fixture=r'''
import Foundation
import CoreGraphics
struct Screen {var nativeBounds=CGRect(x:0,y:0,width:1170,height:540);var maximumFramesPerSecond=60}
enum UIScreen {static var main=Screen()}
struct GraphicsPreset {static let battery=GraphicsPreset(height:432);var height=540;var engineOptions:[String]=[];var title="Performance"}
struct GameSettings {var memoryProfile=MemoryProfile.automatic;var engineMemoryMB=0;var graphicsPreset=GraphicsPreset();var renderHeight=720;var matchScreenShape=false;var frameRateCap=60;static func frameRateTitle(_ cap:Int)->String{"\(cap) FPS"}}
var requested:(Int32,Int32,Int32)=(0,0,0);var pacing=0.0
func PGSetMemoryProfile(_ n:Int32){}
func PGSetEngineMemoryMB(_ n:Int32){}
func PGConfigureEngine(_ options:UnsafePointer<UnsafePointer<CChar>?>,_ count:UInt32,_ w:Int32,_ h:Int32,_ limit:Int32){requested=(w,h,limit)}
func PGSetPresentPacing(_ seconds:Double){pacing=seconds}
enum GraphicsConfiguration {
'''+source+r'''
let settings=GameSettings()
for cap in [0,30,60] {
 for heat in 0...3 {
  let interval=EngineLanThermalGraphics.startupLimit(frameRateCap:cap,thermalState:heat)
  assert(interval == (heat==3 ? 3:heat==2 ? 2:cap==0 ? 0:cap==30 ? 2:1))
 }
}
_ = GraphicsConfiguration.apply(settings,screen:CGSize(width:1170,height:540),renderScale:EngineLanThermalGraphics.startupScale(thermalState:2),frameIntervalOverride:2)
assert(requested.1==576&&requested.2==2&&pacing==1.0/30)
_ = GraphicsConfiguration.apply(settings,screen:CGSize(width:1170,height:540),renderScale:EngineLanThermalGraphics.startupScale(thermalState:3),frameIntervalOverride:3)
assert(requested.1==468&&requested.2==3&&pacing==1.0/20)
assert(settings.renderHeight==720&&settings.frameRateCap==60)
_ = GraphicsConfiguration.apply(settings,screen:CGSize(width:1170,height:540))
assert(requested.1==720&&requested.2==1&&pacing==0)
var policy=EngineLanThermalGraphics();policy.begin(frameRateCap:60,initialLimit:2)
for second in 0..<30 {assert(policy.nextLimit(thermalState:1,ready:true,now:Double(second))==nil)}
assert(policy.nextLimit(thermalState:1,ready:true,now:30)==1)
policy.begin(frameRateCap:60,initialLimit:3)
assert(policy.nextLimit(thermalState:2,ready:true,now:0)==nil)
assert(policy.nextLimit(thermalState:2,ready:true,now:31)==nil) // unseen/background interval
let low=GraphicsPreset(height:432)
assert(GraphicsConfiguration.size(for:low,renderHeight:0,screen:.zero,matchScreenShape:false,renderScale:0.8).1==360)
assert(GraphicsConfiguration.size(for:low,renderHeight:0,screen:.zero,matchScreenShape:false,renderScale:Double.nan).1==432)
'''
  self.run_fixture(fixture,swift=True,extra=[ROOT/'EngineLanThermalGraphics.swift',APP/'App/LowMemoryGraphics.swift'])
  staged=prepare.controller_patch((APP/'App/NativePortViewController.swift').read_text())
  self.assertIn('frameIntervalOverride: requestedFrameInterval',staged)
  self.assertIn('renderScale: thermalScale',staged)
 def test_actual_pressure_cache_trim_is_bounded_and_fence_safe(self):
  text=(APP/'Source/MetalRenderer/MRRenderer.mm').read_text();body=text[text.index('static void trimIdleBufferCaches('):text.index('static void retireStorage(')]
  fixture=r'''
#include "MRBufferPool.h"
#include "MRBufferArena.h"
#include <atomic>
#include <cassert>
#include <memory>
#define TARGET_OS_SIMULATOR 0
using Resource=std::shared_ptr<unsigned>;
static PGSharedBufferPool<Resource> sharedBufferPool;
static PGBufferArena<Resource> bufferArena;
struct Renderer {std::atomic<uint64_t> completed{1};};
static Renderer renderer;static Renderer* R=&renderer;
static std::atomic<bool> memoryTrimRequested{false};
static double lastMemoryCheck=0,warningHoldUntil=0;
static bool bufferCachePressure=false;static uint64_t bufferCacheTrimmedBytes=0;
static uint64_t headroom=100ull<<20;static unsigned queries=0;
static int reduced=0;
int PGIsLowMemoryDevice(){return reduced;}
uint64_t os_proc_available_memory(){++queries;return headroom;}
'''+body+r'''
int main(){
 sharedBufferPool.retire(std::make_shared<unsigned>(1),16ull<<20,2);
 sharedBufferPool.retire(std::make_shared<unsigned>(2),16ull<<20,1);
 trimIdleBufferCaches(1001);assert(bufferCachePressure&&bufferCacheTrimmedBytes==(16ull<<20)&&sharedBufferPool.bytes()==(16ull<<20));
 trimIdleBufferCaches(1002);assert(queries==1);
 R->completed.store(2);trimIdleBufferCaches(2002);assert(bufferCacheTrimmedBytes==(32ull<<20));
 headroom=512ull<<20;trimIdleBufferCaches(3003);assert(!bufferCachePressure);
 memoryTrimRequested.store(true);trimIdleBufferCaches(3004);assert(bufferCachePressure);
 trimIdleBufferCaches(32000);assert(bufferCachePressure);
 trimIdleBufferCaches(34005);assert(!bufferCachePressure);
 // Standard path remains inactive at 600 MiB. Reduced mode trims before the
 // streamer reaches its 512 MiB eviction reserve, and keeps in-flight data.
 sharedBufferPool.retire(std::make_shared<unsigned>(3),16ull<<20,3);
 sharedBufferPool.retire(std::make_shared<unsigned>(4),16ull<<20,2);
 headroom=600ull<<20;trimIdleBufferCaches(35006);assert(!bufferCachePressure&&sharedBufferPool.bytes()==(32ull<<20));
 reduced=1;trimIdleBufferCaches(36007);assert(bufferCachePressure&&sharedBufferPool.bytes()==(16ull<<20));
 R->completed.store(3);trimIdleBufferCaches(37008);assert(!sharedBufferPool.bytes());
 headroom=700ull<<20;trimIdleBufferCaches(38009);assert(bufferCachePressure);
 headroom=(768ull<<20)+1;trimIdleBufferCaches(39010);assert(!bufferCachePressure);
 // An explicit warning still holds cleanup for 30 seconds at ample headroom.
 memoryTrimRequested.store(true);trimIdleBufferCaches(39011);assert(bufferCachePressure);
 trimIdleBufferCaches(68012);assert(bufferCachePressure);
 trimIdleBufferCaches(70013);assert(!bufferCachePressure);
}
'''
  self.run_fixture(fixture)
if __name__=='__main__':unittest.main()
