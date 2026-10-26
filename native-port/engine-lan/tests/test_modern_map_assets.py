"""Real movie/manifest compatibility, sparse AS2 registration and native delta parity."""
import copy,hashlib,importlib.util,json,struct,subprocess,sys,tempfile,unittest,zlib
from pathlib import Path
from public_test_inputs import game_file
ROOT=Path(__file__).resolve().parents[1];APP=ROOT.parent/'app';sys.path.insert(0,str(ROOT));sys.path.insert(0,str(APP/'Scripts'))
import modern_map_assets as runtime
import build_modern_blips as build
MIRROR=game_file('data')

def run_array(body,pool):
    """Minimal independent VM for the actual pinned array-construction bytecode."""
    stack=[];regs={};p=0
    while p<len(body):
        op=body[p];p+=1;n=struct.unpack_from('<H',body,p)[0] if op>=128 else 0;p+=2 if op>=128 else 0;d=body[p:p+n];p+=n
        if op==0x96:
            q=0
            while q<len(d):
                typ=d[q];q+=1
                if typ==0:end=d.index(0,q);v=d[q:end].decode();q=end+1
                elif typ==4:v=regs[d[q]];q+=1
                elif typ==6:v=struct.unpack('<d',d[q+4:q+8]+d[q:q+4])[0];q+=8
                elif typ==7:v=struct.unpack_from('<i',d,q)[0];q+=4
                elif typ==8:v=pool[d[q]];q+=1
                elif typ==9:v=pool[struct.unpack_from('<H',d,q)[0]];q+=2
                else:raise AssertionError(typ)
                stack.append(v)
        elif op==0x40:
            assert stack.pop()=='Array' and stack.pop()==0;stack.append({})
        elif op==0x87:regs[d[0]]=stack[-1]
        elif op==0x17:stack.pop()
        elif op==0x52:
            assert stack.pop()=='push';target=stack.pop();assert stack.pop()==1;value=stack.pop();target[len(target)]=value;stack.append(len(target))
        elif op==0x4f:value=stack.pop();index=stack.pop();target=stack.pop();target[index]=value
        elif op==0x3e:return stack.pop()
        else:raise AssertionError(hex(op))
    raise AssertionError('Missing return')

def decode_bitmap_artwork(encoded):
    """Independently check standard SWF tags, ARGB pixels and bitmap geometry."""
    chunks=list(build.tags(encoded,0));assert [r[1] for r in chunks]==[36,32]
    bitmap,shape=chunks[0][2],chunks[1][2]
    identity,kind,width,height=struct.unpack_from('<HBHH',bitmap)
    assert kind==5 and width==height==32
    raw=zlib.decompress(bitmap[7:]);assert len(raw)==32*32*4
    cursor=2+(5+(shape[2]>>3)*4+7)//8
    assert shape[cursor:cursor+2]==b'\x01\x41'
    assert struct.unpack_from('<H',shape,cursor+2)[0]==identity
    bit=(cursor+4)*8
    def take(n,signed=False):
        nonlocal bit
        v=0
        for _ in range(n):v=(v<<1)|((shape[bit//8]>>(7-bit%8))&1);bit+=1
        return v-(1<<n) if signed and v&(1<<(n-1)) else v
    assert take(1)==1;n=take(5);assert [take(n,True),take(n,True)]==[655360,655360]
    assert take(1)==0;n=take(5);assert [take(n,True),take(n,True)]==[-160,-160]
    bit=(bit+7)//8*8;assert take(8)==0 # no lines
    assert take(4)==1 and take(4)==0 and take(1)==0 and take(5)==5
    n=take(5);assert [take(n,True),take(n,True)]==[-160,-160] and take(1)==1
    edges=[]
    for _ in range(4):
        assert take(1)==1 and take(1)==1;n=take(4)+2;assert take(1)==0
        edges.append((take(1),take(n,True)))
    assert edges==[(0,320),(1,320),(0,-320),(1,-320)] and take(6)==0
    return raw

class ModernMapAssets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patch=json.loads(runtime.PATCH.read_text());cls.original=(MIRROR/runtime.PATH).read_bytes();cls.result=runtime.apply(cls.original,cls.patch)
        cls.crypt=staticmethod(build.codec(MIRROR.parent/'b/8b0b5899ed/game.wasm'))
        count,names_size=struct.unpack_from('<II',cls.original,4)
        table=cls.crypt(cls.original[16:16+count*16],True);names=cls.crypt(cls.original[16+count*16:16+count*16+names_size],True)
        for i in range(count):
            a,b,c,d=struct.unpack_from('<4I',table,i*16)
            if b==0x7fffff00:continue
            at=a&65535
            if names[at:names.index(0,at)]!=b'minimap.gfx':continue
            packed=a|(b<<32);offset=((packed>>40)&0xffffff)*512;length=(packed>>16)&0xffffff
            cls.gfx=zlib.decompress(cls.crypt(cls.original[offset:offset+length],True),-15)
        assert build.sha(cls.gfx)==build.ORIGINAL_GFX

    def test_generator_reproduces_bundled_delta_exactly(self):
        patch,result,movie=build.build(self.original,self.crypt,APP/'Resources/ModernBlips')
        self.assertEqual(patch,self.patch);self.assertEqual(result,self.result)
        self.assertEqual(build.sha(movie),self.patch['updated_movie_sha256'])

    def test_delta_is_bounded_pinned_reversible_and_manifest_keeps_indices(self):
        self.assertEqual(hashlib.sha256(self.original).hexdigest(),runtime.BASE_SHA)
        self.assertEqual(len(self.result),self.patch['result_bytes']);self.assertLess(len(self.result),1048576)
        original_manifest=(MIRROR/'manifest.json').read_bytes();before=json.loads(original_manifest);after=json.loads(runtime.manifest(original_manifest,self.patch))
        self.assertEqual(before['version'],after['version']);self.assertEqual(len(before['files']),len(after['files']))
        for a,b in zip(before['files'],after['files']):
            self.assertEqual(a[0],b[0]);self.assertEqual(a[2:],b[2:])
            if a[0]==runtime.PATH:self.assertEqual(b[1],len(self.result))
            else:self.assertEqual(a,b)
        restored=bytearray(self.result[:len(self.original)])
        for e in self.patch['edits']:restored[e['offset']:e['offset']+16]=bytes.fromhex(e['before'])
        self.assertEqual(bytes(restored),self.original)
        for field,value in [('base_sha256','0'*64),('result_sha256','0'*64),('result_bytes',len(self.original)+512*1024),('append_base64','??')]:
            bad=copy.deepcopy(self.patch);bad[field]=value
            with self.assertRaises((ValueError,TypeError)):runtime.apply(self.original,bad)
        bad=copy.deepcopy(self.patch);bad['edits'][0]['offset']=len(self.original)
        with self.assertRaises(ValueError):runtime.apply(self.original,bad)
        with self.assertRaises(ValueError):runtime.apply(bytes(len(self.original)),self.patch)

    def test_real_sparse_array_preserves_every_original_slot(self):
        # Extracted pinned original class; supplied original movie is an existing local input.
        gfx=self.gfx;at=8+(5+(gfx[8]>>3)*4+7)//8+4
        raw=next(d[2:] for _,t,d,_ in build.tags(gfx,at) if t==59 and build.sha(d[2:])==build.CLASS_SHA)
        count=struct.unpack_from('<H',raw,3)[0];pool=[s.decode() for s in raw[5:5+struct.unpack_from('<H',raw,1)[0]-2].split(b'\0')[:count]]
        old=run_array(raw[0x21b0:0x21b0+7018],pool)
        icons=json.loads((APP/'Resources/ModernBlips/catalog.json').read_text())['icons'];expanded=build.expand_class(raw,icons);size=struct.unpack_from('<H',expanded,0x21ae)[0];new=run_array(expanded[0x21b0:0x21b0+size],pool)
        self.assertEqual(len(old),426);self.assertEqual(len(new),448)
        for k,v in old.items():self.assertEqual(new[k],v)
        for row in icons:self.assertEqual(new[row['id']],row['name'])
        self.assertNotIn(426,new);self.assertNotIn(891,new)
        updated=build.movie(gfx,icons,APP/'Resources/ModernBlips');self.assertEqual(struct.unpack_from('<I',updated,4)[0],len(updated))
        exports=[]
        for _,kind,data,_ in build.tags(updated,at):
            if kind==56:exports.append(data[4:-1].decode())
        for row in icons:self.assertEqual(exports.count(row['name']),1)
        self.assertEqual(len(exports),484+22)

    def test_official_pixels_and_lossless_bitmaps_are_nonempty(self):
        catalog=json.loads((APP/'Resources/ModernBlips/catalog.json').read_text())
        self.assertEqual(len(catalog['icons']),22)
        for row in catalog['icons']:
            raw=(APP/'Resources/ModernBlips'/row['file']).read_bytes();self.assertEqual(build.sha(raw),row['sha256']);pixels=build.rgba(raw)
            self.assertTrue(any(c[3] for line in pixels for c in line))
            self.assertTrue(any(not c[3] for line in pixels for c in line))
            artwork=build.bitmap_artwork(65000,65001,pixels)
            decoded=decode_bitmap_artwork(artwork)
            expected=bytes(v for line in pixels for r,g,b,a in line for v in (a,round(r*a/255),round(g*a/255),round(b*a/255)))
            self.assertEqual(decoded,expected)
        corrupted=bytearray(raw);corrupted[-6]^=1
        with self.assertRaises(ValueError):build.rgba(bytes(corrupted))

    def test_native_apply_and_manifest_preserve_source_mods_and_corruption_refusal(self):
        harness=r'''
import Foundation
@main struct QA {
 static func main() throws {
  let root=URL(fileURLWithPath:CommandLine.arguments[1]), patchURL=URL(fileURLWithPath:CommandLine.arguments[2]), base=URL(fileURLWithPath:CommandLine.arguments[3])
  let decoder=JSONDecoder();decoder.keyDecodingStrategy = .convertFromSnakeCase
  let patch=try decoder.decode(ModernMapIcons.Patch.self,from:Data(contentsOf:patchURL)), original=try Data(contentsOf:base)
  let output=try ModernMapIcons.apply(original,patch:patch);assert(output.count==patch.resultBytes)
  var refused=false;do {_ = try ModernMapIcons.apply(Data(repeating:0,count:original.count),patch:patch)}catch{refused=true};assert(refused)
  let local=root.appendingPathComponent("data"), source=local.appendingPathComponent(ModernMapIcons.archivePath)
  try FileManager.default.createDirectory(at:source.deletingLastPathComponent(),withIntermediateDirectories:true);try original.write(to:source)
  let manifest=root.appendingPathComponent("base.json"), value:[String:Any] = ["version":"unchanged","files":[[ModernMapIcons.archivePath,original.count,123],["keep.rpf",456,789]],"_mugoatOverrides":["keep.rpf":"/custom/keep.rpf"]]
  try JSONSerialization.data(withJSONObject:value).write(to:manifest)
  let updated=try ModernMapIcons.prepare(manifest:manifest,localData:local,runtime:root.appendingPathComponent("cache"),patchURL:patchURL)
  let metadata=try JSONSerialization.jsonObject(with:Data(contentsOf:updated)) as! [String:Any], overrides=metadata["_mugoatOverrides"] as! [String:String]
  let untouched=try Data(contentsOf:source), staged=try Data(contentsOf:URL(fileURLWithPath:overrides[ModernMapIcons.archivePath]!))
  let custom=try ModernMapIcons.prepare(manifest:updated,localData:local,runtime:root,patchURL:patchURL)
  assert(overrides["keep.rpf"]=="/custom/keep.rpf");assert(untouched==original);assert(staged==output);assert(custom==updated)
  print("NATIVE_OFFICIAL_ICON_DELTA_PARITY_PASS")
 }
}
'''
        with tempfile.TemporaryDirectory(prefix='zgta-native-map-') as folder:
            p=Path(folder);(p/'QA.swift').write_text(harness)
            r=subprocess.run(['/usr/bin/xcrun','swiftc','-module-cache-path',str(p/'modules'),str(APP/'App/ModernMapIcons.swift'),str(p/'QA.swift'),'-o',str(p/'qa')],capture_output=True,text=True,timeout=120)
            self.assertEqual(r.returncode,0,r.stderr)
            r=subprocess.run([str(p/'qa'),str(p),str(runtime.PATCH),str(MIRROR/runtime.PATH)],capture_output=True,text=True,timeout=30)
            self.assertEqual(r.returncode,0,r.stderr);self.assertIn('NATIVE_OFFICIAL_ICON_DELTA_PARITY_PASS',r.stdout)

    def test_native_reader_uses_verified_new_size_after_original_preloader(self):
        harness=r'''
#import "NativeModernMapAsset.h"
#include <assert.h>
int main(int argc,const char **argv){@autoreleasepool{
 NSArray *old=@[@[@"x64/data/cdimages/scaleform_minimap.rpf",@720896]];
 BOOL expected=strcmp(argv[2],"valid")==0;
 assert(pg_modern_map_configure(argv[1],old)==expected);
 uint8_t buffer[32];int64_t got=-99;
 assert(!pg_modern_map_read(5,0,buffer,32,&got));
 if(expected){
  uint64_t tail=strtoull(argv[3],NULL,10)-18;
  assert(pg_modern_map_read(0,tail,buffer,32,&got)&&got==18);
  assert(!memcmp(buffer,(const uint8_t *)pg_modern_map_data.bytes+tail,18));
  assert(pg_modern_map_read(0,UINT64_MAX,buffer,32,&got)&&got==0);
  assert(pg_modern_map_read(0,0,buffer,0,&got)&&got==0);
  assert(pg_modern_map_configure("/does-not-exist",old));
 }
 puts("NATIVE_PRELOADER_SIZE_AND_HASH_PASS");
}}
'''
        with tempfile.TemporaryDirectory(prefix='zgta-native-reader-') as folder:
            p=Path(folder);(p/'QA.m').write_text(harness);(p/'archive.rpf').write_bytes(self.result)
            data={'files':[[runtime.PATH,len(self.result)]],'_mugoatOverrides':{runtime.PATH:str(p/'archive.rpf')},'_zemaModernMapIcons':{'sha256':self.patch['result_sha256']}}
            compile=subprocess.run(['/usr/bin/xcrun','clang','-fobjc-arc','-Werror','-Wno-deprecated-declarations','-framework','Foundation','-I',str(APP/'Source'),str(p/'QA.m'),'-o',str(p/'qa')],capture_output=True,text=True,timeout=120)
            self.assertEqual(compile.returncode,0,compile.stderr)
            for mode in ['valid','corrupt_hash','wrong_index','wrong_size']:
                candidate=copy.deepcopy(data)
                if mode=='corrupt_hash':candidate['_zemaModernMapIcons']['sha256']='0'*64
                if mode=='wrong_index':candidate['files'].insert(0,['unrelated.rpf',99])
                if mode=='wrong_size':candidate['files'][0][1]=720896
                (p/'manifest.json').write_text(json.dumps(candidate))
                r=subprocess.run([str(p/'qa'),str(p/'manifest.json'),mode,str(len(self.result))],capture_output=True,text=True,timeout=30)
                self.assertEqual(r.returncode,0,r.stderr);self.assertIn('NATIVE_PRELOADER_SIZE_AND_HASH_PASS',r.stdout)

if __name__=='__main__':unittest.main()
