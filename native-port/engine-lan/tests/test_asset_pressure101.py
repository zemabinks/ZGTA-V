"""Exercise the actual native hint scheduler under changing app headroom."""
from pathlib import Path
import subprocess
import tempfile
import unittest

APP = Path(__file__).resolve().parents[2] / "app"


class AssetPressure101(unittest.TestCase):
    def test_actual_scheduler_preserves_demand_and_modern_reserve(self):
        source = (APP / "Source/NativeAssets.m").read_text()
        scheduler = source[source.index("static bool assetHintsHaveHeadroom(void)"):
                           source.index("// A dedicated consumer keeps processing")]
        fixture = r'''
#import <Foundation/Foundation.h>
#include <assert.h>
#include <stdatomic.h>
#include "NativeAssetHints.h"
#include "NativeAssetWake.h"
#define TARGET_OS_SIMULATOR 0
static int low;
static uint64_t headroom;
int PGIsLowMemoryDevice(void){return low;}
uint64_t os_proc_available_memory(void){return headroom;}
static PGAssetHintQueue normalHints,lowHints;
static _Atomic int activePrefetch,activeSpeculative;
static uint64_t hintsScheduled,hintsCached;
static NSArray *assetFiles;
static NSString *packedRoot=@"/unused";
static bool assetPrefetchRead,assetSpeculativeRead,assetBalancedQOS;
static bool assetEventDriven=true;
static PGAssetWake assetWake=PG_ASSET_WAKE_INITIALIZER;
static dispatch_queue_t prefetchQueue,speculativeQueue;
static NSMutableArray *scheduled;
static unsigned reads,allocations,releases;
static bool lowerAfterFirst,raiseRead;
static uint64_t lowerTo;
static void deferBlock(dispatch_block_t block){[scheduled addObject:[block copy]];}
#define dispatch_async(queue,block) deferBlock(block)
static uint64_t pg_packed_present_bytes(const char*a,const char*b,uint64_t s,uint64_t o,uint64_t n){return 0;}
static int64_t readAsset(uint32_t id,uint64_t offset,uint8_t *bytes,uint32_t length){
 assert(assetPrefetchRead);reads++;
 if(lowerAfterFirst&&reads==1)headroom=lowerTo;
 if(raiseRead)@throw [NSException exceptionWithName:@"ControlledReadError" reason:nil userInfo:nil];
 return length;
}
static void *trackMalloc(size_t n){allocations++;return malloc(n);}
static void trackFree(void *p){if(p)releases++;free(p);}
#define malloc trackMalloc
#define free trackFree
''' + scheduler + r'''
static void reset(bool speculative,uint32_t length){
 assert(activePrefetch==0&&activeSpeculative==0);
 normalHints=(PGAssetHintQueue){0};lowHints=(PGAssetHintQueue){0};
 hintsScheduled=hintsCached=reads=allocations=releases=0;
 scheduled=[NSMutableArray new];lowerAfterFirst=raiseRead=false;
 assetPrefetchRead=assetSpeculativeRead=false;
 pg_asset_hint_push(speculative?&lowHints:&normalHints,(PGAssetHint){.id=0,.offset=0,.length=length,.speculative=speculative});
}
static void runScheduled(void){
 while(scheduled.count){dispatch_block_t block=scheduled[0];[scheduled removeObjectAtIndex:0];block();}
}
int main(void){@autoreleasepool {
 assetFiles=@[@[@"fixture.rpf",@(4ull<<20)]];
 // Equality admits work; a single byte below each existing reserve defers it.
 for(low=0;low<=1;low++){
  uint64_t reserve=(low?512ull:384ull)<<20;
  reset(true,4096);headroom=reserve-1;pumpAssetHints();
  assert(!scheduled.count&&!hintsScheduled&&!allocations&&lowHints.count==1);
  headroom=reserve;pumpAssetHints();assert(scheduled.count==1&&activePrefetch==1&&activeSpeculative==1);
  runScheduled();assert(reads==1&&allocations==1&&releases==1&&!activePrefetch&&!activeSpeculative);
 }
 // A queued normal or speculative job must not allocate/read after pressure changes.
 for(unsigned speculative=0;speculative<=1;speculative++){
  low=1;headroom=600ull<<20;reset(speculative,3u<<20);pumpAssetHints();
  assert(scheduled.count==1&&hintsScheduled==1);
  uint64_t generation=pg_asset_wake_snapshot(&assetWake);
  headroom=(512ull<<20)-1;runScheduled();
  assert(!reads&&!allocations&&!releases&&!activePrefetch&&!activeSpeculative);
  assert(pg_asset_wake_snapshot(&assetWake)==generation+1);
  assert(!assetPrefetchRead&&!assetSpeculativeRead);
  // Recheck during a long hint rather than allocating/reading all its chunks.
  headroom=600ull<<20;reset(speculative,3u<<20);lowerAfterFirst=true;lowerTo=511ull<<20;
  pumpAssetHints();runScheduled();assert(reads==1&&allocations==1&&releases==1);
  assert(!activePrefetch&&!activeSpeculative&&!assetPrefetchRead&&!assetSpeculativeRead);
 }
 // Higher-memory devices retain their original policy in the 384–512 MiB band.
 low=0;headroom=450ull<<20;reset(true,3u<<20);pumpAssetHints();runScheduled();
 assert(reads==3&&allocations==1&&releases==1);
 // The original 384 MiB boundary still applies between modern-device chunks.
 low=0;headroom=450ull<<20;reset(false,3u<<20);lowerAfterFirst=true;lowerTo=(384ull<<20)-1;
 pumpAssetHints();runScheduled();assert(reads==1&&!activePrefetch);
 // Optional reads on Reduced memory stop at four total or one speculative.
 // Normal priority still takes all available slots; queued work is retained.
 for(low=0;low<=1;low++){
  const unsigned total=low?4:16,spec=low?1:4;
  headroom=900ull<<20;reset(false,4096);
  for(unsigned n=1;n<20;n++)pg_asset_hint_push(&normalHints,(PGAssetHint){.id=0,.length=4096});
  pumpAssetHints();assert(scheduled.count==total&&activePrefetch==total&&normalHints.count==20-total);
  runScheduled();assert(reads==total&&!activePrefetch);
  pumpAssetHints();assert(scheduled.count==(20-total<total?20-total:total));runScheduled();
  reset(true,4096);
  for(unsigned n=1;n<8;n++)pg_asset_hint_push(&lowHints,(PGAssetHint){.id=0,.length=4096,.speculative=true});
  pumpAssetHints();assert(scheduled.count==spec&&activeSpeculative==spec&&lowHints.count==8-spec);
  runScheduled();assert(reads==spec&&!activePrefetch&&!activeSpeculative);
 }
 // Existing finally cleanup also owns a failing read.
 low=1;headroom=600ull<<20;reset(true,4096);raiseRead=true;pumpAssetHints();
 bool threw=false;@try{runScheduled();}@catch(NSException*e){threw=true;}
 assert(threw&&reads==1&&allocations==1&&releases==1&&!activePrefetch&&!activeSpeculative);
 assert(!assetPrefetchRead&&!assetSpeculativeRead);
 puts("PASS: actual hint scheduler reserve boundaries, dispatch/chunk pressure changes, modern policy, and exception cleanup.");
}return 0;}
'''
        with tempfile.TemporaryDirectory(prefix="zgta-asset-pressure101-") as tmp:
            root = Path(tmp)
            src, exe = root / "probe.m", root / "probe"
            src.write_text(fixture)
            build = subprocess.run(
                ["xcrun", "clang", "-std=c11", "-O1", "-fobjc-arc", "-fblocks",
                 "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                 "-framework", "Foundation", "-I", str(APP / "Source"),
                 str(src), "-o", str(exe)], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

        # This candidate changes hint scheduling only. Preserve the exact demand
        # source boundary so pressure cannot manufacture a completed demand read.
        demand_start = source.index("static int64_t readLocalAsset(")
        demand_end = source.index("// Health counters", demand_start)
        self.assertNotIn("assetHintsHaveHeadroom", source[demand_start:demand_end])


if __name__ == "__main__":
    unittest.main()
