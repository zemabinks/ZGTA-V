"""Execute actual Swift RPF views and shipped C inflater; no game/user data writes."""
import hashlib,json,os,struct,subprocess,tempfile,unittest
from pathlib import Path
from test_browser_mods import rpf
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT.parent/'app'
SUPRA=ROOT.parents[2]/'gta-supra-casup-20261024/extracted/[SupraMKv]/Add-on/dlc.rpf'
SWIFT=r'''
import Foundation
import Darwin
enum L10n {
 static let language="en"
 static let translations:[String:[String:String]]=[:]
 static func text(_ value:String,language:String,catalog:[String:[String:String]])->String {value}
}
func storage(_ a:RPFArchive)->Data {
 let f=Mirror(reflecting:a).children
 return (f.first(where:{$0.label=="backing"}) ?? f.first(where:{$0.label=="bytes"})!).value as! Data
}
func address(_ d:Data)->UInt {d.withUnsafeBytes {UInt(bitPattern:$0.baseAddress!)}}
func rejects(_ body:() throws->Void)->Bool {do {try body();return false} catch {return true}}
@main struct Fixture {
 static func main() throws {
  let root=URL(fileURLWithPath:CommandLine.arguments[1]),mode=CommandLine.arguments[2]
  if mode=="summary" {
   let a=try RPFArchive(url:root)
   var report:[String:[Int]]=[:],children:[RPFArchive]=[]
   for e in a.entries {report[e.path]=[e.offset,e.size,e.unpacked,e.encrypted ? 1:0,e.compressed ? 1:0,e.resourceVersion ?? -1]}
   let before=fixture_heap_bytes();var sum=0,same=true
   for e in a.entries where e.path.hasSuffix(".rpf") {
    let child=try a.nested(e);children.append(child);sum+=e.size
    same = same && address(storage(child))==address(storage(a))
    for v in child.entries {report[e.path+":"+v.path]=[v.offset,v.size,v.unpacked,v.encrypted ? 1:0,v.compressed ? 1:0,v.resourceVersion ?? -1]}
   }
   let value:[String:Any]=["entries":report,"sameBacking":same,"nestedBytes":sum,"retainedArchives":children.count,"heapBefore":before,"heapAfter":fixture_heap_bytes()]
   withExtendedLifetime(children) {print(String(data:try! JSONSerialization.data(withJSONObject:value,options:[.sortedKeys]),encoding:.utf8)!)}
   return
  }
  if mode=="pack" {
   let p=try ModPack(url:root)
   print(String(data:try JSONSerialization.data(withJSONObject:["name":p.name,"models":p.models,"vehicles":p.vehicleModels],options:[.sortedKeys]),encoding:.utf8)!);return
  }
  let a=try RPFArchive(url:root.appendingPathComponent("outer.rpf"))
  let b=try a.nested(a.entries.first(where:{$0.path=="middle.rpf"})!)
  let c=try b.nested(b.entries.first(where:{$0.path=="leaf.rpf"})!)
  let e=c.entries.first(where:{$0.path=="vehicles.meta"})!
  let expected=try Data(contentsOf:root.appendingPathComponent("expected.xml"))
  let decoded=try c.metadata(e);precondition(decoded==expected)
  precondition(address(storage(a))==address(storage(b)) && address(storage(b))==address(storage(c)))
  let middle=try Data(contentsOf:root.appendingPathComponent("middle.rpf"))
  let leaf=try Data(contentsOf:root.appendingPathComponent("leaf.rpf"))
  precondition(b.bytes==middle && c.bytes==leaf)
  var mutable=try Data(contentsOf:root.appendingPathComponent("outer.rpf"))
  let immutable=try RPFArchive(bytes:mutable);mutable[0]=0;precondition(immutable.bytes[0]==0x37)
  let prefix=Data(repeating:99,count:17)+immutable.bytes
  let sliced=try RPFArchive(bytes:prefix[17...])
  let slicedChild=try sliced.nested(sliced.entries.first(where:{$0.path=="middle.rpf"})!)
  precondition(slicedChild.bytes==b.bytes)
  for file in ["child-escape.rpf","child-truncated.rpf","child-cycle.rpf","child-names.rpf"] {
   let parent=try RPFArchive(url:root.appendingPathComponent(file))
   precondition(rejects {_ = try parent.nested(parent.entries[0])})
  }
  for file in ["short.rpf","bad-table.rpf","bad-offset.rpf","bad-resource.rpf"] {
   precondition(rejects {_ = try RPFArchive(url:root.appendingPathComponent(file))})
  }
  for file in ["bad-compressed.rpf","wrong-decoded.rpf","trailing-compressed.rpf"] {
   let value=try RPFArchive(url:root.appendingPathComponent(file))
   precondition(rejects {_ = try value.metadata(value.entries[0])})
  }
  for offset in [-1,Int.max] {
   let forged=RPFArchive.Entry(path:"forged",offset:offset,size:1,unpacked:1,encrypted:false,compressed:false,resourceVersion:nil)
   precondition(rejects {_ = try b.nested(forged)});precondition(rejects {_ = try b.metadata(forged)})
  }
  let overflow=RPFArchive.Entry(path:"forged",offset:1,size:Int.max,unpacked:1,encrypted:false,compressed:true,resourceVersion:nil)
  precondition(rejects {_ = try b.metadata(overflow)})
  let compressed=RPFArchive.Entry(path:"forged",offset:0,size:1,unpacked:1,encrypted:false,compressed:true,resourceVersion:nil)
  precondition(rejects {_ = try b.nested(compressed)})
  print("RPF_BOUNDED_VIEWS_PASS")
 }
}
'''
def run(args):
 p=subprocess.run([str(a) for a in args],capture_output=True,text=True,timeout=90)
 if p.returncode:raise AssertionError(p.stdout+'\n'+p.stderr)
 return p.stdout

def build(folder,source=None):
 folder.mkdir(parents=True,exist_ok=True)
 (folder/'main.swift').write_text(SWIFT)
 (folder/'shim.h').write_text('#include <stdint.h>\nint gi_inflate_raw(const void *,uint32_t,void *,uint32_t);\nuint64_t fixture_heap_bytes(void);\n')
 (folder/'GameInstallerShim.h').write_text((folder/'shim.h').read_text())
 (folder/'heap.c').write_text('#include <stdint.h>\n#include <malloc/malloc.h>\nuint64_t fixture_heap_bytes(void){malloc_statistics_t s={0};malloc_zone_statistics(malloc_default_zone(),&s);return s.size_in_use;}\n')
 run(['/usr/bin/clang','-I',folder,'-c',APP/'Source/NativeRPFInflate.c','-o',folder/'inflate.o'])
 run(['/usr/bin/clang','-c',folder/'heap.c','-o',folder/'heap.o'])
 run(['/usr/bin/swiftc','-parse-as-library','-O','-module-cache-path',folder/'cache','-import-objc-header',folder/'shim.h',source or APP/'App/RPFArchive.swift',folder/'main.swift',folder/'inflate.o',folder/'heap.o','-lz','-o',folder/'check'])
 return folder/'check'

def fixtures(root):
 xml=b'<Item><modelName>boundedcar</modelName></Item>'*16
 leaf=rpf({'vehicles.meta':xml},compressed=('vehicles.meta',))
 middle=rpf({'leaf.rpf':leaf,'filler.bin':b'x'*4096})
 outer=rpf({'middle.rpf':middle,'sibling.bin':b'y'*8192})
 for name,data in [('expected.xml',xml),('leaf.rpf',leaf),('middle.rpf',middle),('outer.rpf',outer)]: (root/name).write_bytes(data)
 value=bytearray(leaf);packed=struct.unpack_from('<Q',value,32)[0];struct.pack_into('<Q',value,32,(packed & ((1<<40)-1)) | (3<<40))
 (root/'child-escape.rpf').write_bytes(rpf({'child.rpf':bytes(value),'sibling.bin':b'z'*2000000}))
 (root/'child-truncated.rpf').write_bytes(rpf({'child.rpf':leaf[:30],'sibling.bin':leaf}))
 value=bytearray(leaf);struct.pack_into('<I',value,24,0)
 (root/'child-cycle.rpf').write_bytes(rpf({'child.rpf':bytes(value)}))
 value=bytearray(leaf);struct.pack_into('<I',value,8,0xffffffff)
 (root/'child-names.rpf').write_bytes(rpf({'child.rpf':bytes(value)}))
 (root/'short.rpf').write_bytes(b'RPF')
 value=bytearray(leaf);struct.pack_into('<I',value,4,0xffffffff);(root/'bad-table.rpf').write_bytes(value)
 value=bytearray(leaf);struct.pack_into('<I',value,36,0x7ffffeff);(root/'bad-offset.rpf').write_bytes(value)
 value=bytearray(rpf({'a.yft':b'x'*16},resources={'a.yft':162}));struct.pack_into('<I',value,32,0xffff0001);struct.pack_into('<I',value,36,0xffffff00);(root/'bad-resource.rpf').write_bytes(value)
 value=bytearray(leaf);value[512]=255;(root/'bad-compressed.rpf').write_bytes(value)
 value=bytearray(leaf);struct.pack_into('<I',value,40,len(xml)+1);(root/'wrong-decoded.rpf').write_bytes(value)
 value=bytearray(leaf);packed=struct.unpack_from('<Q',value,32)[0]+(1<<16);struct.pack_into('<Q',value,32,packed);(root/'trailing-compressed.rpf').write_bytes(value)

class RPFViews102(unittest.TestCase):
 def test_bounded_views_actual_parser_and_inflater(self):
  with tempfile.TemporaryDirectory(prefix='zgta-rpf-views102-') as tmp:
   root=Path(tmp);fixtures(root)
   self.assertIn('RPF_BOUNDED_VIEWS_PASS',run([build(root/'compiled'),root,'tests']))
 def test_original_supra_backing_and_metadata_parity(self):
  path=Path(os.environ.get('ZGTA_TEST_SUPRA_RPF',SUPRA))
  if not path.is_file():self.skipTest('Read-only supplied Supra RPF absent; set ZGTA_TEST_SUPRA_RPF')
  before=hashlib.sha256(path.read_bytes()).hexdigest()
  with tempfile.TemporaryDirectory(prefix='zgta-supra-views102-') as tmp:
   exe=build(Path(tmp)/'compiled');summary=json.loads(run([exe,path,'summary']))
   self.assertTrue(summary['sameBacking']);self.assertEqual(summary['retainedArchives'],2)
   actual=json.loads(run([exe,path,'pack']))
   self.assertEqual(actual['vehicles'],['casup']);self.assertEqual(actual['name'],'casup')
   self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
   self.assertGreater(summary['nestedBytes'],20*1024*1024)
   print(json.dumps({'supraSHA256':before,'actualPack':actual,'boundedViews':summary},sort_keys=True))
if __name__=='__main__':unittest.main()
