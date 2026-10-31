"""Execute the actual injected predicate and native/browser GPU state consumers."""
import gzip
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import render_performance
import stipple_gpu


class ExactFadePhase(unittest.TestCase):
    def test_actual_browser_predicate_matches_original_float4_and_legacy(self):
        script = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context={};vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8')+';this.fade=zemaWithStipple',context);
const original='@fragment fn main(@builtin(position) p:vec4<f32>)->@location(0) vec4<f32>{ return vec4<f32>(1); }';
function predicate(code){
 let text=context.fade(original,code), body=text.slice(text.indexOf('{')+1,text.indexOf(' return vec4'));
 body=body.replace(/\bu32\(/g,'Math.trunc(').replace(/\bmax\(/g,'Math.max(').replace(/(\d+)u\b/g,'$1').replace(/discard;/g,'return false;');
 return new Function('p',body+'return true;');
}
let comparisons=0;
const masks=[...Array(2).fill(0),...Array(9).fill(15),...Array(9).fill(0xf00f),...Array(6).fill(0xf0ff),...Array(6).fill(65535)];
for(let alpha=0;alpha<256;alpha++)for(let invert=0;invert<2;invert++){
 const raw=masks[alpha>>3]^(invert?65535:0),fade=[0,1,2,3].map(k=>((raw>>(4*k))&15)/15);
 const phaseBits=fade.reduce((m,v,k)=>m|((v>=1?1:0)<<k),0), keep=predicate(16|phaseBits), other=predicate(16|(phaseBits^15));
 for(let y=0;y<8;y++)for(let x=0;x<8;x++){
  const p={x:x+0.5,y:y+0.5}, phase=(x&1)+2*(y&1),expected=fade[phase]>=1;
  assert.equal(keep(p),expected);assert.notEqual(keep(p),other(p));comparisons++;
 }
}
for(let mask=0;mask<16;mask++){
 const keep=predicate(16|mask);
 for(let y=0;y<2;y++)for(let x=0;x<2;x++)assert.equal(keep({x:x+0.5,y:y+0.5}),!!((mask>>((x&1)+2*(y&1)))&1));
 assert.equal(keep({x:-2.5,y:-1.5}),!!(mask&1),'negative coordinates clamp to zero');
}
for(let level=1;level<16;level++){
 const keep=predicate(level);let n=0;
 for(let y=0;y<4;y++)for(let x=0;x<4;x++){
  const rank=4*((((x^y)&1)<<1)|(y&1))+(((((x^y)>>1)&1)<<1)|(y>>1));
  assert.equal(keep({x:x+0.5,y:y+0.5}),rank<level);n+=keep({x:x+0.5,y:y+0.5});
 }assert.equal(n,level);
}
for(const invalid of [0,32,-1,1.5,NaN])assert.throws(()=>context.fade(original,invalid),/Stipple level/);
assert.equal((context.fade(original,25).match(/@builtin\(position\)/g)||[]).length,1);
assert.match(context.fade('@fragment fn main()->@location(0) vec4<f32>{ return vec4<f32>(1); }',25),/@builtin\(position\) zema_fade_position/);
console.log(JSON.stringify({status:'PASS',originalFloat4Comparisons:comparisons,exactMasks:16,legacyLevels:15}));
'''
        subprocess.run(['node', '-e', script, str(ROOT/'stipple_gpu.js')], check=True)

    def test_actual_browser_packet_range_dirty_and_reset(self):
        fixture = ROOT.parents[1]/'docs/verification/render-performance98/inputs/wgpu_worker97.js.gz'
        if not fixture.is_file():
            self.skipTest('Supply pinned Build97 worker fixture')
        worker = stipple_gpu.apply(render_performance.apply(gzip.decompress(fixture.read_bytes()).decode()))
        begin = worker.index('case 65 /* host STIPPLE */:')
        packet = worker[begin:worker.index('case 0 /* NOP */:', begin)]
        script = r'''
const assert=require('node:assert/strict'),S={stipple:0};let pdirty=false;
const packet=new Function('S','u32','n',`let p=0,pdirty=false;switch(65){${process.argv[1]}}return pdirty;`);
for(let code=0;code<=40;code++){
 const previous=S.stipple,want=code<32?code:0;
 assert.equal(packet(S,new Uint32Array([code]),1),want!==previous);assert.equal(S.stipple,want);
 assert.equal(packet(S,new Uint32Array([code]),1),false);
}
packet(S,new Uint32Array([31]),1);assert.equal(S.stipple,31);
packet(S,new Uint32Array([0]),1);assert.equal(S.stipple,0);
packet(S,new Uint32Array([4294967295]),1);assert.equal(S.stipple,0);
assert.throws(()=>packet(S,new Uint32Array([16]),2),/Malformed/);
console.log('actual browser packet state: PASS');
'''
        subprocess.run(['node', '-e', script, packet], check=True)

    def test_actual_native_packet_and_32bit_variant_bookkeeping(self):
        native = ROOT.parent/'app/Source/MetalRenderer'
        text = (native/'MRRenderer.mm').read_text()
        begin = text.index('case STIPPLE: {')
        packet = text[begin:text.index('case SET_DEPTH_STENCIL:', begin)]
        # Compile the actual switch arm, with a bounded renderer state and logger.
        code = r'''#include <cstdint>
#include <cassert>
struct Renderer { uint32_t stipple=0;bool pipeDirty=false; };
void logOnce(const char*,const char*){}
void packet(Renderer* R,uint32_t code,uint32_t n){
uint32_t data[]={code};const uint32_t* p=data;
enum{STIPPLE=65};switch(STIPPLE){''' + packet + r'''}}
int main(){Renderer r;
for(uint32_t c=0;c<=40;c++){
uint32_t previous=r.stipple,want=c<32?c:0;r.pipeDirty=false;
packet(&r,c,1);assert(r.stipple==want);assert(r.pipeDirty==(previous!=want));
r.pipeDirty=false;packet(&r,c,1);assert(!r.pipeDirty);
}
packet(&r,31,1);assert(r.stipple==31);packet(&r,0,1);assert(r.stipple==0);
packet(&r,0xffffffffu,1);assert(r.stipple==0);
packet(&r,16,2);assert(r.stipple==0);
uint32_t requested=0,failed=0;void* functions[32]={};
for(uint32_t i=1;i<32;i++)requested|=1u<<i;
assert(requested==0xfffffffeu);failed|=1u<<31;assert(failed==0x80000000u);
functions[31]=&r;assert(functions[31]);return 0;}
'''
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'packet.cpp'; binary=source.with_suffix('')
            source.write_text(code)
            subprocess.run(['clang++','-std=c++17','-fsanitize=address,undefined',str(source),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)
        header=(native/'MRInternal.h').read_text(); shaders=(native/'MRShaders.mm').read_text()
        self.assertIn('stippleFunctions[32]',header)
        self.assertIn('uint32_t stippleFailedMask',header)
        self.assertIn('uint32_t stippleRequestedMask',header)
        self.assertIn('stippleFailedMask = UINT32_MAX',shaders)
        self.assertIn('i < 32; i++',shaders)
        self.assertIn('stipple > 31',shaders)
        self.assertIn('stipple < 32 ? stipple : 0',shaders)
        self.assertIn('if (info->stippleFailedMask & (1u << stipple)) return nil;',shaders)


if __name__ == '__main__': unittest.main()
