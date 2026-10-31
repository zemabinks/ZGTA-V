"""Execute the portable consumer recorder and real Swift report attachment.

These unit programs exercise the shipped source without creating an app,
starting the game, reading producer memory or waiting on a GPU.
"""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT.parent / 'app'

CPP = r'''
#include "NativeRenderingDiagnostics.h"
#include <cassert>
#include <iostream>
#include <string>

static PGRenderingObservation observation(uint64_t frame, bool partial=false) {
 PGRenderingObservation value{}; value.frame=frame; value.snapshotFrame=frame;
 for(auto& word:value.shadow)word=0x3f800000u;
 for(auto& word:value.bound)word=0x3f800000u;
 if(partial)value.shadow[1]=0;
 return value;
}
static void offer(PGRenderingDiagnostics& capture, const PGRenderingObservation& value) {
 if(capture.wantsFrame(value.frame))capture.record(value);
}
static void off_by_default_and_exact_counters() {
 PGRenderingDiagnostics capture;
 assert(!capture.active());assert(!capture.wantsFrame(1));
 capture.record(observation(1));capture.copy(true,true);
 auto s=capture.read();assert(s.generation==0&&s.observedDraws==0&&s.cbCopies==0&&s.observations.empty());
 capture.enable(true);assert(capture.active());
 capture.copy(true,false);capture.copy(false,true);capture.copy(true,true);capture.copy(false,false);
 assert(capture.wantsFrame(120));capture.record(observation(120));
 assert(!capture.wantsFrame(121));
 s=capture.read();assert(s.generation==1&&s.observedDraws==2);
 assert(s.cbCopies==4&&s.cbCopiesUpdated==2&&s.cbCopiesUnsupported==2&&s.observations.size()==1);
 capture.enable(true);assert(capture.read().generation==1); // Idempotent while enabled.
 capture.enable(false);assert(!capture.active());
 capture.copy(true,true);assert(!capture.wantsFrame(180));capture.record(observation(120));
 auto stopped=capture.read();assert(stopped.observedDraws==2&&stopped.cbCopies==4&&stopped.observations.size()==1);
 capture.enable(true);s=capture.read();
 assert(s.generation==2&&s.observedDraws==0&&s.cbCopies==0&&s.cbCopiesUpdated==0&&s.cbCopiesUnsupported==0);
 assert(s.observations.empty());
}
static void frame_window_and_separate_quotas() {
 PGRenderingDiagnostics capture;capture.enable(true);
 for(unsigned n=0;n<8;n++){auto value=observation(100);value.kind=n;offer(capture,value);}
 auto s=capture.read();assert(s.observations.size()==4);
 for(unsigned n=0;n<20;n++){auto value=observation(100,true);value.kind=100+n;offer(capture,value);}
 s=capture.read();assert(s.observations.size()==16);
 assert(!capture.wantsFrame(100));
 for(unsigned n=0;n<4;n++)assert(s.observations[n].kind==n);
 for(unsigned n=0;n<12;n++)assert(s.observations[4+n].kind==100+n);
 assert(!capture.wantsFrame(99));capture.record(observation(99,true));
 assert(!capture.wantsFrame(101));capture.record(observation(101,true));
 assert(capture.read().observations.size()==16);
 assert(capture.wantsFrame(160));capture.record(observation(160));
 assert(capture.read().observations.size()==17);
 // A nonzero opcode is partial even if shadow words are all one.
 auto stipple=observation(160);stipple.stipple=25;
 for(unsigned n=0;n<20;n++)offer(capture,stipple);
 s=capture.read();assert(s.observations.size()==29);
 for(unsigned n=17;n<29;n++)assert(s.observations[n].stipple==25);
 // The sixteen sampled frames are [start,start+900], every sixty frames.
 assert(!capture.wantsFrame(100+960));capture.record(observation(1060));
 assert(capture.read().observations.size()==29);
}
static void exact_limit_and_stopped_retention() {
 PGRenderingDiagnostics capture;capture.enable(true);
 for(uint64_t frame=500;frame<500+16*60;frame+=60){
  for(unsigned n=0;n<4;n++)offer(capture,observation(frame));
  for(unsigned n=0;n<12;n++)offer(capture,observation(frame,true));
 }
 auto full=capture.read();assert(full.observations.size()==PGRenderingDiagnostics::Limit);
 assert(full.observedDraws==256);assert(full.observations.front().frame==500);
 assert(full.observations.back().frame==1400);
 for(unsigned n=0;n<1000;n++)offer(capture,observation(1400,true));
 assert(capture.read().observations.size()==256);
 assert(!capture.wantsFrame(1460));
 capture.enable(false);auto stopped=capture.read();
 assert(stopped.observations.size()==256&&stopped.observedDraws==1257);
 capture.record(observation(1400));capture.copy(true,true);
 assert(capture.read().observations.size()==256&&capture.read().cbCopies==0);
}
static void no_metadata_leak_between_generations() {
 PGRenderingDiagnostics capture;capture.enable(true);
 auto old=observation(77,true);old.target=987;old.constantBuffer=123;old.version=999;
 old.shadowValid=old.boundValid=old.encoded=true;
 std::strcpy(old.vertexShader,"1111111111111111");std::strcpy(old.pixelShader,"2222222222222222");
 std::strcpy(old.outcome,"old-generation");offer(capture,old);
 capture.copy(true,true);capture.enable(false);
 auto stopped=capture.read();assert(stopped.observations.size()==1&&stopped.observations[0].target==987);
 capture.enable(true);assert(capture.read().observations.empty());
 auto fresh=observation(9000);fresh.kind=7;offer(capture,fresh);
 auto s=capture.read();assert(s.generation==2&&s.observedDraws==1&&s.cbCopies==0&&s.observations.size()==1);
 const auto& value=s.observations[0];assert(value.frame==9000&&value.kind==7);
 assert(value.target==0&&value.constantBuffer==0&&value.version==0);
 assert(!value.shadowValid&&!value.boundValid&&!value.encoded);
 assert(value.vertexShader[0]==0&&value.pixelShader[0]==0&&value.outcome[0]==0);
 assert(stopped.generation==1&&stopped.observations[0].target==987); // Snapshot owns its copy.
}
int main(){
 off_by_default_and_exact_counters();frame_window_and_separate_quotas();
 exact_limit_and_stopped_retention();no_metadata_leak_between_generations();
 std::cout<<"{\"recorder\":\"PASS\",\"limit\":256,\"windowFrames\":960,\"samplePeriod\":60,\"fullQuota\":4,\"partialQuota\":12,\"stateCases\":4}\n";
}
'''

SWIFT = r'''
import Foundation
func encoded(_ run: PerformanceRun) throws -> [String: Any] {
 return try JSONSerialization.jsonObject(with: JSONEncoder().encode(run.result!)) as! [String: Any]
}
func finish(_ run: PerformanceRun, capture: Bool=false, start: Double=0) {
 run.start(now:start,context:capture ? ["renderingCapture":"true"]:[:])
 for n in stride(from:1000.0,through:32000.0,by:1000.0) {
  run.observeConditions(["thermalState":0,"requestedFrameInterval":1],now:start+n)
  run.sample(fps:n<16000 ? 60:30,now:start+n)
 }
 assert(run.state == .complete && run.result != nil)
}
func consumer(_ observations: [[String: String]], format: String="zgta-rendering-consumer105-v1", note: String="bounded consumer capture") throws -> Data {
 return try JSONSerialization.data(withJSONObject:["format":format,"observations":observations,
  "counters":["generation":2,"observedDraws":200,"constantBufferCopies":5,"shadowCopiesUpdated":3,"unknownSourceCopies":1],"note":note])
}
let event = ["frame":"900","snapshotFrame":"900","drawKind":"1","drawArg1":"24","drawArg2":"1",
 "stipple":"25","constantBuffer":"77","version":"3","target":"2","depth":"4",
 "vs":"1111111111111111","ps":"2222222222222222","outcome":"encoded",
 "shadow0":"3f800000","shadow1":"00000000","shadow2":"00000000","shadow3":"3f800000",
 "bound0":"3f800000","bound1":"00000000","bound2":"00000000","bound3":"3f800000"]
let valid = try consumer([event])
let capture = PerformanceRun()
capture.start(now:0,context:["renderingCapture":"true"])
capture.attachRenderingDiagnostics(valid)
assert(capture.state == .running && capture.result == nil)
finish(capture,capture:true)
capture.attachRenderingDiagnostics(valid)
let attached = try encoded(capture)
let document = attached["renderingDiagnostics"] as! [String:Any]
assert(document["format"] as! String == "zgta-rendering-consumer105-v1")
assert(document["observations"] as! [[String:String]] == [event])
let counters = document["counters"] as! [String:NSNumber]
assert(counters["generation"]!.uint64Value == 2 && counters["observedDraws"]!.uint64Value == 200)
assert(counters["constantBufferCopies"]!.uint64Value == 5 && counters["shadowCopiesUpdated"]!.uint64Value == 3)
assert(counters["unknownSourceCopies"]!.uint64Value == 1)
let warnings = attached["comparisonWarnings"] as! [String]
assert(warnings == ["Rendering diagnostics were active; this run is not a clean FPS comparison."])

let normal = PerformanceRun();finish(normal)
let baseline = try encoded(normal)
assert(baseline["renderingDiagnostics"] == nil)
assert((baseline["comparisonWarnings"] as! [String]).isEmpty)
for key in ["durationMS","samples","averageFPS","medianWindowFPS","slowestWindowFPS"] {
 assert((baseline[key] as! NSNumber) == (attached[key] as! NSNumber))
}
assert(NSDictionary(dictionary:baseline["conditions"] as! [String:Any]).isEqual(to:attached["conditions"] as! [String:Any]))
assert(NSArray(array:baseline["timeline"] as! [Any]).isEqual(to:attached["timeline"] as! [Any]))

let invalid: [Data] = [Data("{broken".utf8),
 try consumer([event],format:"unexpected-format"),try consumer(Array(repeating:event,count:257)),
 try consumer([event],note:String(repeating:"x",count:524289)),
 Data("{\"format\":\"zgta-rendering-consumer105-v1\",\"observations\":[{\"frame\":900}],\"counters\":{},\"note\":\"bad typed observation\"}".utf8),
 Data("{\"format\":\"zgta-rendering-consumer105-v1\",\"observations\":[],\"counters\":{\"observedDraws\":-1},\"note\":\"bad counter\"}".utf8)]
for data in invalid {
 normal.attachRenderingDiagnostics(data)
 let normalAfterInvalid = try encoded(normal)
 assert(normalAfterInvalid["renderingDiagnostics"] == nil)
 capture.attachRenderingDiagnostics(data)
 let captureAfterInvalid = try encoded(capture)
 assert(captureAfterInvalid["renderingDiagnostics"] != nil)
 assert(capture.result!.renderingDiagnostics!.observations == [event])
}
let boundary = PerformanceRun();finish(boundary,capture:true)
boundary.attachRenderingDiagnostics(try consumer(Array(repeating:event,count:256)))
assert(boundary.result!.renderingDiagnostics!.observations.count == 256)
let empty = PerformanceRun();finish(empty,capture:true)
empty.attachRenderingDiagnostics(try consumer([]))
assert(empty.result!.renderingDiagnostics!.observations.isEmpty)

// Reusing the measurement object must discard prior capture metadata/warnings.
finish(capture,start:50000)
assert(capture.result!.renderingDiagnostics == nil)
assert(capture.result!.comparisonWarnings.isEmpty)
capture.start(now:100000,context:["renderingCapture":"true"]);capture.cancel()
capture.attachRenderingDiagnostics(valid)
assert(capture.state == .cancelled && capture.result == nil)
print("{\"swiftReport\":\"PASS\",\"invalidInputs\":6,\"acceptedObservationBoundary\":256,\"fpsResultsUnchanged\":true,\"restartClearsCapture\":true}")
'''


class RenderingDiagnostics105(unittest.TestCase):
    def run_program(self, arguments):
        result = subprocess.run([str(v) for v in arguments],capture_output=True,text=True,timeout=120)
        self.assertEqual(result.returncode,0,result.stdout + result.stderr)
        return result.stdout

    def test_compiled_consumer_recorder_bounds_and_capture_lifecycle(self):
        compiler = shutil.which('clang++')
        if not compiler: self.skipTest('C++ compiler unavailable')
        with tempfile.TemporaryDirectory(prefix='zgta-rendering-recorder105-') as folder:
            d = Path(folder); source=d/'recorder.cpp'; source.write_text(CPP)
            self.run_program([compiler,'-std=c++17','-pthread','-I',APP/'Source',source,'-o',d/'recorder'])
            report = json.loads(self.run_program([d/'recorder']))
            self.assertEqual(report['recorder'],'PASS')
            self.assertEqual(report['limit'],256)
            self.assertEqual(report['windowFrames'],960)
            self.assertEqual((report['fullQuota'],report['partialQuota']),(4,12))
            print('RENDERING_CONSUMER105_COMPILED_PASS: ' + json.dumps(report,sort_keys=True))

    def test_real_swift_finish_attach_decode_rejection_and_fps_equivalence(self):
        compiler = shutil.which('swiftc')
        if not compiler: self.skipTest('Swift compiler unavailable')
        with tempfile.TemporaryDirectory(prefix='zgta-rendering-report105-') as folder:
            d=Path(folder);source=d/'main.swift';source.write_text(SWIFT)
            self.run_program([compiler,'-module-cache-path',d/'ModuleCache',APP/'App/PerformanceRun.swift',source,'-o',d/'report'])
            report = json.loads(self.run_program([d/'report']))
            self.assertEqual(report['swiftReport'],'PASS')
            self.assertEqual(report['invalidInputs'],6)
            self.assertTrue(report['fpsResultsUnchanged'])
            self.assertTrue(report['restartClearsCapture'])
            print('RENDERING_REPORT105_REAL_SWIFT_PASS: ' + json.dumps(report,sort_keys=True))


if __name__ == '__main__': unittest.main()
