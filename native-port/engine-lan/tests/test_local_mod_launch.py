"""Execute production preload admission with the native first-manifest boundary."""
from pathlib import Path
import subprocess
import tempfile
import unittest
APP=Path(__file__).resolve().parents[2]/'app'
def method(source,name):
    begin=source.index('    func '+name);brace=source.index('{',begin);depth=1;end=brace+1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[begin:end]
class LocalModLaunch(unittest.TestCase):
    def test_final_local_manifest_and_frozen_remote_cache(self):
        source=(APP/'App/AssetPreloader.swift').read_text();body=method(source,'prepare()')
        property_line=next(s for s in source.splitlines() if 'var localLaunchNeedsRestart:' in s)
        fixture='''import Foundation
func check(_ value:Bool,_ message:String){if !value{print(message);exit(42)}}
enum GameFolder{static var isChosen=true}
enum EnginePaths{static var manifest:String?="base.json";static func filesRoot()->URL{URL(fileURLWithPath:"/temporary-test-root")}}
var calls=0
var frozen:String?
// NativeAssets boundary double: first manifest wins; no engine, files or network.
func PGAssetCachePrepare(_ manifest:UnsafePointer<CChar>,_ root:UnsafePointer<CChar>){calls+=1;if frozen==nil{frozen=String(cString:manifest)}}
final class Probe{var prepared=false
'''+body+'\n'+property_line+'''
}
let local=Probe();local.prepare()
check(calls==0 && frozen==nil && !local.prepared,"LOCAL_BASE_MANIFEST_PREEMPTED_MOD_OVERLAY")
check(!local.localLaunchNeedsRestart,"Existing local folder should launch directly")
"mod-overlay.json".withCString{m in "/temporary-test-root".withCString{PGAssetCachePrepare(m,$0)}}
check(frozen=="mod-overlay.json","Local engine must initialize from final mod overlay")
calls=0;frozen=nil;GameFolder.isChosen=false
let remote=Probe();remote.prepare();remote.prepare()
check(calls==1 && frozen=="base.json" && remote.prepared,"Remote cache must prepare once")
GameFolder.isChosen=true;remote.prepare()
check(calls==1 && frozen=="base.json" && remote.localLaunchNeedsRestart,"Local switch must request restart without replacing an active cache")
GameFolder.isChosen=false;EnginePaths.manifest=nil
let missing=Probe();missing.prepare()
check(!missing.prepared && calls==1,"Missing manifest must not configure cache")
print("LOCAL_MOD_MANIFEST_ADMISSION_PASS")
'''
        with tempfile.TemporaryDirectory(prefix='zgta-local-mod-') as folder:
            root=Path(folder);p=root/'main.swift'
            def run_case(text,name):
                p.write_text(text)
                c=subprocess.run(['/usr/bin/swiftc','-warnings-as-errors','-module-cache-path',str(root/'modules'),str(p),'-o',str(root/name)],capture_output=True,text=True,timeout=90)
                self.assertEqual(c.returncode,0,c.stdout+c.stderr)
                return subprocess.run([str(root/name)],capture_output=True,text=True,timeout=15)
            result=run_case(fixture,'after');self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            # Restore the previous admission behavior to demonstrate the actual regression.
            before=body.replace('        guard !GameFolder.isChosen else { return }\n','')
            self.assertNotEqual(before,body)
            result=run_case(fixture.replace(body,before),'before')
            self.assertEqual(result.returncode,42,result.stdout+result.stderr)
            self.assertIn('LOCAL_BASE_MANIFEST_PREEMPTED_MOD_OVERLAY',result.stdout)
    def test_all_preload_entries_and_launch_side_effects_are_guarded(self):
        source=(APP/'App/AssetPreloader.swift').read_text()
        for name in ['refresh(completion:','start()','resumeIfNeeded()']:
            body=method(source,name);self.assertLess(body.index('guard !GameFolder.isChosen'),body.index('prepare()'))
        source=(APP/'App/NativePortViewController.swift').read_text()
        self.assertLess(source.index('if localData != nil && AssetPreloader.shared.localLaunchNeedsRestart'),source.index('        engineStarted = true'))
        self.assertIn('if(atomic_exchange(&assetsConfigured,true))return;',(APP/'Source/NativeAssets.m').read_text())
if __name__=='__main__':unittest.main()
