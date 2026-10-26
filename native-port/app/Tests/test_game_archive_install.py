"""Real ZIP/split ZIP extraction plus retained parent grant/source protection.

Only the OS security-scope calls are instrumented in the private compiled copy;
File Provider permission itself still requires a physical device test.
"""
import json, os, subprocess, tempfile, unittest, zipfile
from pathlib import Path
APP = Path(__file__).resolve().parents[1]
class ArchiveInstallTests(unittest.TestCase):
 def test_discovered_folder_archive_installs_without_consuming_source(self):
  with tempfile.TemporaryDirectory(prefix='zgta-archive-install-') as t:
   root=Path(t)
   manifest=root/'manifest.json';manifest.write_text(json.dumps({'files':[['common/config.xml',2,0],['x64/example.dat',3,0]]}))
   archive=root/'Game.zip'
   with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('Prepared Game/data/common/config.xml',b'ok');z.writestr('Prepared Game/data/x64/example.dat',b'123');z.writestr('unrelated.txt',b'not a game file')
   raw=archive.read_bytes();(root/'Split.zip.001').write_bytes(raw[:len(raw)//2]);(root/'Split.zip.002').write_bytes(raw[len(raw)//2:])
   (root/'bad.zip').write_bytes(b'not an archive')
   source=(APP/'App/GameInstall.swift').read_text().replace('url.startAccessingSecurityScopedResource()', 'Fixture.begin(url)').replace('$0.stopAccessingSecurityScopedResource()', 'Fixture.end($0)')
   (root/'GameInstall.swift').write_text(source)
   support='''import Foundation
   enum Fixture {
    static let root=URL(fileURLWithPath: ROOT_PATH)
    static var grants=[String:Int]()
    static func begin(_ u:URL)->Bool { grants[u.path,default:0]+=1; return true }
    static func end(_ u:URL) { grants[u.path,default:0]-=1 }
    static let readBegan=DispatchSemaphore(value:0)
    static let readMayContinue=DispatchSemaphore(value:0)
    static var testCoordination=false
   }
   enum EnginePaths { static var manifest:String? { Fixture.root.appendingPathComponent("manifest.json").path } }
   enum GameFolder {
    static var log: (String)->Void = { line in
     if Fixture.testCoordination && line.hasPrefix("Install: Coordinated archive read:") {
      Fixture.readBegan.signal(); Fixture.readMayContinue.wait()
     }
    }
    static func clear() {}
    static func findInAppFolder() {}
   }
   '''.replace('ROOT_PATH',json.dumps(t))
   (root/'Support.swift').write_text(support)
   (root/'main.swift').write_text('''import Foundation
   final class ArchivePresenter:NSObject,NSFilePresenter {
    let presentedItemURL:URL?
    let presentedItemOperationQueue=OperationQueue()
    init(_ url:URL) { presentedItemURL=url; super.init(); presentedItemOperationQueue.maxConcurrentOperationCount=1 }
   }
   if CommandLine.arguments.count==4 && CommandLine.arguments[1]=="--coordination-writer" {
    var error:NSError?
    NSFileCoordinator(filePresenter:nil).coordinate(writingItemAt:URL(fileURLWithPath:CommandLine.arguments[2]),options:[],error:&error) { _ in
     try! Data("writer granted".utf8).write(to:URL(fileURLWithPath:CommandLine.arguments[3]))
    }
    exit(error == nil ? 0 : 2)
   }
   func require(_ value:Bool,_ message:String="Archive check") { precondition(value,message) }
   let root=Fixture.root
   func install(_ name:String,success:Bool,cancel:Bool=false) throws {
    let archive=root.appendingPathComponent(name)
    let before=try Data(contentsOf:archive)
    let destination=root.appendingPathComponent("output-"+name)
    let presenter=ArchivePresenter(archive)
    NSFileCoordinator.addFilePresenter(presenter)
    defer { NSFileCoordinator.removeFilePresenter(presenter) }
    try FileManager.default.createDirectory(at:destination.appendingPathComponent("data/common"),withIntermediateDirectories:true)
    try Data("old incomplete game".utf8).write(to:destination.appendingPathComponent("data/common/config.xml"))
    try Data("existing save fixture".utf8).write(to:destination.appendingPathComponent("existing-save.zgtasave"))
    var done=false; var passed=false
    let run=GameInstallRun.start(.fileInFolder(archive,folder:root),to:destination,progress:{ _ in },completion:{ result in
     if case .success=result { passed=true }; done=true
    })
    require(Fixture.grants[root.path]==1,"Parent folder grant must stay active after start returns")
    let marker=root.appendingPathComponent("writer-entered")
    try? FileManager.default.removeItem(at:marker)
    let writer=Process()
    if Fixture.testCoordination {
     require(Fixture.readBegan.wait(timeout:.now()+5) == .success,"Read coordination started")
     writer.executableURL=URL(fileURLWithPath:CommandLine.arguments[0])
     writer.arguments=["--coordination-writer",archive.path,marker.path]
     try writer.run()
     RunLoop.main.run(until:Date().addingTimeInterval(0.3))
     require(!FileManager.default.fileExists(atPath:marker.path),"Provider writer must wait until extraction finishes")
     if cancel { run.cancel() }
     Fixture.readMayContinue.signal()
    }
    let deadline=Date().addingTimeInterval(10)
    while !done && Date()<deadline { RunLoop.main.run(until:Date().addingTimeInterval(0.01)) }
    withExtendedLifetime(run) {}
    require(done && passed==success,"Actual extraction result: "+name)
    require(Fixture.grants.values.allSatisfy { $0==0 },"All grants released after completion")
    if Fixture.testCoordination {
     let deadline=Date().addingTimeInterval(5)
     while writer.isRunning && Date()<deadline { RunLoop.main.run(until:Date().addingTimeInterval(0.01)) }
     if writer.isRunning { writer.terminate() }
     require(FileManager.default.fileExists(atPath:marker.path) && writer.terminationStatus==0,"Read coordination released after extraction")
    }
    require(try Data(contentsOf:archive)==before,"Source archive retained byte for byte")
    require(try Data(contentsOf:destination.appendingPathComponent("existing-save.zgtasave"))==Data("existing save fixture".utf8),"Existing unrelated save retained")
    if success {
     require(try Data(contentsOf:destination.appendingPathComponent("data/common/config.xml"))==Data("ok".utf8))
     require(try Data(contentsOf:destination.appendingPathComponent("data/x64/example.dat"))==Data("123".utf8))
     require(!FileManager.default.fileExists(atPath:destination.appendingPathComponent("unrelated.txt").path))
    }
   }
   Fixture.testCoordination=true
   try install("Game.zip",success:true)
   try install("Game.zip",success:false,cancel:true)
   Fixture.testCoordination=false
   let part2=try Data(contentsOf:root.appendingPathComponent("Split.zip.002"))
   try install("Split.zip.001",success:true)
   require(try Data(contentsOf:root.appendingPathComponent("Split.zip.002"))==part2)
   try install("bad.zip",success:false)
   print("PASS: actual coordinated ZIP/split ZIP reads, writer exclusion and release, parent grant lifetime, pre-existing game replacement, unrelated save/source retention and error cleanup")
   ''')
   shim=APP/'App/GameInstaller/GameInstallerShim'
   headers=os.environ.get('ZGTA_ARCHIVE_HEADERS')
   if not headers: self.skipTest('Set ZGTA_ARCHIVE_HEADERS to the existing libarchive headers; no dependency download is performed')
   built_c=subprocess.run(['/usr/bin/clang','-I',headers,'-c',str(shim.with_suffix('.c')),'-o',str(root/'shim.o')],capture_output=True,text=True)
   self.assertEqual(built_c.returncode,0,built_c.stderr)
   command=['/usr/bin/swiftc','-module-cache-path',str(root/'cache'),'-import-objc-header',str(shim.with_suffix('.h')),*map(str,sorted((APP/'App/GameInstaller').glob('*.swift'))),str(APP/'App/Localization.swift'),str(root/'GameInstall.swift'),str(root/'Support.swift'),str(root/'main.swift'),str(root/'shim.o'),'-larchive','-o',str(root/'install-test')]
   built=subprocess.run(command,capture_output=True,text=True,timeout=120);self.assertEqual(built.returncode,0,built.stderr)
   ran=subprocess.run([str(root/'install-test')],capture_output=True,text=True,timeout=45);self.assertEqual(ran.returncode,0,ran.stderr+ran.stdout);self.assertIn('PASS:',ran.stdout)
if __name__=='__main__':unittest.main()
