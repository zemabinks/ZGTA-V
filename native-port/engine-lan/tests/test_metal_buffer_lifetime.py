"""GPU completion safety and actual command-loop temporary-resource lifetime."""
from pathlib import Path
import subprocess
import tempfile
import unittest

APP=Path(__file__).resolve().parents[2]/'app'

class MetalBufferLifetime(unittest.TestCase):
    def test_reuse_waits_for_gpu_and_stays_bounded_under_streaming_churn(self):
        with tempfile.TemporaryDirectory(prefix='zema-buffer-pool-') as d:
            binary=Path(d)/'fixture'
            subprocess.run(['/usr/bin/clang++','-std=c++17','-Wall','-Wextra','-Werror',
                            str(APP/'Tests/buffer_pool.cpp'),'-o',str(binary)],check=True,capture_output=True,text=True)
            subprocess.run([str(binary)],check=True,capture_output=True,text=True,timeout=10)

    def test_actual_ring_loop_drains_temporaries_and_preserves_command_order(self):
        source=(APP/'Source/MetalRenderer/MRRenderer.mm').read_text()
        loop=source[source.index('static void loop() {'):source.index('// ---- startup')]
        fixture=r'''
#import <Foundation/Foundation.h>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <stdexcept>
#include <vector>
static unsigned live=0,peak=0,notifications=0;
@interface Temporary : NSObject @end
@implementation Temporary
- (instancetype)init { self=[super init];if(self){live++;if(live>peak)peak=live;}return self; }
- (void)dealloc { live--;[super dealloc]; }
@end
struct PGGraphicsProgress { enum Phase { RingIdle };void phase(Phase){}void executing(uint32_t,uint32_t){} } graphicsProgress;
struct Renderer { uint8_t* mem;uint64_t ring=0;std::vector<int> pendingQueries;double lastCommitMs=0,busyMs=0;struct {double idle=0;} work; };
static Renderer* R;static const uint32_t RING_DATA=64,WRAP=1;static const int CIdle=0;
static double nowMs(){return 1;}static void report(){}static void commit(int){}
static void PGGraphicsNotify(uint64_t){notifications++;}
static void PGGraphicsWait(uint64_t,uint32_t,int64_t){throw std::runtime_error("done");}
static unsigned consumed=0;
static void execute(uint32_t op,const uint32_t*,uint32_t n){
 assert(n==0&&op==100+consumed);consumed++;[[[Temporary alloc]init]autorelease];
}
'''+loop+r'''
int main(){@autoreleasepool {
 alignas(8) uint8_t memory[64+1025*8]={};Renderer renderer;R=&renderer;R->mem=memory;
 auto* hdr=(std::atomic<uint32_t>*)memory;hdr[0].store(sizeof memory);
 auto* words=(uint32_t*)(memory+64);for(unsigned i=0;i<1025;i++){words[i*2]=100+i;words[i*2+1]=0;}
 try{loop();assert(false);}catch(const std::runtime_error&){}
 assert(consumed==1025);assert(hdr[1].load()==sizeof memory);assert(hdr[3].load()==1025);
 assert(notifications>=3);assert(live==0);
 fprintf(stderr,"commands=%u peak-temporaries=%u\n",consumed,peak);return peak<=512?0:3;
}}
'''
        with tempfile.TemporaryDirectory(prefix='zema-metal-loop-') as d:
            path=Path(d);(path/'fixture.mm').write_text(fixture)
            compiled=subprocess.run(['/usr/bin/clang++','-std=c++17','-fno-objc-arc','-framework','Foundation',
                            str(path/'fixture.mm'),'-o',str(path/'fixture')],capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            result=subprocess.run([str(path/'fixture')],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
