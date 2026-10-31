"""Execute browser/Swift measurement cores against identical clock/FPS traces."""
import json
import os
from pathlib import Path
from public_test_inputs import game_file
import subprocess
import tempfile
import unittest
import serve_browser

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT.parent/'app'

class Performance(unittest.TestCase):
    def test_matching_bounded_measurements_and_rejected_stale_runs(self):
        cases=[]
        for label,events in [
            ('constant',[[n,60] for n in range(500,32500,500)]),
            ('weighted',[[n,20 if n%1500==0 else 50] for n in range(500,32500,500)]),
            ('zero',[[n,0] for n in range(500,32500,500)]),
            ('stopped',[[500,60],[2501,60]]),
            ('clock-backwards',[[500,60],[400,60]]),
            ('invalid',[[500,-1]]),
            ('overflow',[[500,1001]]),
            ('too-frequent',[[n,60] for n in range(100,21000,100)]),
            ('cancel',[[500,60],[1000,'cancel'],[1500,60]]),
            ('restart',[[500,40],[1000,'cancel'],[0,'restart']]+[[n,30] for n in range(500,32500,500)]),
        ]:cases.append({'label':label,'events':events})
        cases.append({'label':'sustained','duration':180,'events':[[n,60 if n<=92000 else 30] for n in range(500,182500,500)]})
        js=r'''
const fs=require('fs'),{Run}=require(process.argv[1]);
const rows=JSON.parse(fs.readFileSync(process.argv[2])).map(c=>{
 const r=new Run();r.start(0,{},c.duration||30);
 for(const [now,value] of c.events){if(value==='cancel')r.cancel();else if(value==='restart')r.start(now);else r.sample(value,now);}
 return {label:c.label,state:r.state,result:r.result?{duration:r.result.durationMS,count:r.result.samples,average:r.result.averageFPS,median:r.result.medianWindowFPS,slowest:r.result.slowestWindowFPS}:null};
});console.log(JSON.stringify(rows));
'''
        swift=r'''
import Foundation
let cases = try JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))) as! [[String: Any]]
var rows: [[String: Any]] = []
for c in cases {
 let r = PerformanceRun(); r.start(now: 0, durationSeconds: c["duration"] as? Int ?? 30)
 for event in c["events"] as! [[Any]] {
  let now = (event[0] as! NSNumber).doubleValue
  if let value = event[1] as? String { if value == "cancel" { r.cancel() } else { r.start(now: now) } }
  else { r.sample(fps: (event[1] as! NSNumber).doubleValue, now: now) }
 }
 var row: [String: Any] = ["label": c["label"]!, "state": r.state.rawValue, "result": NSNull()]
 if let s = r.result { row["result"] = ["duration": s.durationMS,"count":s.samples,"average":s.averageFPS,"median":s.medianWindowFPS,"slowest":s.slowestWindowFPS] }
 rows.append(row)
}
let output = try JSONSerialization.data(withJSONObject: rows, options: [.sortedKeys])
print(String(data: output, encoding: .utf8)!)
'''
        def run(args):
            p=subprocess.run([str(v) for v in args],capture_output=True,text=True,timeout=120)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr);return p.stdout
        with tempfile.TemporaryDirectory(prefix='zgta-performance-') as folder:
            d=Path(folder);(d/'cases.json').write_text(json.dumps(cases));(d/'main.swift').write_text(swift)
            browser=json.loads(run(['node','-e',js,ROOT/'performance-run.js',d/'cases.json']))
            run(['/usr/bin/swiftc','-module-cache-path',d/'ModuleCache',APP/'App/PerformanceRun.swift',d/'main.swift','-o',d/'measure'])
            native=json.loads(run([d/'measure',d/'cases.json']))
            self.assertEqual(browser,native)
            by_name={r['label']:r for r in browser}
            self.assertEqual(by_name['constant']['result'],{'duration':30000,'count':60,'average':60,'median':60,'slowest':60})
            self.assertEqual(by_name['weighted']['result']['average'],40)
            self.assertEqual(by_name['restart']['result']['average'],30)
            self.assertEqual(by_name['sustained']['result']['duration'],180000)
            self.assertEqual(by_name['sustained']['result']['average'],45)
            for name in ['stopped','clock-backwards','invalid','overflow','too-frequent','cancel']:
                self.assertEqual(by_name[name]['state'],'cancelled');self.assertIsNone(by_name[name]['result'])

    def test_condition_summaries_match_and_remain_bounded(self):
        js = r'''
const {Run}=require(process.argv[1]);const r=new Run();r.start(0);
for(let n=500;n<=32000;n+=500){
 const v={availableMemoryBytes:1000000-n,appFootprintBytes:-1,thermalState:n<16000?0:2,requestedRenderHeight:n<16000?540:432,resourceBytesReleased:n<16000?n:100,resourceBytesReused:n*2,thermalScale:NaN,requestedFrameInterval:n<16000?1:2,secondsSinceWorldReady:n/1000+120,unapproved:99,metalAllocatedBytes:104857600,cpuGPUFenceWaitMSPerFrame:n/1000,assetReadCount:n/500,bufferArenaLiveBytes:8192,bufferArenaRequestedBytes:7272,bufferArenaPendingBytes:512,bufferArenaReusableBytes:1024,textureCreateFailures:n/1000,textureDecodeFailures:0};
 r.observeConditions(v,n);r.observeConditions({availableMemoryBytes:0},n+1);r.sample(60,n);
}
console.log(JSON.stringify(r.result));r.start(40000);if(Object.keys(r.conditions).length)throw Error('Restart retained conditions');r.cancel();r.observeConditions({thermalState:3},42000);if(Object.keys(r.conditions).length)throw Error('Cancelled observation');
'''
        swift = r'''
import Foundation
let r = PerformanceRun(); r.start(now: 0)
for n in stride(from: 500.0, through: 32000.0, by: 500.0) {
 let v: [String: Double] = ["availableMemoryBytes":1000000-n,"appFootprintBytes": -1,"thermalState":n<16000 ? 0:2,"requestedRenderHeight":n<16000 ? 540:432,"resourceBytesReleased":n<16000 ? n:100,"resourceBytesReused":n*2,"thermalScale":Double.nan,"requestedFrameInterval":n<16000 ? 1:2,"secondsSinceWorldReady":n/1000+120,"unapproved":99,"metalAllocatedBytes":104857600,"cpuGPUFenceWaitMSPerFrame":n/1000,"assetReadCount":n/500,"bufferArenaLiveBytes":8192,"bufferArenaRequestedBytes":7272,"bufferArenaPendingBytes":512,"bufferArenaReusableBytes":1024,"textureCreateFailures":n/1000,"textureDecodeFailures":0]
 r.observeConditions(v, now:n);r.observeConditions(["availableMemoryBytes":0], now:n+1);r.sample(fps:60, now:n)
}
print(String(data:try JSONEncoder().encode(r.result!), encoding:.utf8)!)
r.start(now:40000);r.cancel();r.observeConditions(["thermalState":3], now:42000)
assert(r.result == nil && r.state == .cancelled)
'''
        def run(args):
            p=subprocess.run([str(v) for v in args],capture_output=True,text=True,timeout=120)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr);return p.stdout
        with tempfile.TemporaryDirectory(prefix='zgta-conditions-') as folder:
            d=Path(folder);(d/'main.swift').write_text(swift)
            browser=json.loads(run(['node','-e',js,ROOT/'performance-run.js']))
            run(['/usr/bin/swiftc','-module-cache-path',d/'ModuleCache',APP/'App/PerformanceRun.swift',d/'main.swift','-o',d/'measure'])
            native=json.loads(run([d/'measure']))
            self.assertEqual(browser,native)
            c=native['conditions'];self.assertEqual(c['availableMemoryBytes']['observations'],31)
            self.assertEqual(c['availableMemoryBytes']['minimum'],968000)
            self.assertNotIn('appFootprintBytes',c);self.assertNotIn('unapproved',c);self.assertNotIn('thermalScale',c)
            self.assertEqual(c['resourceBytesReused']['delta'],60000)
            self.assertTrue(c['resourceBytesReleased']['counterReset']);self.assertNotIn('delta',c['resourceBytesReleased'])
            self.assertEqual(c['requestedFrameInterval']['maximum'],2)
            self.assertEqual(c['secondsSinceWorldReady']['minimum'],122)
            self.assertEqual(c['metalAllocatedBytes']['maximum'],104857600)
            self.assertEqual(c['cpuGPUFenceWaitMSPerFrame']['maximum'],32)
            self.assertEqual(c['assetReadCount']['delta'],60)
            self.assertEqual(c['bufferArenaLiveBytes']['last'],8192)
            self.assertEqual(c['textureCreateFailures']['delta'],30)
            self.assertEqual(len(native['comparisonWarnings']),5)


    def test_sustained_timeline_tracks_heat_and_frame_cap_changes(self):
        js=r'''const {Run}=require(process.argv[1]);const r=new Run();r.start(0,{},180);
for(let n=500;n<=182000;n+=500){r.observeConditions({thermalState:n<92000?1:2,requestedFrameInterval:n<92000?1:2},n);r.sample(n<=92000?60:30,n);}
console.log(JSON.stringify(r.result));'''
        swift=r'''import Foundation
let r=PerformanceRun();r.start(now:0,durationSeconds:180)
for n in stride(from:500.0,through:182000.0,by:500.0){r.observeConditions(["thermalState":n<92000 ? 1:2,"requestedFrameInterval":n<92000 ? 1:2],now:n);r.sample(fps:n<=92000 ? 60:30,now:n)}
print(String(data:try JSONEncoder().encode(r.result!),encoding:.utf8)!)
'''
        with tempfile.TemporaryDirectory(prefix='zgta-sustained-') as folder:
            d=Path(folder);(d/'main.swift').write_text(swift)
            def run(args):
                p=subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=120)
                self.assertEqual(p.returncode,0,p.stdout+p.stderr);return p.stdout
            browser=json.loads(run(['node','-e',js,ROOT/'performance-run.js']))
            run(['/usr/bin/swiftc','-module-cache-path',d/'cache',APP/'App/PerformanceRun.swift',d/'main.swift','-o',d/'run'])
            native=json.loads(run([d/'run']))
            self.assertEqual(browser,native)
            self.assertEqual(native['averageFPS'],45)
            self.assertEqual(len(native['timeline']),180)
            self.assertEqual(native['timeline'][0]['conditions']['thermalState'],1)
            self.assertEqual(native['timeline'][-1]['conditions']['thermalState'],2)
            self.assertEqual(native['timeline'][-1]['fps'],30)
            self.assertEqual(native['timeline'][-1]['conditions']['requestedFrameInterval'],2)

    def test_real_mod_manager_mount_and_measurement_controls(self):
        p=subprocess.run(['node',str(ROOT/'tests/performance_run_ui_fixture.cjs'),str(ROOT)],capture_output=True,text=True,timeout=20)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)

    def test_real_worker_channel_transform_and_launcher_wiring(self):
        stage=Path(os.environ.get('ZGTA_TEST_BROWSER_STAGE',str(APP/'Build/Browser-UpstreamStability-20261021-v42')))
        loader=serve_browser.fps_transport('loader.js',(stage/'loader.js').read_bytes()).decode()
        gpu=serve_browser.fps_transport('wgpu_worker.js',(stage/'wgpu_worker.js').read_bytes()).decode()
        for data,name in [(loader,'loader.js'),(gpu,'wgpu_worker.js')]:
            with self.assertRaises(ValueError):serve_browser.fps_transport(name,data.encode())
        snippet=loader[loader.index('const gq ='):loader.index("if (m.slots)")]
        resolve=gpu[gpu.index('(()=>{const n=new URLSearchParams'):gpu.index("})())",gpu.index('(()=>{const n=new URLSearchParams'))+4]
        script='const a=require("assert/strict");const transport=m=>{'+snippet+'return gq.get("fpsChannel");};\n'
        script+='const resolve=search=>{const self={location:{search}};return '+resolve+';};\n'
        script+="for(const id of ['zema-fps-11111111-1111-1111-1111-111111111111','zema-fps-22222222-2222-2222-2222-222222222222']){a.equal(transport({fpsChannel:id}),id);a.equal(resolve('?fpsChannel='+id),id);}a.equal(transport({fpsChannel:'private/path'}),null);a.equal(resolve('?fpsChannel=private/path'),'game-fps');"
        p=subprocess.run(['node','-e',script],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        mirror=game_file('index.html').read_bytes()
        for mode in ['lan','story','sandbox']:
            page=serve_browser.index(mirror,mode).decode()
            self.assertIn('fpsChannel:window.ZemaFPSChannel',page)
            self.assertIn('new BroadcastChannel(window.ZemaFPSChannel)',page)
            self.assertIn('/zema-lab/performance-run.js',page)
            self.assertLess(page.index('/zema-lab/trainer-ui.js'),page.index('/zema-lab/performance-run.js'),'The manager DOMContentLoaded listener must mount before performance controls attach')

if __name__=='__main__':unittest.main()
