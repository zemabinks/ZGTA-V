"""Run memory budgets and independent display settings; preserve modern Build99 requests."""
from pathlib import Path
import subprocess,tempfile,unittest,sys
ROOT=Path(__file__).resolve().parents[1];APP=ROOT.parent/'app'
sys.path.insert(0,str(ROOT))
import prepare_experimental as prepare

class LowMemory100(unittest.TestCase):
 def execute(self,source,swift=False,extra=(),cpp=False):
  with tempfile.TemporaryDirectory(prefix='zgta-lowmem100-') as tmp:
   p=Path(tmp);src=p/('main.swift' if swift else 'main.cpp' if cpp else 'main.c');src.write_text(source)
   cmd=(['/usr/bin/swiftc','-warnings-as-errors','-module-cache-path',str(p/'cache')] if swift else ['clang++' if cpp else 'clang','-std=c++17' if cpp else '-std=c11','-fsanitize=address,undefined','-fno-omit-frame-pointer'])
   result=subprocess.run(cmd+list(map(str,extra))+[str(src),'-I',str(APP/'Source'),'-I',str(APP/'Source/MetalRenderer'),'-o',str(p/'fixture')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   result=subprocess.run([str(p/'fixture')],capture_output=True,text=True,timeout=30)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr);return result.stdout

 def test_actual_video_budget_and_higher_memory_identity(self):
  host=(APP/'Source/EngineHost.c').read_text()
  body=host[host.index('int PGGPUReadsBC(void);'):host.index('static u32 nativeEngineCores')]
  self.execute(r'''
#include "NativeLowMemoryPolicy.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
typedef uint64_t u64;
static uint64_t processLimitMB;
static int lowMemoryDevice,bc;
int PGGPUReadsBC(void){return bc;}
void pg_log(const char* s){}
'''+body+r'''
int main(){
 assert(!pg_low_memory_device(0));
 assert(pg_memory_profile(3ull<<30,0));assert(!pg_memory_profile(8ull<<30,0));
 assert(!pg_memory_profile(3ull<<30,1));assert(pg_memory_profile(8ull<<30,2));
 assert(pg_memory_profile(3ull<<30,77));assert(!pg_memory_profile(0,0));assert(pg_low_memory_device(3072ull<<20));
 assert(pg_low_memory_device((3400ull<<20)-1));assert(!pg_low_memory_device(3400ull<<20));
 for(unsigned ram=4096;ram<=16384;ram+=1024)assert(!pg_low_memory_device((uint64_t)ram<<20));
 unsetenv("PG_VIDEO_MEMORY_MB");
 for(processLimitMB=1000;processLimitMB<=16384;processLimitMB+=17){
  for(bc=0;bc<=1;bc++){
   lowMemoryDevice=0;uint64_t textures=processLimitMB>2440?processLimitMB-1800:640;
   uint64_t expected=bc?textures:textures/2;if(expected<640)expected=640;
   const uint64_t reported=4ull<<30;
   assert(pg_video_memory(reported)==((expected<<20)>=reported?reported:expected<<20));
   lowMemoryDevice=1;uint64_t budget=pg_video_memory(reported)>>20;
   assert(budget>0&&budget<640&&budget<=512);
   if(!bc)assert(budget<=256);
  }
 }
 processLimitMB=2048;lowMemoryDevice=1;bc=0;assert(pg_video_memory(4ull<<30)==256ull<<20);
 bc=1;assert(pg_video_memory(4ull<<30)==512ull<<20);
 assert(pg_video_memory(64ull<<20)==64ull<<20); // cannot exceed actual adapter report
 setenv("PG_VIDEO_MEMORY_MB","777",1);assert(pg_video_memory(4ull<<30)==777ull<<20);
}
''')

 def test_low_memory_trim_starts_earlier_without_touching_inflight(self):
  text=(APP/'Source/MetalRenderer/MRRenderer.mm').read_text()
  body=text[text.index('static void trimIdleBufferCaches('):text.index('static void retireStorage(')]
  self.execute(r'''
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
static uint64_t headroom=350ull<<20;static int low=0;
int PGIsLowMemoryDevice(){return low;}
uint64_t os_proc_available_memory(){return headroom;}
'''+body+r'''
int main(){
 sharedBufferPool.retire(std::make_shared<unsigned>(1),4ull<<20,1);
 sharedBufferPool.retire(std::make_shared<unsigned>(2),4ull<<20,2);
 trimIdleBufferCaches(1001);assert(!bufferCachePressure&&bufferCacheTrimmedBytes==0);
 low=1;trimIdleBufferCaches(2002);assert(bufferCachePressure&&bufferCacheTrimmedBytes==(4ull<<20));
 assert(sharedBufferPool.bytes()==4ull<<20); // unfinished GPU use retained
 R->completed.store(2);trimIdleBufferCaches(3003);assert(sharedBufferPool.bytes()==0);
 headroom=480ull<<20;trimIdleBufferCaches(4004);assert(bufferCachePressure);
 headroom=770ull<<20;trimIdleBufferCaches(5005);assert(!bufferCachePressure);
}
''',cpp=True)

 def graphics_fixture(self,configuration):
  presets=(APP/'App/GraphicsOptions.swift').read_text().split('enum GraphicsPreset:',1)[1].split('/// What this device',1)[0]
  return r'''
import Foundation
import CoreGraphics
enum ProcessInfo {struct Info {var physicalMemory:UInt64=8*1024*1024*1024};static var processInfo=Info()}
enum L10n {static func text(_ s:String)->String{s}}
struct Screen {var nativeBounds=CGRect(x:0,y:0,width:1170,height:540);var maximumFramesPerSecond=120}
enum UIScreen {static var main=Screen()}
enum GraphicsPreset:'''+presets+r'''
struct GameSettings {var memoryProfile=MemoryProfile.automatic;var engineMemoryMB=0;var graphicsPreset=GraphicsPreset.max;var renderHeight=2160;var matchScreenShape=true;var frameRateCap=0;static func frameRateTitle(_ cap:Int)->String{"\(cap) FPS"}}
var requested:(Int32,Int32,Int32)=(0,0,0);var pacing=0.0;var options:[String]=[]
func PGSetMemoryProfile(_ n:Int32){}
func PGSetEngineMemoryMB(_ n:Int32){}
func PGConfigureEngine(_ o:UnsafePointer<UnsafePointer<CChar>?>,_ count:UInt32,_ w:Int32,_ h:Int32,_ limit:Int32){requested=(w,h,limit);options=(0..<Int(count)).map{String(cString:o[$0]!)}}
func PGSetPresentPacing(_ seconds:Double){pacing=seconds}
enum GraphicsConfiguration {
'''+configuration

 def test_independent_memory_profile_and_modern_parity(self):
  source=(APP/'App/GraphicsOptions.swift').read_text().split('enum GraphicsConfiguration {',1)[1]
  old=subprocess.check_output(['git','show','b3a69e59bd57fa458159f3063a45e7e417045e4f:native-port/app/App/GraphicsOptions.swift'],cwd=APP,text=True).split('enum GraphicsConfiguration {',1)[1]
  sweep=r'''
for preset in GraphicsPreset.allCases {for height in [0,360,432,540,720,1080,2160] {for cap in [0,30,60] {for heat in 0...3 {
 var s=GameSettings();s.graphicsPreset=preset;s.renderHeight=height;s.frameRateCap=cap
 let limit=EngineLanThermalGraphics.startupLimit(frameRateCap:cap,thermalState:heat)
 _ = GraphicsConfiguration.apply(s,screen:CGSize(width:1170,height:540),renderScale:EngineLanThermalGraphics.startupScale(thermalState:heat),frameIntervalOverride:limit)
 print(requested.0,requested.1,requested.2,pacing,options.joined(separator:"|"))
}}}}
'''
  extra=[APP/'App/LowMemoryGraphics.swift',ROOT/'EngineLanThermalGraphics.swift']
  self.assertEqual(self.execute(self.graphics_fixture(source)+sweep,True,extra),self.execute(self.graphics_fixture(old)+sweep,True,extra))
  self.execute(self.graphics_fixture(source)+r'''
let devices:[UInt64]=[3221225472,3565158400,4294967296,8589934592]
for ram in devices {
 ProcessInfo.processInfo.physicalMemory=ram;let low=ram<3565158400
 for heat in 0...3 {
  let saved=GameSettings();let cap=saved.frameRateCap
  let interval=EngineLanThermalGraphics.startupLimit(frameRateCap:cap,thermalState:heat)
  _ = GraphicsConfiguration.apply(saved,screen:CGSize(width:1170,height:540),renderScale:EngineLanThermalGraphics.startupScale(thermalState:heat),frameIntervalOverride:interval)
  assert(LowMemoryGraphics.isEnabled()==low)
  assert(options==GraphicsPreset.max.engineOptions);assert(requested.2==interval)
  assert(requested.1==Int((2160 * EngineLanThermalGraphics.startupScale(thermalState:heat)).rounded()) & ~1)
  assert(saved.renderHeight==2160&&saved.frameRateCap==0&&saved.graphicsPreset == .max)
 }
}
ProcessInfo.processInfo.physicalMemory=3*1024*1024*1024
var policy=EngineLanThermalGraphics();policy.begin(frameRateCap:60,initialLimit:3)
for n in 0..<30 {assert(policy.nextLimit(thermalState:0,ready:true,now:Double(n))==nil)}
assert(policy.nextLimit(thermalState:0,ready:true,now:30)==1)
assert(!LowMemoryGraphics.isEnabled(profile:.standard))
assert(LowMemoryGraphics.isEnabled(physicalMemoryBytes:8*1024*1024*1024,profile:.reduced))
''',True,extra)
  staged=prepare.controller_patch((APP/'App/NativePortViewController.swift').read_text())
  self.assertIn('lanThermalGraphics.begin(frameRateCap: GameSettings.shared.frameRateCap',staged)
  self.assertIn('bootedFrameRateCap = GameSettings.shared.frameRateCap',staged)

if __name__=='__main__':unittest.main()
