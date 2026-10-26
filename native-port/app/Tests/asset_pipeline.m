#import <Foundation/Foundation.h>
#include "HostInternal.h"
#include "WasmFutex.h"
#include "wasm-rt-impl.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#undef wasm_rt_impl_try
#define wasm_rt_impl_try() 0
void pg_log(const char *message){fprintf(stderr,"[asset-probe] %s\n",message);}
void *pg_pointer(struct w2c_env *host,uint64_t address,uint64_t bytes){abort();}
wasm_rt_shared_memory_t *w2c_env_memory(struct w2c_env *host){return &host->memory;}
uint32_t pg_atomic_wait32(wasm_rt_shared_memory_t *m,uint64_t a,uint32_t v,uint64_t t){return 0;}
uint32_t pg_atomic_notify(wasm_rt_shared_memory_t *m,uint64_t a,uint32_t n){return 0;}
#define PG_ASSET_TEST_HOOK 1
#include "../Source/NativeAssets.m"
static dispatch_semaphore_t fillStarted,fillRelease;
static _Atomic unsigned pausedFills;
static _Atomic unsigned normalQOSSeen,speculativeQOSSeen;
static void recordHintQOS(uint32_t id,uint64_t offset){
 if(assetPrefetchRead){qos_class_t qos=QOS_CLASS_UNSPECIFIED;assert(!pthread_get_qos_class_np(pthread_self(),&qos,NULL));atomic_store(assetSpeculativeRead?&speculativeQOSSeen:&normalQOSSeen,(unsigned)qos);}
}
static void pauseFill(uint32_t id,uint64_t offset){
 if(offset==16384&&atomic_fetch_add(&pausedFills,1)==0){dispatch_semaphore_signal(fillStarted);dispatch_semaphore_wait(fillRelease,DISPATCH_TIME_FOREVER);}
}
static void failFill(uint32_t id,uint64_t offset){@throw [NSException exceptionWithName:@"ProbeFillFailure" reason:@"Controlled cleanup check" userInfo:nil];}
int main(void){@autoreleasepool {
 NSString *token=NSUUID.UUID.UUIDString;
 NSString *name=[NSString stringWithFormat:@"_codex_asset_probe_%@.bin",token];
 NSString *served=[[[NSString stringWithUTF8String:getenv("PG_LOCAL_MIRROR")?:"."] stringByAppendingPathComponent:@"data"] stringByAppendingPathComponent:name];
 NSString *temporary=[NSTemporaryDirectory() stringByAppendingPathComponent:[@"playgta-asset-probe-" stringByAppendingString:token]];
 NSMutableData *fixture=[NSMutableData dataWithLength:2*1024*1024+123];uint8_t *original=fixture.mutableBytes;
 for(NSUInteger i=0;i<fixture.length;i++)original[i]=(uint8_t)(i*17^(i>>8));
 assert([fixture writeToFile:served options:NSDataWritingAtomic error:nil]);
 fprintf(stderr,"[asset-probe] fixture %s\n",served.fileSystemRepresentation);
 @try {
  assetFiles=@[@[name,@(fixture.length)]];assetLocks=@[[PGAssetCondition new]];
  cacheRoot=temporary;packedRoot=[temporary stringByAppendingPathComponent:@"Packed-v1"];
  NSString *legacy=[temporary stringByAppendingPathComponent:@"0"];
  assert([[NSFileManager defaultManager] createDirectoryAtPath:legacy withIntermediateDirectories:YES attributes:nil error:nil]);
  assert([[NSFileManager defaultManager] createDirectoryAtPath:packedRoot withIntermediateDirectories:YES attributes:nil error:nil]);
  assert([[fixture subdataWithRange:NSMakeRange(0,4096)] writeToFile:[legacy stringByAppendingPathComponent:@"0"] options:NSDataWritingAtomic error:nil]);
  NSURLSessionConfiguration *configuration=[NSURLSessionConfiguration ephemeralSessionConfiguration];configuration.timeoutIntervalForRequest=10;
  assetSession=[NSURLSession sessionWithConfiguration:configuration];atomic_store(&nextReport,UINT64_MAX);atomic_store(&fetchedBytes,0);
  uint8_t *bytes=malloc(fixture.length);assert(bytes);
  assert(readAsset(0,127,bytes,2000)==2000&&!memcmp(bytes,original+127,2000)&&atomic_load(&fetchedBytes)==0);
  assert(readAsset(0,4000,bytes,5000)==5000&&!memcmp(bytes,original+4000,5000)&&atomic_load(&fetchedBytes)==8192);
  assert(readAsset(0,4000,bytes,5000)==5000&&!memcmp(bytes,original+4000,5000)&&atomic_load(&fetchedBytes)==8192);
  uint32_t length=(uint32_t)fixture.length-32768;
  assert(readAsset(0,32768,bytes,length)==length&&!memcmp(bytes,original+32768,length));
  uint64_t fetched=atomic_load(&fetchedBytes);assert(fetched<fixture.length);
  assert(readAsset(0,32768,bytes,length)==length&&!memcmp(bytes,original+32768,length)&&atomic_load(&fetchedBytes)==fetched);
  // Simulate a network fill holding this archive's writer lock. A cached read
  // must finish while a missing read waits, then both return exact bytes.
  PGAssetCondition *writer=assetLocks[0];[writer lock];
  dispatch_semaphore_t hotDone=dispatch_semaphore_create(0),coldStarted=dispatch_semaphore_create(0),coldDone=dispatch_semaphore_create(0);
  __block BOOL hotCorrect=NO,coldCorrect=NO;
  dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{@autoreleasepool {
   uint8_t cached[5000];hotCorrect=readAsset(0,4000,cached,sizeof cached)==sizeof cached&&!memcmp(cached,original+4000,sizeof cached);dispatch_semaphore_signal(hotDone);
  }});
  dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{@autoreleasepool {
   uint8_t missing[4096];dispatch_semaphore_signal(coldStarted);coldCorrect=readAsset(0,12288,missing,sizeof missing)==sizeof missing&&!memcmp(missing,original+12288,sizeof missing);dispatch_semaphore_signal(coldDone);
  }});
  long started=dispatch_semaphore_wait(coldStarted,dispatch_time(DISPATCH_TIME_NOW,2*NSEC_PER_SEC));
  long hotResult=dispatch_semaphore_wait(hotDone,dispatch_time(DISPATCH_TIME_NOW,2*NSEC_PER_SEC));
  long coldWaiting=dispatch_semaphore_wait(coldDone,dispatch_time(DISPATCH_TIME_NOW,100*NSEC_PER_MSEC));
  [writer unlock];
  assert(!started&&!hotResult&&hotCorrect&&coldWaiting);
  assert(!dispatch_semaphore_wait(coldDone,dispatch_time(DISPATCH_TIME_NOW,15*NSEC_PER_SEC))&&coldCorrect);
  assert(atomic_load(&fetchedBytes)==fetched+4096);
  // Hold one actual network fill before its fetch. A disjoint cache miss in
  // the same archive finishes, while an overlapping miss shares that fill.
  fillStarted=dispatch_semaphore_create(0);fillRelease=dispatch_semaphore_create(0);assetFillTestHook=pauseFill;
  dispatch_semaphore_t firstDone=dispatch_semaphore_create(0),otherDone=dispatch_semaphore_create(0),sameDone=dispatch_semaphore_create(0),sameStarted=dispatch_semaphore_create(0);
  __block BOOL firstCorrect=NO,otherCorrect=NO,sameCorrect=NO;
  dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{@autoreleasepool {uint8_t data[4096];firstCorrect=readAsset(0,16384,data,sizeof data)==sizeof data&&!memcmp(data,original+16384,sizeof data);dispatch_semaphore_signal(firstDone);}});
  assert(!dispatch_semaphore_wait(fillStarted,dispatch_time(DISPATCH_TIME_NOW,2*NSEC_PER_SEC)));
  dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{@autoreleasepool {uint8_t data[4096];otherCorrect=readAsset(0,24576,data,sizeof data)==sizeof data&&!memcmp(data,original+24576,sizeof data);dispatch_semaphore_signal(otherDone);}});
  dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{@autoreleasepool {uint8_t data[4096];dispatch_semaphore_signal(sameStarted);sameCorrect=readAsset(0,16384,data,sizeof data)==sizeof data&&!memcmp(data,original+16384,sizeof data);dispatch_semaphore_signal(sameDone);}});
  long sameLaunched=dispatch_semaphore_wait(sameStarted,dispatch_time(DISPATCH_TIME_NOW,2*NSEC_PER_SEC));
  long otherResult=dispatch_semaphore_wait(otherDone,dispatch_time(DISPATCH_TIME_NOW,5*NSEC_PER_SEC));
  long sameWaiting=dispatch_semaphore_wait(sameDone,dispatch_time(DISPATCH_TIME_NOW,100*NSEC_PER_MSEC));
  dispatch_semaphore_signal(fillRelease);
  assert(!sameLaunched&&!otherResult&&otherCorrect&&sameWaiting);
  assert(!dispatch_semaphore_wait(firstDone,dispatch_time(DISPATCH_TIME_NOW,15*NSEC_PER_SEC))&&firstCorrect);
  assert(!dispatch_semaphore_wait(sameDone,dispatch_time(DISPATCH_TIME_NOW,15*NSEC_PER_SEC))&&sameCorrect);
  assetFillTestHook=NULL;assert(atomic_load(&pausedFills)==1&&atomic_load(&fetchedBytes)==fetched+3*4096&&writer.flights.count==0);
  // Failure must release the flight, mapping and lock before retry.
  assetFillTestHook=failFill;BOOL threw=NO;@try{readAsset(0,28672,bytes,4096);}@catch(NSException *exception){threw=YES;}
  assetFillTestHook=NULL;assert(threw&&writer.flights.count==0);
  dispatch_semaphore_t lockAvailable=dispatch_semaphore_create(0);
  dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{[writer lock];[writer unlock];dispatch_semaphore_signal(lockAvailable);});
  assert(!dispatch_semaphore_wait(lockAvailable,dispatch_time(DISPATCH_TIME_NOW,2*NSEC_PER_SEC)));
  assert(readAsset(0,28672,bytes,4096)==4096&&!memcmp(bytes,original+28672,4096));
  assert(readAsset(0,fixture.length,bytes,10)==0&&readAsset(1,0,bytes,4)==-1&&readAsset(0,0,bytes,0)==0);
  // An unusable packed path preserves the original cache read path.
  NSString *savedPackedRoot=packedRoot;packedRoot=[temporary stringByAppendingPathComponent:@"not-a-directory"];
  assert([[NSData data] writeToFile:packedRoot options:NSDataWritingAtomic error:nil]);
  assert(readAsset(0,7,bytes,100)==100&&!memcmp(bytes,original+7,100));packedRoot=savedPackedRoot;
  // Exercise the actual scheduler with a >512 KB normal announcement and a
  // bit-30 speculative announcement. A fully cached hint starts no download.
  assetFiles=@[@[name,@(fixture.length)],@[name,@(fixture.length)]];assetLocks=@[writer,[PGAssetCondition new]];
  assetBalancedQOS=[NSProcessInfo.processInfo.arguments containsObject:@"--balanced-asset-qos"];
  prefetchQueue=dispatch_queue_create("playgta5.asset-hint-probe",assetBalancedQOS?dispatch_queue_attr_make_with_qos_class(DISPATCH_QUEUE_CONCURRENT,QOS_CLASS_UTILITY,0):DISPATCH_QUEUE_CONCURRENT);
  speculativeQueue=assetBalancedQOS?dispatch_queue_create("playgta5.asset-speculation-probe",dispatch_queue_attr_make_with_qos_class(DISPATCH_QUEUE_CONCURRENT,QOS_CLASS_BACKGROUND,0)):prefetchQueue;
  assetFillTestHook=recordHintQOS;
  uint64_t beforeHints=atomic_load(&fetchedBytes);PGAssetHint hint;
  assert(pg_asset_hint_decode(1,0,(uint32_t)fixture.length,&hint));pg_asset_hint_push(&normalHints,hint);
  assert(pg_asset_hint_decode(0,32768,(uint32_t)fixture.length-32768,&hint));pg_asset_hint_push(&normalHints,hint);
  assert(pg_asset_hint_decode(0,20480,0x40000000|4096,&hint));pg_asset_hint_push(&lowHints,hint);
  pumpAssetHints();double deadline=assetNowMS()+15000;
  while(atomic_load(&activePrefetch)&&assetNowMS()<deadline)usleep(1000);
  assert(!atomic_load(&activePrefetch)&&!atomic_load(&activeSpeculative)&&normalHints.count==0&&lowHints.count==0&&hintsScheduled==2&&hintsCached==1);
  assert(atomic_load(&fetchedBytes)==beforeHints+fixture.length+4096);
  assetFillTestHook=NULL;
  if(assetBalancedQOS){assert(atomic_load(&normalQOSSeen)==QOS_CLASS_UTILITY&&atomic_load(&speculativeQOSSeen)==QOS_CLASS_BACKGROUND);puts("PASS: actual scheduled normal/speculative jobs execute at utility/background QoS.");}
  NSString *one=[packedRoot stringByAppendingPathComponent:@"1"];
  assert(pg_packed_present_bytes([one stringByAppendingString:@".data"].fileSystemRepresentation,[one stringByAppendingString:@".map"].fileSystemRepresentation,fixture.length,0,fixture.length)==fixture.length);
  assert(readAsset(1,fixture.length-123,bytes,123)==123&&!memcmp(bytes,original+fixture.length-123,123)&&atomic_load(&fetchedBytes)==beforeHints+fixture.length+4096);
  free(bytes);[assetSession invalidateAndCancel];
  puts("PASS: real HTTPS ranges, exact cache bytes, migration/fallback, concurrent disjoint fills, shared overlaps, exception cleanup, production hint scheduler with full ranges/bit-30 flags, and cached hint skipping.");
 } @finally {
  [[NSFileManager defaultManager] removeItemAtPath:served error:nil];
  [[NSFileManager defaultManager] removeItemAtPath:temporary error:nil];
 }
}return 0;}
