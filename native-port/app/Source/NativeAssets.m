#import <Foundation/Foundation.h>
#include <TargetConditionals.h>
#include "HostInternal.h"
#include "WasmFutex.h"
#include "wasm-rt-impl.h"
#include <pthread.h>
#include <limits.h>
#include <fcntl.h>
#include <unistd.h>
#include <os/proc.h>
#include "NativePackedAssetCache.h"
#include "NativeAssetPreload.h"
#include "NativeFeedWidth.h"
#include "NativeAssetRead.h"

// A language choice requested by the native app when the WASM engine boots.
// This does not guarantee the underlying web game uses the locale or has the necessary fonts.
const char *PGSelectedGameLanguage(void) {
  NSString *chosen = [[NSUserDefaults standardUserDefaults] stringForKey:@"gtaPortAppLanguage"];
  static const char *supported[] = {
    "en-US", "fr-FR", "it-IT", "de-DE", "es-ES", "ja-JP", "ko-KR",
    "pl-PL", "pt-BR", "ru-RU", "zh-CN", "es-MX", "zh-TW"
  };
  if (chosen != nil) {
    for (size_t i = 0; i < sizeof(supported)/sizeof(supported[0]); ++i) {
      if ([chosen isEqualToString:[NSString stringWithUTF8String:supported[i]]]) return supported[i];
    }
  }
  return "en-US";
}

// The server that holds your own copy of the game files (set in the app).
static NSString *assetServer=@"";
void PGSetAssetServer(const char *url){
  NSString *value=[[NSString stringWithUTF8String:url?url:""] stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet];
  while([value hasSuffix:@"/"])value=[value substringToIndex:value.length-1];
  assetServer=value;
}
NSString *PGAssetServer(void){return assetServer;}

// A folder on this device with the game's data/ files (chosen in the app):
// every asset read goes straight to the file; no server, no download cache.
static NSString *localDataRoot;
void PGSetLocalGameFolder(const char *dataPath){
  localDataRoot=dataPath&&*dataPath?[NSString stringWithUTF8String:dataPath]:nil;
  if(localDataRoot)pg_log("Game files are read from the folder on this device; no server is used.");
}
bool PGUsingLocalGameFolder(void){return localDataRoot!=nil;}
#include "NativeAssetHints.h"

@interface PGAssetCondition : NSCondition { @public _Atomic bool overrideReadReported; }
@property(nonatomic,strong) NSMutableArray<NSArray<NSNumber *> *> *flights;
@end
@implementation PGAssetCondition
- (instancetype)init {if((self=[super init]))_flights=[NSMutableArray array];return self;}
@end

static NSArray *assetFiles;
static uint32_t feedWidthAssetID=UINT32_MAX;
static NSData *feedWidthData;
static NSString *assetVersion;
static NSDictionary<NSString *, NSString *> *assetOverrides;
static bool assetHasModPacks;
bool pg_assets_have_mod_packs(void){return assetHasModPacks;}
static NSArray<PGAssetCondition *> *assetLocks;
static NSString *cacheRoot;
static NSURLSession *assetSession;
static struct w2c_env *assetHost;
static uint64_t assetTable;
static _Atomic uint64_t fetchedBytes;
static _Atomic uint64_t nextReport;
static _Atomic int activePrefetch;
static _Atomic int activeSpeculative;
static dispatch_queue_t prefetchQueue,speculativeQueue;
static bool assetBalancedQOS;
static NSString *packedRoot;
static int assetTraceFD=-1;
static int assetTimingFD=-1;
static _Atomic uint64_t assetTimingRecords;
static bool assetStreamSimulation,assetConcurrentFills=true;
static unsigned assetSimulatedLatencyMS;
static _Thread_local bool assetPrefetchRead;
static _Thread_local bool assetSpeculativeRead;
static bool assetQueuedHints=true;
static PGAssetHintQueue normalHints,lowHints;
static uint64_t hintsNormalSeen,hintsLowSeen,hintsScheduled,hintsCached,hintsLapped;
static _Thread_local double assetReadNetworkMS,assetReadLockMS;
static _Thread_local uint64_t assetReadNetworkBytes;
static _Thread_local unsigned assetReadSource;
static _Thread_local bool assetSizeMismatch;
static double assetNowMS(void){return NSProcessInfo.processInfo.systemUptime*1000;}
#ifdef PG_ASSET_TEST_HOOK
static void (*assetFillTestHook)(uint32_t,uint64_t);
#endif
static BOOL assetBlockInFlight(PGAssetCondition *condition,uint64_t block){
  for(NSArray<NSNumber *> *range in condition.flights)if(block>=range[0].unsignedLongLongValue&&block<range[1].unsignedLongLongValue)return YES;
  return NO;
}

static _Atomic bool assetsConfigured;
#include "NativeModernMapAsset.h"
void pg_assets_configure(const char *manifest,const char *root) {
  // The Settings preloader may configure the same cache before Play; the
  // engine's later call then reuses it (same manifest and root).
  // Settings may have initialized the original manifest already. The immutable
  // UI override uses its own verified size and never rewrites that cache.
  pg_modern_map_configure(manifest,assetFiles);
  if(atomic_exchange(&assetsConfigured,true))return;
  @autoreleasepool {
    NSData *data=[NSData dataWithContentsOfFile:@(manifest)];
    NSDictionary *parsed=[NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
    assetFiles=parsed[@"files"];
    feedWidthAssetID=UINT32_MAX;feedWidthData=nil;
    for(NSUInteger i=0;i<assetFiles.count;i++)if([assetFiles[i][0] caseInsensitiveCompare:@"common/data/ui/frontend.xml"]==NSOrderedSame){feedWidthAssetID=(uint32_t)i;break;}
    assetVersion=parsed[@"version"];
    assetOverrides=parsed[@"_mugoatOverrides"];
    for(NSString *path in assetOverrides)if([path.lowercaseString containsString:@"/dlcpacks/"]&&[path.lowercaseString hasSuffix:@"/dlc.rpf"])assetHasModPacks=true;
    if(assetOverrides.count){NSString *line=[NSString stringWithFormat:@"Native asset registry: %lu files, %lu local overrides, vehicle packs %@.",(unsigned long)assetFiles.count,(unsigned long)assetOverrides.count,assetHasModPacks?@"present":@"absent"];pg_log(line.UTF8String);}
    NSMutableArray *locks=[NSMutableArray arrayWithCapacity:assetFiles.count];
    for(NSUInteger i=0;i<assetFiles.count;i++)[locks addObject:[PGAssetCondition new]];
    assetLocks=locks;
    cacheRoot=[[@(root) stringByDeletingLastPathComponent] stringByAppendingPathComponent:[@"AssetCache-" stringByAppendingString:parsed[@"version"]?:@"current"]];
    assetConcurrentFills=![NSProcessInfo.processInfo.arguments containsObject:@"--serialized-asset-fills"];
    assetQueuedHints=![NSProcessInfo.processInfo.arguments containsObject:@"--reference-asset-hints"];
    assetBalancedQOS=![NSProcessInfo.processInfo.arguments containsObject:@"--unbalanced-asset-qos"];
#if TARGET_OS_SIMULATOR
    assetStreamSimulation=[NSProcessInfo.processInfo.arguments containsObject:@"--stream-assets"];
    const char *tag=getenv("PG_ASSET_CACHE_TAG");
    if(assetStreamSimulation&&tag&&*tag){NSString *name=@(tag);NSCharacterSet *allowed=[NSCharacterSet characterSetWithCharactersInString:@"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"];
      if(name.length<=64&&[name rangeOfCharacterFromSet:allowed.invertedSet].location==NSNotFound)cacheRoot=[cacheRoot stringByAppendingFormat:@"-%@",name];}
    const char *latency=getenv("PG_ASSET_LATENCY_MS");if(assetStreamSimulation&&latency)assetSimulatedLatencyMS=(unsigned)MIN(2000,MAX(0,atoi(latency)));
    if(assetStreamSimulation){char mode[160];snprintf(mode,sizeof mode,"Simulator asset streaming enabled: %u ms injected latency, concurrent fills %u.",assetSimulatedLatencyMS,assetConcurrentFills);pg_log(mode);}
#endif
    [[NSFileManager defaultManager] createDirectoryAtPath:cacheRoot withIntermediateDirectories:YES attributes:nil error:nil];
    [[NSURL fileURLWithPath:cacheRoot] setResourceValue:@YES forKey:NSURLIsExcludedFromBackupKey error:nil];
    packedRoot=[cacheRoot stringByAppendingPathComponent:@"Packed-v1"];
    [[NSFileManager defaultManager] createDirectoryAtPath:packedRoot withIntermediateDirectories:YES attributes:nil error:nil];
    const char *trace=getenv("PG_NATIVE_ASSET_TRACE");
    if(trace&&atoi(trace)){
      NSString *tracePath=[[@(root) stringByDeletingLastPathComponent] stringByAppendingPathComponent:@"native-asset-ranges.csv"];
      assetTraceFD=open(tracePath.fileSystemRepresentation,O_WRONLY|O_CREAT|O_TRUNC|O_APPEND,0600);
      if(assetTraceFD>=0)pg_log("Recording native startup asset ranges.");
    }
    const char *timing=getenv("PG_ASSET_IO_TRACE");
    if(timing&&atoi(timing)){
      NSString *timingPath=[[@(root) stringByDeletingLastPathComponent] stringByAppendingPathComponent:@"native-asset-timings.csv"];
      assetTimingFD=open(timingPath.fileSystemRepresentation,O_WRONLY|O_CREAT|O_TRUNC|O_APPEND,0600);
      if(assetTimingFD>=0){const char *header="start_ms,end_ms,id,offset,length,result,source,prefetch,network_ms,lock_ms,network_bytes\n";write(assetTimingFD,header,strlen(header));}
    }
    NSURLSessionConfiguration *config=[NSURLSessionConfiguration ephemeralSessionConfiguration];
    config.HTTPMaximumConnectionsPerHost=assetQueuedHints?16:8;config.timeoutIntervalForRequest=25;config.timeoutIntervalForResource=60;
    assetSession=[NSURLSession sessionWithConfiguration:config];
    atomic_store(&nextReport,25*1024*1024);
    prefetchQueue=dispatch_queue_create("playgta5.assets.prefetch",assetBalancedQOS?dispatch_queue_attr_make_with_qos_class(DISPATCH_QUEUE_CONCURRENT,QOS_CLASS_UTILITY,0):DISPATCH_QUEUE_CONCURRENT);
    speculativeQueue=assetBalancedQOS?dispatch_queue_create("playgta5.assets.speculation",dispatch_queue_attr_make_with_qos_class(DISPATCH_QUEUE_CONCURRENT,QOS_CLASS_BACKGROUND,0)):prefetchQueue;
    pg_log(assetBalancedQOS?"Native background asset priorities: utility hints, background speculation (opt-in).":"Native background asset priorities: original.");
#if TARGET_OS_SIMULATOR
    // Simulator profiling: PG_LOCAL_MIRROR (folder with data/) reads the Mac's copy directly.
    const char *mirror=getenv("PG_LOCAL_MIRROR");
    if(!localDataRoot&&!assetStreamSimulation&&mirror)localDataRoot=[[NSString stringWithUTF8String:mirror] stringByAppendingPathComponent:@"data"];
#endif
    if(!localDataRoot)[[assetSession dataTaskWithURL:[NSURL URLWithString:[assetServer stringByAppendingString:@"/data/manifest.json"]] completionHandler:^(NSData *body,NSURLResponse *response,NSError *error){
      if(error){NSString *message=[@"Asset server connection failed: " stringByAppendingString:error.localizedDescription];pg_log(message.UTF8String);}
      else if([(NSHTTPURLResponse *)response statusCode]==200){pg_log("Connected to the asset server.");}
      else {NSString *message=[NSString stringWithFormat:@"Asset server probe HTTP %ld, URL %@, server %@",(long)[(NSHTTPURLResponse *)response statusCode],response.URL,[(NSHTTPURLResponse *)response valueForHTTPHeaderField:@"Server"]];pg_log(message.UTF8String);}
    }] resume];
  }
}
static NSData *fetchRangeImpl(NSString *path,uint64_t offset,uint64_t length,uint64_t *actualSize) {
  NSString *escaped=[path stringByAddingPercentEncodingWithAllowedCharacters:[NSCharacterSet URLPathAllowedCharacterSet]];
  NSURL *url=[NSURL URLWithString:[[assetServer stringByAppendingString:@"/data/"] stringByAppendingString:escaped]];
  NSMutableURLRequest *request=[NSMutableURLRequest requestWithURL:url];
  [request setValue:[NSString stringWithFormat:@"bytes=%llu-%llu",offset,offset+length-1] forHTTPHeaderField:@"Range"];
  dispatch_semaphore_t done=dispatch_semaphore_create(0);
  __block NSData *received=nil;__block NSHTTPURLResponse *reply=nil;__block NSError *failure=nil;
  NSURLSessionDataTask *task=[assetSession dataTaskWithRequest:request completionHandler:^(NSData *data,NSURLResponse *response,NSError *error){received=data;reply=(NSHTTPURLResponse *)response;failure=error;dispatch_semaphore_signal(done);}];
  task.priority=assetSpeculativeRead?NSURLSessionTaskPriorityLow:assetPrefetchRead?NSURLSessionTaskPriorityDefault:NSURLSessionTaskPriorityHigh;
  if(assetSimulatedLatencyMS)usleep(assetSimulatedLatencyMS*1000);
  [task resume];dispatch_semaphore_wait(done,DISPATCH_TIME_FOREVER);
  if(failure){pg_log(failure.localizedDescription.UTF8String);return nil;}
  NSString *range=[reply valueForHTTPHeaderField:@"Content-Range"];
  NSString *total=[[range componentsSeparatedByString:@"/"] lastObject];
  if(total.length&&![total isEqualToString:@"*"])*actualSize=strtoull(total.UTF8String,NULL,10);
  if(reply.statusCode==416)return [NSData data];
  if(reply.statusCode!=206){NSString *message=[NSString stringWithFormat:@"Asset range HTTP %ld, URL %@, server %@",(long)reply.statusCode,reply.URL,[reply valueForHTTPHeaderField:@"Server"]];pg_log(message.UTF8String);return nil;}
  uint64_t sum=atomic_fetch_add(&fetchedBytes,received.length)+received.length;
  assetReadNetworkBytes+=received.length;assetReadSource=3;
  uint64_t report=atomic_load(&nextReport);
  if(sum>=report&&atomic_compare_exchange_strong(&nextReport,&report,report+25*1024*1024)){
    char line[128];snprintf(line,sizeof line,"Native asset cache: %.1f MB downloaded.",sum/1048576.0);pg_log(line);
  }
  return received;
}
static NSData *fetchRange(NSString *path,uint64_t offset,uint64_t length,uint64_t *actualSize){
  double start=assetNowMS();@try{return fetchRangeImpl(path,offset,length,actualSize);}@finally{assetReadNetworkMS+=assetNowMS()-start;}
}
static int64_t readAssetLegacyLocked(uint32_t id,uint64_t offset,uint8_t *destination,uint32_t length) {
  if(id>=assetFiles.count)return -1;
  if(!length)return 0;
  NSArray *entry=assetFiles[id];NSString *path=entry[0];uint64_t size=[entry[1] unsignedLongLongValue];
  if(offset>=size)return 0;length=(uint32_t)MIN((uint64_t)length,size-offset);
#if TARGET_OS_SIMULATOR
  // Profiling uses the identical mirror directly, without a second asset cache.
#endif
  NSString *directory=[cacheRoot stringByAppendingPathComponent:[NSString stringWithFormat:@"%u",id]];
  [[NSFileManager defaultManager] createDirectoryAtPath:directory withIntermediateDirectories:YES attributes:nil error:nil];
  uint64_t first=offset/4096,last=(offset+length-1)/4096;uint64_t copied=0;
  for(uint64_t block=first;block<=last;block++) {
    NSString *file=[directory stringByAppendingPathComponent:[NSString stringWithFormat:@"%llu",block]];
    NSData *bytes=[NSData dataWithContentsOfFile:file];
    if(!bytes) {
      uint64_t runEnd=block;
      while(runEnd<last&&runEnd-block<255) {NSString *next=[directory stringByAppendingPathComponent:[NSString stringWithFormat:@"%llu",runEnd+1]];if([[NSFileManager defaultManager] fileExistsAtPath:next])break;runEnd++;}
      uint64_t start=block*4096;uint64_t wanted=MIN((runEnd+1)*4096,size)-start;
      NSData *run=fetchRange(path,start,wanted,&size);if(!run)return -1;
      for(uint64_t b=block;b<=runEnd;b++) {
        uint64_t at=(b-block)*4096;if(at>=run.length)break;
        NSData *part=[run subdataWithRange:NSMakeRange(at,MIN((uint64_t)4096,run.length-at))];
        NSString *name=[directory stringByAppendingPathComponent:[NSString stringWithFormat:@"%llu",b]];
        [part writeToFile:name options:NSDataWritingAtomic error:nil];
        if(b==block)bytes=part;
      }
      if(!bytes)return copied;
    }
    uint64_t within=offset>block*4096?offset-block*4096:0;
    if(within>=bytes.length)break;
    uint64_t n=MIN((uint64_t)length-copied,bytes.length-within);
    memcpy(destination+copied,(const uint8_t *)bytes.bytes+within,n);copied+=n;
    if(bytes.length<4096)break;
  }
  return copied;
}
static int64_t readAssetPackedLocked(uint32_t id,uint64_t offset,uint8_t *destination,uint32_t length) {
  if(id>=assetFiles.count)return -1;if(!length)return 0;
  NSArray *entry=assetFiles[id];NSString *path=entry[0];uint64_t size=[entry[1] unsignedLongLongValue];
  if(offset>=size)return 0;length=(uint32_t)MIN((uint64_t)length,size-offset);
#if TARGET_OS_SIMULATOR
  // Simulator graphics timing retains the direct mirror path. Cache mechanics
  // are checked independently against exact ranges and restart persistence.
  if(!assetStreamSimulation)return readAssetLegacyLocked(id,offset,destination,length);
#endif
  NSString *base=[packedRoot stringByAppendingPathComponent:[NSString stringWithFormat:@"%u",id]];
  PGPackedAssetCache cache;
  if(!pg_packed_open(&cache,[base stringByAppendingString:@".data"].fileSystemRepresentation,[base stringByAppendingString:@".map"].fileSystemRepresentation,size))return readAssetLegacyLocked(id,offset,destination,length);
  @try {
    uint64_t first=offset/4096,last=(offset+length-1)/4096;
    NSString *legacy=[cacheRoot stringByAppendingPathComponent:[NSString stringWithFormat:@"%u",id]];
    BOOL hasLegacy=[[NSFileManager defaultManager] fileExistsAtPath:legacy];
    PGAssetCondition *condition=assetLocks[id];
    for(uint64_t block=first;block<=last;block++){
      while(assetBlockInFlight(condition,block)&&!pg_packed_has(&cache,block)){double start=assetNowMS();[condition wait];assetReadLockMS+=assetNowMS()-start;}
      if(pg_packed_has(&cache,block))continue;
      uint64_t end=block,start=block*4096;
      NSData *old=hasLegacy?[NSData dataWithContentsOfFile:[legacy stringByAppendingPathComponent:[NSString stringWithFormat:@"%llu",block]]]:nil;
      NSData *run=nil;
      if(old){
        NSMutableData *migrated=[old mutableCopy];
        while(end<last&&end-block<255&&!pg_packed_has(&cache,end+1)&&!assetBlockInFlight(condition,end+1)){
          NSData *next=[NSData dataWithContentsOfFile:[legacy stringByAppendingPathComponent:[NSString stringWithFormat:@"%llu",end+1]]];
          if(!next)break;[migrated appendData:next];end++;
        }
        run=migrated;
      }else{
        while(end<last&&end-block<255&&!pg_packed_has(&cache,end+1)&&!assetBlockInFlight(condition,end+1)){
          if(hasLegacy&&[[NSFileManager defaultManager] fileExistsAtPath:[legacy stringByAppendingPathComponent:[NSString stringWithFormat:@"%llu",end+1]]])break;
          end++;
        }
        uint64_t wanted=MIN((end+1)*4096,size)-start,actualSize=size;
        NSArray<NSNumber *> *flight=@[@(block),@(end+1)];
        if(assetConcurrentFills){[condition.flights addObject:flight];[condition unlock];}
        @try {
#ifdef PG_ASSET_TEST_HOOK
          if(assetFillTestHook)assetFillTestHook(id,start);
#endif
          run=fetchRange(path,start,wanted,&actualSize);
        } @finally {
          if(assetConcurrentFills){[condition lock];[condition.flights removeObjectIdenticalTo:flight];[condition broadcast];}
        }
        if(actualSize!=size){pg_log("Asset range size disagrees with immutable manifest.");assetSizeMismatch=true;return -1;}
      }
      uint64_t wanted=MIN((end+1)*4096,size)-start;
      if(!run||run.length!=wanted)return -1;
      if(!pg_packed_store(&cache,start,run.bytes,run.length)){
        pg_log("Packed asset cache write failed; using the original cache for this read.");
        return readAssetLegacyLocked(id,offset,destination,length);
      }
      block=end;
    }
    return pg_packed_read(&cache,offset,destination,length);
  } @finally {pg_packed_close(&cache);}
}
// Cached reads bypass fills. Missing ranges reserve blocks while downloading
// outside the archive lock; overlapping reads wait for that one shared fill.
static int64_t readLocalAsset(uint32_t id,uint64_t offset,uint8_t *destination,uint32_t length){
  NSArray *entry=assetFiles[id];uint64_t size=[entry[1] unsignedLongLongValue];
  if(!length||offset>=size)return 0;
  length=(uint32_t)MIN((uint64_t)length,size-offset);
  NSString *overridePath=assetOverrides[entry[0]];
  NSString *file=overridePath?:[localDataRoot stringByAppendingPathComponent:entry[0]];
  int descriptor=open(file.fileSystemRepresentation,O_RDONLY);
  if(descriptor<0){NSString *message=[@"Game file missing from your folder: " stringByAppendingString:entry[0]];pg_log(message.UTF8String);return -1;}
  int64_t count=pg_asset_read_at(descriptor,destination,length,offset);int error=errno;
  close(descriptor);assetReadSource=4;
  if(count<0){NSString *message=[NSString stringWithFormat:@"Game file could not be read: %@ (error %d)",entry[0],error];pg_log(message.UTF8String);errno=error;}
  return count;
}
static int64_t readAssetImpl(uint32_t id,uint64_t offset,uint8_t *destination,uint32_t length) {
  int64_t modernResult;
  if(pg_modern_map_read(id,offset,destination,length,&modernResult)){assetReadSource=4;return modernResult;}
  if(id>=assetFiles.count)return -1;
  NSString *overridePath=assetOverrides[assetFiles[id][0]];
  if(overridePath){
    uint64_t size=[assetFiles[id][1] unsignedLongLongValue];
    if(!length||offset>=size)return 0;
    length=(uint32_t)MIN((uint64_t)length,size-offset);
    int descriptor=open(overridePath.fileSystemRepresentation,O_RDONLY);
    if(descriptor<0){NSString *message=[@"Mod file missing: " stringByAppendingString:overridePath];pg_log(message.UTF8String);return -1;}
    int64_t count=pg_asset_read_at(descriptor,destination,length,offset);int error=errno;
    close(descriptor);assetReadSource=4;
    if(count>0&&assetHasModPacks){PGAssetCondition *condition=assetLocks[id];if(!atomic_exchange_explicit(&condition->overrideReadReported,true,memory_order_relaxed)){NSString *line=[NSString stringWithFormat:@"Mod asset first read: %@; %lld bytes at offset %llu.",assetFiles[id][0],(long long)count,(unsigned long long)offset];pg_log(line.UTF8String);}}
    if(count<0){NSString *message=[NSString stringWithFormat:@"Mod file could not be read: %@ (error %d)",assetFiles[id][0],error];pg_log(message.UTF8String);errno=error;}
    return count;
  }
  if(localDataRoot)return readLocalAsset(id,offset,destination,length);
  if(assetTraceFD>=0&&length){char record[96];int n=snprintf(record,sizeof record,"%u,%llu,%u\n",id,offset,length);if(n>0&&n<sizeof record)write(assetTraceFD,record,(size_t)n);}
#if TARGET_OS_SIMULATOR
  if(assetStreamSimulation){
#endif
  uint64_t size=[assetFiles[id][1] unsignedLongLongValue];
  if(!length||offset>=size)return 0;
  length=(uint32_t)MIN((uint64_t)length,size-offset);
  NSString *base=[packedRoot stringByAppendingPathComponent:[NSString stringWithFormat:@"%u",id]];
  int64_t cached=pg_packed_read_existing([base stringByAppendingString:@".data"].fileSystemRepresentation,[base stringByAppendingString:@".map"].fileSystemRepresentation,size,offset,destination,length);
  if(cached>=0){assetReadSource=1;return cached;}
#if TARGET_OS_SIMULATOR
  }
#endif
  PGAssetCondition *lock=assetLocks[id];double start=assetNowMS();[lock lock];assetReadLockMS+=assetNowMS()-start;
  @try {return readAssetPackedLocked(id,offset,destination,length);}
  @finally {[lock unlock];}
}
// Health counters for the periodic log line (Settings > Share log).
static _Atomic uint64_t healthReads,healthReadBytes,healthReadErrors,healthShortReads,healthSlowReads,healthReadMicros;
void PGAssetHealth(uint64_t out[6]){out[0]=healthReads;out[1]=healthReadBytes;out[2]=healthReadErrors;out[3]=healthShortReads;out[4]=healthSlowReads;out[5]=healthReadMicros;}
// Sandbox on the GTA VI test map: env_test.meta lists only the testbed script archive (about 20
// test scripts), so the startup script finds no main, phone or cheat app there. Reads of that
// file get the GTA V map's script archive plus the cheat-app overlay instead. The engine knows
// every file's size from the manifest, so the rewrite keeps the size: indentation and carriage
// returns are dropped and spaces pad the end. A file that doesn't match is left alone.
static NSData *envTestMeta;
static NSData *envTestMetaRewrite(NSData *original){
  NSString *text=[[NSString alloc] initWithData:original encoding:NSUTF8StringEncoding];
  NSString *testbed=@"\t\t<Item>\r\n\t\t\t<filename>PLATFORM:/LEVELS/TESTBED/SCRIPT/SCRIPT.RPF</filename>\r\n\t\t\t<fileType>RPF_FILE</fileType>\r\n\t\t</Item>\r\n";
  if(!text||[text componentsSeparatedByString:testbed].count!=2)return nil;
  NSString *gta5=@"<Item><filename>platform:/levels/gta5/script/script.rpf</filename><fileType>RPF_FILE</fileType></Item>\n"
    @"<Item><filename>platform:/levels/gta5/script/script_wasm.rpf</filename><fileType>RPF_FILE</fileType><overlay value=\"true\"/></Item>\n";
  text=[text stringByReplacingOccurrencesOfString:testbed withString:gta5];
  text=[[text stringByReplacingOccurrencesOfString:@"\t" withString:@""] stringByReplacingOccurrencesOfString:@"\r" withString:@""];
  NSMutableData *out=[[text dataUsingEncoding:NSUTF8StringEncoding] mutableCopy];
  if(out.length>original.length)return nil;
  NSMutableData *pad=[NSMutableData dataWithLength:original.length-out.length];memset(pad.mutableBytes,' ',pad.length);
  [out appendData:pad];return out;
}
static void envTestMetaOverlay(uint32_t id,uint64_t offset,uint8_t *destination,int64_t count){
  if(count<=0||![assetFiles[id][0] isEqualToString:@"common/data/levels/env_test/env_test.meta"])return;
  @synchronized([NSNull null]) {
    if(!envTestMeta){
      uint64_t size=[assetFiles[id][1] unsignedLongLongValue];
      NSMutableData *original=[NSMutableData dataWithLength:(NSUInteger)size];
      NSData *rewritten=readAssetImpl(id,0,original.mutableBytes,(uint32_t)size)==(int64_t)size?envTestMetaRewrite(original):nil;
      envTestMeta=rewritten?:[NSData data];
      pg_log(rewritten?"GTA VI test map: using the GTA V map's scripts (phone, cheats, free roam).":"GTA VI test map: its level file is not the expected one; the test scripts stay.");
    }
    if(envTestMeta.length&&offset<envTestMeta.length)
      memcpy(destination,(const uint8_t *)envTestMeta.bytes+offset,(size_t)MIN((uint64_t)count,envTestMeta.length-offset));
  }
}
// Keep notifications above the radar at the same width as the browser version.
// Cache one small rewritten copy, including for reads from existing on-device files.
static void feedWidthOverlay(uint32_t id,uint64_t offset,uint8_t *destination,int64_t count) {
  if(id!=feedWidthAssetID || count<=0)return;
  @synchronized([NSNull null]) {
    if(!feedWidthData) {
      uint64_t size=[assetFiles[id][1] unsignedLongLongValue];
      if(size && size<=1024*1024) {
        NSMutableData *data=[NSMutableData dataWithLength:(NSUInteger)size];
        if(readAssetImpl(id,0,data.mutableBytes,(uint32_t)size)==(int64_t)size) {
          bool changed=pg_feed_width(data.mutableBytes,data.length);
          feedWidthData=changed?data:[NSData data];
          pg_log(changed?"Notification width: using the frontend compatibility correction.":"Notification width: frontend layout differs; retaining original bytes.");
        }
      } else feedWidthData=[NSData data];
    }
    pg_feed_width_read(destination,count,offset,feedWidthData.bytes,feedWidthData.length);
  }
}
static int64_t readAsset(uint32_t id,uint64_t offset,uint8_t *destination,uint32_t length){
  assetReadNetworkMS=assetReadLockMS=0;assetReadNetworkBytes=0;assetReadSource=2;
  double healthStart=assetNowMS();
  double start=assetTimingFD>=0?healthStart:0;int64_t result=readAssetImpl(id,offset,destination,length);
  envTestMetaOverlay(id,offset,destination,result);
  feedWidthOverlay(id,offset,destination,result);
  double took=assetNowMS()-healthStart;
  atomic_fetch_add(&healthReads,1);atomic_fetch_add(&healthReadMicros,(uint64_t)(took*1000));
  if(result<0)atomic_fetch_add(&healthReadErrors,1);
  else{atomic_fetch_add(&healthReadBytes,(uint64_t)result);if((uint64_t)result<length)atomic_fetch_add(&healthShortReads,1);}
  if(took>250)atomic_fetch_add(&healthSlowReads,1);
  if(assetTimingFD>=0&&atomic_fetch_add(&assetTimingRecords,1)<200000){char record[256];int n=snprintf(record,sizeof record,"%.3f,%.3f,%u,%llu,%u,%lld,%u,%u,%.3f,%.3f,%llu\n",start,assetNowMS(),id,offset,length,result,assetReadSource,assetPrefetchRead,assetReadNetworkMS,assetReadLockMS,assetReadNetworkBytes);if(n>0&&n<sizeof record)write(assetTimingFD,record,(size_t)n);}
  return result;
}
static _Atomic bool assetEngineBooted;
void pg_assets_prewarm(void){
  atomic_store(&assetEngineBooted,true);
  if(localDataRoot){pg_log("Startup asset warming skipped: the game files are on this device.");pg_log("ASSET_WARM_COMPLETE");return;}
#if TARGET_OS_SIMULATOR
  if(!assetStreamSimulation||[NSProcessInfo.processInfo.arguments containsObject:@"--skip-asset-warm"]){pg_log("Simulator startup asset warming skipped.");return;}
#endif
  @autoreleasepool {
    NSString *path=[NSBundle.mainBundle pathForResource:@"bootset_native" ofType:@"json"];
    NSString *metadataPath=[NSBundle.mainBundle pathForResource:@"bootset_native.summary" ofType:@"json"];
    NSData *metadataData=metadataPath?[NSData dataWithContentsOfFile:metadataPath]:nil;
    NSDictionary *metadata=metadataData?[NSJSONSerialization JSONObjectWithData:metadataData options:0 error:nil]:nil;
    if(![metadata[@"version"] isEqual:assetVersion])path=nil;
    if(!path)path=[NSBundle.mainBundle pathForResource:@"bootset_low" ofType:@"json"];
    NSData *data=path?[NSData dataWithContentsOfFile:path]:nil;
    NSArray *boot=data?[NSJSONSerialization JSONObjectWithData:data options:0 error:nil]:nil;
    if(![boot isKindOfClass:NSArray.class]){pg_log("Startup asset warm set unavailable; continuing demand loading.");return;}
    NSMutableDictionary<NSString *,NSNumber *> *ids=[NSMutableDictionary dictionaryWithCapacity:assetFiles.count];
    for(NSUInteger i=0;i<assetFiles.count;i++)ids[assetFiles[i][0]]=@(i);
    NSMutableArray *jobs=[NSMutableArray array];uint64_t total=0;
    for(NSArray *entry in boot){
      if(![entry isKindOfClass:NSArray.class]||entry.count!=2)continue;NSNumber *identity=ids[entry[0]];if(!identity)continue;
      uint64_t size=[assetFiles[identity.unsignedIntValue][1] unsignedLongLongValue];NSMutableArray *ranges=[NSMutableArray array];
      for(NSArray *range in entry[1]){
        if(![range isKindOfClass:NSArray.class]||range.count!=2)continue;
        uint64_t first=[range[0] unsignedLongLongValue],last=[range[1] unsignedLongLongValue];if(first>=size||last<first)continue;
        first=first/4096*4096;last=MIN((MIN(last,size-1)/4096+1)*4096,size);if(last<=first)continue;
        [ranges addObject:@[@(first),@(last)]];total+=last-first;
      }
      if(ranges.count)[jobs addObject:@[identity,ranges]];
    }
    uint64_t present=0;
    for(NSArray *job in jobs){uint32_t id=[job[0] unsignedIntValue];uint64_t size=[assetFiles[id][1] unsignedLongLongValue];NSString *base=[packedRoot stringByAppendingPathComponent:[NSString stringWithFormat:@"%u",id]];
      for(NSArray *range in job[1]){uint64_t first=[range[0] unsignedLongLongValue],end=[range[1] unsignedLongLongValue];present+=pg_packed_present_bytes([base stringByAppendingString:@".data"].fileSystemRepresentation,[base stringByAppendingString:@".map"].fileSystemRepresentation,size,first,end-first);}}
    NSNumber *available=nil;[[NSURL fileURLWithPath:cacheRoot] getResourceValue:&available forKey:NSURLVolumeAvailableCapacityForImportantUsageKey error:nil];
    if(available&&available.unsignedLongLongValue<total-present+256*1024*1024){pg_log("Startup asset warming skipped to preserve available phone storage.");return;}
    char storage[192];snprintf(storage,sizeof storage,"Startup asset storage: %.1f MB already cached, %.1f MB missing.",present/1048576.0,(total-present)/1048576.0);pg_log(storage);
    if(!total)return;
    char begin[160];snprintf(begin,sizeof begin,"ASSET_WARM_PROGRESS 0 %.0f",total/1048576.0);pg_log(begin);
    if(present==total){
      // Published bitmap bits describe immutable, fully synced cache blocks.
      // Preparation only needs readiness; avoid copying the whole warm set.
      snprintf(begin,sizeof begin,"ASSET_WARM_PROGRESS 100 %.0f",total/1048576.0);pg_log(begin);
      pg_log("Startup asset warming: all planned bytes verified cached; no data copies needed.");
      pg_log("ASSET_WARM_COMPLETE");return;
    }
    __block _Atomic uint64_t next=0,completed=0,lastReport=0;
    __block _Atomic unsigned failures=0;
    uint64_t totalBytes=total;
    dispatch_apply(6,prefetchQueue,^(size_t lane){@autoreleasepool {
      uint8_t *scratch=malloc(1024*1024);if(!scratch){atomic_fetch_add(&failures,1);return;}
      for(;;){
        if(atomic_load(&failures)>=3)break;
        uint64_t jobIndex=atomic_fetch_add(&next,1);if(jobIndex>=jobs.count)break;
        NSArray *job=jobs[jobIndex];uint32_t id=[job[0] unsignedIntValue];
        uint64_t assetSize=[assetFiles[id][1] unsignedLongLongValue];NSString *base=[packedRoot stringByAppendingPathComponent:[NSString stringWithFormat:@"%u",id]];
        NSString *dataPath=[base stringByAppendingString:@".data"],*mapPath=[base stringByAppendingString:@".map"];
        @autoreleasepool {for(NSArray *range in job[1]){
          uint64_t offset=[range[0] unsignedLongLongValue],end=[range[1] unsignedLongLongValue];
          while(offset<end){
            if(atomic_load(&failures)>=3)break;
            uint32_t length=(uint32_t)MIN((uint64_t)1024*1024,end-offset);
            uint64_t cached=pg_packed_present_bytes(dataPath.fileSystemRepresentation,mapPath.fileSystemRepresentation,assetSize,offset,length);
            int64_t actual=cached==length?length:readAsset(id,offset,scratch,length);
            if(actual!=length){atomic_fetch_add(&failures,1);break;}
            offset+=length;uint64_t done=atomic_fetch_add(&completed,length)+length,percent=MIN((uint64_t)100,done*100/totalBytes),previous=atomic_load(&lastReport);
            if(percent>=previous+2&&atomic_compare_exchange_strong(&lastReport,&previous,percent)){char progress[128];snprintf(progress,sizeof progress,"ASSET_WARM_PROGRESS %llu %.0f",percent,totalBytes/1048576.0);pg_log(progress);}
          }
        }}
      }
      free(scratch);
    }});
    char summary[192];snprintf(summary,sizeof summary,"Startup asset warming: %.1f / %.1f MB ready, %u failures; continuing engine boot.",atomic_load(&completed)/1048576.0,totalBytes/1048576.0,atomic_load(&failures));pg_log(summary);
    pg_log("ASSET_WARM_COMPLETE");
  }
}
static void pumpAssetHints(void){
  // Demand reads still run; defer background hints while streaming needs its
  // 384 MiB reserve for eviction and transient Metal uploads.
#if !TARGET_OS_SIMULATOR
  if(os_proc_available_memory()<384ull*1024*1024)return;
#endif
  PGAssetHint hint;
  while(pg_asset_hint_next(&normalHints,&lowHints,(unsigned)atomic_load(&activePrefetch),(unsigned)atomic_load(&activeSpeculative),16,4,&hint)){
    if(hint.id>=assetFiles.count)continue;
    uint64_t size=[assetFiles[hint.id][1] unsignedLongLongValue];if(hint.offset>=size)continue;
    hint.length=(uint32_t)MIN((uint64_t)hint.length,size-hint.offset);
    NSString *base=[packedRoot stringByAppendingPathComponent:[NSString stringWithFormat:@"%u",hint.id]];
    if(pg_packed_present_bytes([base stringByAppendingString:@".data"].fileSystemRepresentation,[base stringByAppendingString:@".map"].fileSystemRepresentation,size,hint.offset,hint.length)==hint.length){hintsCached++;continue;}
    PGAssetHint job=hint;atomic_fetch_add(&activePrefetch,1);if(job.speculative)atomic_fetch_add(&activeSpeculative,1);hintsScheduled++;
    dispatch_block_t work=^{@autoreleasepool {
      assetPrefetchRead=true;assetSpeculativeRead=job.speculative;
      uint8_t *bytes=malloc(1024*1024);
      @try {if(bytes){uint64_t end=job.offset+job.length;for(uint64_t at=job.offset;at<end;){uint32_t length=(uint32_t)MIN((uint64_t)1024*1024,end-at);if(readAsset(job.id,at,bytes,length)!=length)break;at+=length;}}}
      @finally {free(bytes);assetPrefetchRead=assetSpeculativeRead=false;if(job.speculative)atomic_fetch_sub(&activeSpeculative,1);atomic_fetch_sub(&activePrefetch,1);}
    }};
    if(assetBalancedQOS)work=dispatch_block_create_with_qos_class(DISPATCH_BLOCK_ENFORCE_QOS_CLASS,job.speculative?QOS_CLASS_BACKGROUND:QOS_CLASS_UTILITY,0,work);
    dispatch_async(assetBalancedQOS&&job.speculative?speculativeQueue:prefetchQueue,work);
  }
}
// A dedicated consumer keeps processing upcoming reads even when all demand
// threads are waiting for a large region file. It follows the mirror protocol:
// bit 30 selects speculation, and only the lower 30 bits are a byte count.
static void *assetHintLoop(void *unused){
  pthread_setname_np("gta.asset.hints");if(assetBalancedQOS)pthread_set_qos_class_self_np(QOS_CLASS_UTILITY,0);
  wasm_rt_trap_t trap=wasm_rt_impl_try();if(trap){pg_log("Native asset hint worker encountered invalid engine memory.");return NULL;}
  _Atomic int32_t *table=pg_pointer(assetHost,assetTable,64);double report=assetNowMS();
  for(;;){int32_t bell=atomic_load(table);@autoreleasepool {
    uint32_t ring=atomic_load(table+2),capacity=atomic_load(table+3),head=atomic_load(table+4),tail=atomic_load(table+5);
    if(ring&&capacity){uint32_t oldest=pg_asset_hint_oldest(head,tail,capacity);hintsLapped+=(uint32_t)(oldest-tail);tail=oldest;
      while(tail!=head){uint64_t address=assetTable+((uint64_t)ring+(uint64_t)(tail%capacity)*4)*4;_Atomic int32_t *entry=pg_pointer(assetHost,address,16);uint32_t raw=atomic_load(entry+3);if(!raw)break;
        PGAssetHint hint;uint32_t id=atomic_load(entry);uint64_t offset=(uint32_t)atomic_load(entry+1)|((uint64_t)(uint32_t)atomic_load(entry+2)<<32);
        if(pg_asset_hint_decode(id,offset,raw,&hint)){if(hint.speculative){pg_asset_hint_push(&lowHints,hint);hintsLowSeen++;}else{pg_asset_hint_push(&normalHints,hint);hintsNormalSeen++;}}
        atomic_store(entry+3,0);tail++;
      }
      atomic_store(table+5,(int32_t)tail);
    }
    pumpAssetHints();double now=assetNowMS();if(now-report>=10000){char line[256];snprintf(line,sizeof line,"Native asset hints: normal %llu, speculative %llu, scheduled %llu, cached %llu, lapped %llu, queues %u/%u, active %d/%d.",hintsNormalSeen,hintsLowSeen,hintsScheduled,hintsCached,hintsLapped,normalHints.count,lowHints.count,atomic_load(&activePrefetch),atomic_load(&activeSpeculative));pg_log(line);report=now;}
  }pg_atomic_wait32(w2c_env_memory(assetHost),assetTable,bell,10000000);}
}
static void *assetLoop(void *unused) {
  char workerName[32];snprintf(workerName,sizeof workerName,"gta.asset.read.%ld",(long)(intptr_t)unused);pthread_setname_np(workerName);
  wasm_rt_trap_t trap=wasm_rt_impl_try();if(trap){pg_log("Native asset worker encountered invalid engine memory.");return NULL;}
  _Atomic int32_t *table=pg_pointer(assetHost,assetTable,64);
  for(;;) {
    int32_t bell=atomic_load(table);int count=atomic_load(table+1);
    if(count<0||count>4096){pg_log("Invalid native asset slot count.");return NULL;}
    for(int i=0;i<count;i++) {
      uint64_t address=assetTable+(16+(uint64_t)i*16)*4;
      _Atomic int32_t *slot=pg_pointer(assetHost,address,64);int32_t expected=1;
      if(!atomic_compare_exchange_strong(slot,&expected,3))continue;
      @autoreleasepool {
        uint32_t id=atomic_load(slot+1),len=atomic_load(slot+6);
        uint64_t off=(uint32_t)atomic_load(slot+2)|((uint64_t)(uint32_t)atomic_load(slot+3)<<32);
        uint64_t dest=(uint32_t)atomic_load(slot+4)|((uint64_t)(uint32_t)atomic_load(slot+5)<<32);
        int64_t result=readAsset(id,off,pg_pointer(assetHost,dest,len),len);
        atomic_store(slot+7,(int32_t)result);atomic_store(slot,2);
        pg_atomic_notify(w2c_env_memory(assetHost),address,UINT32_MAX);
      }
    }
    // Consume optional prefetch hints. Demand reads remain authoritative.
    if (!assetQueuedHints&&(intptr_t)unused==0) {
    uint32_t hintOffset=atomic_load(table+2),entries=atomic_load(table+3);
    uint32_t used=atomic_load(table+5),claimed=atomic_load(table+4);
    while(entries&&used!=claimed) {
      uint64_t address=assetTable+(hintOffset+(uint64_t)(used%entries)*4)*4;
      _Atomic int32_t *hint=pg_pointer(assetHost,address,16);
      int32_t wanted=atomic_load(hint+3);if(!wanted||atomic_load(&activePrefetch)>=4)break;
      uint32_t id=(uint32_t)atomic_load(hint);
      uint64_t offset=(uint32_t)atomic_load(hint+1)|((uint64_t)(uint32_t)atomic_load(hint+2)<<32);
      uint32_t length=MIN((uint32_t)wanted,512*1024);
      atomic_store(hint+3,0);used++;atomic_store(table+5,used);atomic_fetch_add(&activePrefetch,1);
      dispatch_async(prefetchQueue,^{@autoreleasepool {assetPrefetchRead=assetSpeculativeRead=true;uint8_t *bytes=malloc(length);if(bytes){readAsset(id,offset,bytes,length);free(bytes);}assetPrefetchRead=assetSpeculativeRead=false;atomic_fetch_sub(&activePrefetch,1);}});
    }
    }
    pg_atomic_wait32(w2c_env_memory(assetHost),assetTable,bell,10000000);
  }
}
void w2c_env_wasm_httpfs_io_start_js(struct w2c_env *host,u64 table) {
  if(assetTable)return;assetHost=host;assetTable=table;
  pg_log("Native asset request queue attached; files cached on the phone.");
  for(int i=0;i<6;i++){pthread_t thread;pthread_create(&thread,NULL,assetLoop,(void *)(intptr_t)i);pthread_detach(thread);}
  if(assetQueuedHints){pthread_t thread;pthread_create(&thread,NULL,assetHintLoop,NULL);pthread_detach(thread);pg_log("Native upcoming asset queue enabled: 16 hints, at most 4 speculative; demand reads take priority.");}
}

// MARK: Download all game files (see NativeAssetPreload.h)

void PGAssetCachePrepare(const char *manifestPath,const char *filesRoot){pg_assets_configure(manifestPath,filesRoot);}
bool PGAssetPreloadSupported(void){
  if(!assetFiles.count||!packedRoot||localDataRoot)return false;
#if TARGET_OS_SIMULATOR
  return assetStreamSimulation;
#else
  return true;
#endif
}
// Files whose server size disagrees with the bundled manifest can never be
// cached (the engine rejects them too). They are remembered in the cache
// directory and left out of the plan so it can still complete.
static NSMutableIndexSet *preloadUnavailable;
static pthread_mutex_t preloadUnavailableLock=PTHREAD_MUTEX_INITIALIZER;
static NSString *preloadUnavailablePath(void){return [cacheRoot stringByAppendingPathComponent:@"preload-unavailable.txt"];}
static NSIndexSet *preloadUnavailableIDs(void){
  pthread_mutex_lock(&preloadUnavailableLock);
  if(!preloadUnavailable){
    preloadUnavailable=[NSMutableIndexSet indexSet];
    NSString *text=[NSString stringWithContentsOfFile:preloadUnavailablePath() encoding:NSUTF8StringEncoding error:nil];
    for(NSString *line in [text componentsSeparatedByString:@"\n"])if(line.length)[preloadUnavailable addIndex:(NSUInteger)line.integerValue];
  }
  NSIndexSet *copy=[preloadUnavailable copy];pthread_mutex_unlock(&preloadUnavailableLock);return copy;
}
static bool preloadMarkUnavailable(uint32_t id){
  preloadUnavailableIDs();
  pthread_mutex_lock(&preloadUnavailableLock);
  if([preloadUnavailable containsIndex:id]){pthread_mutex_unlock(&preloadUnavailableLock);return false;}
  [preloadUnavailable addIndex:id];NSMutableString *text=[NSMutableString string];
  [preloadUnavailable enumerateIndexesUsingBlock:^(NSUInteger index,BOOL *stop){[text appendFormat:@"%lu\n",(unsigned long)index];}];
  [text writeToFile:preloadUnavailablePath() atomically:YES encoding:NSUTF8StringEncoding error:nil];
  pthread_mutex_unlock(&preloadUnavailableLock);return true;
}
static NSArray<NSNumber *> *preloadSelection(const char *filter){
  NSIndexSet *unavailable=preloadUnavailableIDs();
  NSArray<NSString *> *prefixes=nil;
  if(filter&&*filter){NSMutableArray *list=[NSMutableArray array];for(NSString *part in [@(filter) componentsSeparatedByString:@","])if(part.length)[list addObject:part];prefixes=list;}
  NSMutableArray<NSNumber *> *ids=[NSMutableArray arrayWithCapacity:assetFiles.count];
  for(NSUInteger i=0;i<assetFiles.count;i++){
    if(prefixes){BOOL match=NO;NSString *path=assetFiles[i][0];for(NSString *prefix in prefixes)if([path hasPrefix:prefix]){match=YES;break;}if(!match)continue;}
    if([unavailable containsIndex:i])continue;
    [ids addObject:@(i)];
  }
  return ids;
}
static uint64_t preloadPresent(uint32_t id,uint64_t offset,uint64_t length){
  uint64_t size=[assetFiles[id][1] unsignedLongLongValue];
  NSString *base=[packedRoot stringByAppendingPathComponent:[NSString stringWithFormat:@"%u",id]];
  return pg_packed_present_bytes([base stringByAppendingString:@".data"].fileSystemRepresentation,[base stringByAppendingString:@".map"].fileSystemRepresentation,size,offset,length);
}
void PGAssetPreloadMeasure(const char *filter,uint64_t *totalBytes,uint64_t *cachedBytes,uint32_t *fileCount){
  uint64_t total=0,cached=0;uint32_t files=0;
  if(assetFiles.count&&packedRoot){@autoreleasepool {
    for(NSNumber *identity in preloadSelection(filter)){
      uint32_t id=identity.unsignedIntValue;uint64_t size=[assetFiles[id][1] unsignedLongLongValue];
      total+=size;files++;if(size)cached+=preloadPresent(id,0,size);
    }
  }}
  if(totalBytes)*totalBytes=total;if(cachedBytes)*cachedBytes=cached;if(fileCount)*fileCount=files;
}

static pthread_mutex_t preloadLock=PTHREAD_MUTEX_INITIALIZER;
static NSArray<NSNumber *> *preloadIDs;
static NSUInteger preloadCursorFile;
static uint64_t preloadCursorOffset;
static _Atomic bool preloadStop,preloadExhausted;
static _Atomic int preloadRunning;
static _Atomic unsigned preloadLanes=4;
static _Atomic uint64_t preloadTotal,preloadCached,preloadDownloaded,preloadReported;
static _Atomic unsigned preloadConsecutiveFailures;
static _Atomic int32_t preloadError;
static const uint32_t preloadSpan=1024*1024;

// Next missing span, in manifest order. Whole files already on the device are
// skipped with one presence-map check.
static bool preloadNextSpan(uint32_t *id,uint64_t *offset,uint32_t *length){
  pthread_mutex_lock(&preloadLock);bool found=false;
  while(!found&&preloadCursorFile<preloadIDs.count){
    uint32_t file=preloadIDs[preloadCursorFile].unsignedIntValue;uint64_t size=[assetFiles[file][1] unsignedLongLongValue];
    if(preloadCursorOffset==0&&(!size||preloadPresent(file,0,size)==size)){preloadCursorFile++;continue;}
    if(preloadCursorOffset>=size){preloadCursorFile++;preloadCursorOffset=0;continue;}
    *id=file;*offset=preloadCursorOffset;*length=(uint32_t)MIN((uint64_t)preloadSpan,size-preloadCursorOffset);
    preloadCursorOffset+=*length;found=true;
  }
  pthread_mutex_unlock(&preloadLock);return found;
}
static void preloadFail(int32_t error,const char *message){
  int32_t none=PGAssetPreloadErrorNone;atomic_compare_exchange_strong(&preloadError,&none,error);
  atomic_store(&preloadStop,true);pg_log(message);
}
static void *preloadLane(void *context){
  unsigned lane=(unsigned)(uintptr_t)context;
  char name[32];snprintf(name,sizeof name,"gta.asset.preload.%u",lane);pthread_setname_np(name);
  // Same low URL priority as speculative engine hints: demand reads go first.
  assetPrefetchRead=assetSpeculativeRead=true;
  uint8_t *scratch=malloc(preloadSpan);
  if(!scratch)preloadFail(PGAssetPreloadErrorStorage,"Asset preload: out of memory for a download buffer.");
  while(scratch&&!atomic_load(&preloadStop)){
    if(atomic_load(&preloadExhausted))break;
    if(lane>=atomic_load(&preloadLanes)){usleep(250000);continue;}
    uint32_t id,length;uint64_t offset;
    if(!preloadNextSpan(&id,&offset,&length)){atomic_store(&preloadExhausted,true);break;}
    @autoreleasepool {
      if([preloadUnavailableIDs() containsIndex:id])continue;
      uint64_t before=preloadPresent(id,offset,length);
      if(before==length)continue;
      bool stored=false;
      bool unavailable=false;
      for(unsigned attempt=0;attempt<4&&!atomic_load(&preloadStop);attempt++){
        assetSizeMismatch=false;
        if(attempt){for(unsigned wait=0;wait<(4u<<attempt)&&!atomic_load(&preloadStop);wait++)usleep(250000);}
        int64_t actual=readAsset(id,offset,scratch,length);
        if(assetSizeMismatch){unavailable=true;break;}
        if(actual!=length)continue;
        // readAsset can still return bytes when the packed write failed (it
        // falls back to the old cache). Only a published span counts.
        if(preloadPresent(id,offset,length)!=length){preloadFail(PGAssetPreloadErrorStorage,"Asset preload: cache write did not persist; stopping (storage full?).");break;}
        stored=true;break;
      }
      if(unavailable){
        // Drop the whole file from this run's plan and every later one.
        if(preloadMarkUnavailable(id)){
        uint64_t size=[assetFiles[id][1] unsignedLongLongValue],present=preloadPresent(id,0,size);
        atomic_fetch_sub(&preloadTotal,size);atomic_fetch_sub(&preloadCached,present);
        pthread_mutex_lock(&preloadLock);if(preloadCursorFile<preloadIDs.count&&preloadIDs[preloadCursorFile].unsignedIntValue==id){preloadCursorFile++;preloadCursorOffset=0;}pthread_mutex_unlock(&preloadLock);
        char line[PATH_MAX+96];snprintf(line,sizeof line,"Asset preload: %s differs in size from the manifest on the server; skipped.",[assetFiles[id][0] UTF8String]);pg_log(line);
        }
      }else if(stored){
        atomic_store(&preloadConsecutiveFailures,0);
        atomic_fetch_add(&preloadDownloaded,length-before);
        uint64_t cached=atomic_fetch_add(&preloadCached,length-before)+length-before,total=atomic_load(&preloadTotal);
        uint64_t percent=total?cached*100/total:100,reported=atomic_load(&preloadReported);
        if(percent>=reported+5&&atomic_compare_exchange_strong(&preloadReported,&reported,percent)){char line[160];snprintf(line,sizeof line,"ASSET_PRELOAD_PROGRESS %llu %.1f %.1f",percent,cached/1048576.0,total/1048576.0);pg_log(line);}
      }else if(!atomic_load(&preloadStop)&&atomic_fetch_add(&preloadConsecutiveFailures,1)+1>=3){
        preloadFail(PGAssetPreloadErrorNetwork,"Asset preload: the asset server did not answer; stopping.");
      }
    }
  }
  free(scratch);
  if(atomic_fetch_sub(&preloadRunning,1)==1){
    // Last lane out re-measures: engine demand fills count too.
    uint64_t total=0,cached=0;uint32_t files=0;
    pthread_mutex_lock(&preloadLock);NSArray<NSNumber *> *ids=preloadIDs;pthread_mutex_unlock(&preloadLock);
    @autoreleasepool {NSIndexSet *unavailable=preloadUnavailableIDs();for(NSNumber *identity in ids){uint32_t file=identity.unsignedIntValue;if([unavailable containsIndex:file])continue;uint64_t size=[assetFiles[file][1] unsignedLongLongValue];total+=size;files++;if(size)cached+=preloadPresent(file,0,size);}}
    atomic_store(&preloadCached,cached);atomic_store(&preloadTotal,total);
    // Went through the whole plan without a pause and still missing bytes:
    // some spans kept failing. Say so instead of looking merely paused.
    int32_t none=PGAssetPreloadErrorNone;
    if(cached<total&&atomic_load(&preloadExhausted)&&!atomic_load(&preloadStop))atomic_compare_exchange_strong(&preloadError,&none,PGAssetPreloadErrorNetwork);
    char line[224];snprintf(line,sizeof line,"Asset preload stopped: %.1f / %.1f MB on device across %u files, %.1f MB downloaded this run, error %d.",cached/1048576.0,total/1048576.0,files,atomic_load(&preloadDownloaded)/1048576.0,atomic_load(&preloadError));pg_log(line);
    if(cached==total)pg_log("ASSET_PRELOAD_COMPLETE");
  }
  return NULL;
}
bool PGAssetPreloadStart(const char *filter,unsigned lanes){
  if(!PGAssetPreloadSupported())return false;
  int idle=0;if(!atomic_compare_exchange_strong(&preloadRunning,&idle,-1))return true;
  lanes=MAX(1u,MIN(6u,lanes));
  NSArray<NSNumber *> *ids=preloadSelection(filter);uint64_t total=0,cached=0;
  for(NSNumber *identity in ids){uint32_t file=identity.unsignedIntValue;uint64_t size=[assetFiles[file][1] unsignedLongLongValue];total+=size;if(size)cached+=preloadPresent(file,0,size);}
  pthread_mutex_lock(&preloadLock);preloadIDs=ids;preloadCursorFile=0;preloadCursorOffset=0;pthread_mutex_unlock(&preloadLock);
  atomic_store(&preloadTotal,total);atomic_store(&preloadCached,cached);atomic_store(&preloadDownloaded,0);
  atomic_store(&preloadReported,total?cached*100/total:100);atomic_store(&preloadConsecutiveFailures,0);
  atomic_store(&preloadError,PGAssetPreloadErrorNone);atomic_store(&preloadStop,false);atomic_store(&preloadExhausted,false);atomic_store(&preloadLanes,lanes);
  char line[200];snprintf(line,sizeof line,"Asset preload started: %.1f / %.1f MB already on device across %lu files, %u lanes.",cached/1048576.0,total/1048576.0,(unsigned long)ids.count,lanes);pg_log(line);
  atomic_store(&preloadRunning,6);
  for(unsigned i=0;i<6;i++){pthread_t thread;if(pthread_create(&thread,NULL,preloadLane,(void *)(uintptr_t)i)){atomic_fetch_sub(&preloadRunning,1);continue;}pthread_detach(thread);}
  return true;
}
void PGAssetPreloadStop(void){atomic_store(&preloadStop,true);}
void PGAssetPreloadSetLanes(unsigned lanes){atomic_store(&preloadLanes,MAX(1u,MIN(6u,lanes)));}
PGAssetPreloadStatus PGAssetPreloadGetStatus(void){
  PGAssetPreloadStatus status={0};int running=atomic_load(&preloadRunning);
  status.running=running!=0;status.totalBytes=atomic_load(&preloadTotal);status.cachedBytes=atomic_load(&preloadCached);
  status.downloadedBytes=atomic_load(&preloadDownloaded);status.error=atomic_load(&preloadError);
  return status;
}
bool PGAssetCacheRemoveAll(uint64_t *freedBytes){
  if(freedBytes)*freedBytes=0;
  if(!cacheRoot||atomic_load(&preloadRunning)||atomic_load(&assetEngineBooted))return false;
  uint64_t cached=0;PGAssetPreloadMeasure(NULL,NULL,&cached,NULL);
  NSFileManager *files=NSFileManager.defaultManager;NSError *error=nil;
  // One explicit directory: this manifest version's cache (packed and legacy).
  if([files fileExistsAtPath:cacheRoot]&&![files removeItemAtPath:cacheRoot error:&error]){pg_log([@"Asset cache removal failed: " stringByAppendingString:error.localizedDescription].UTF8String);return false;}
  [files createDirectoryAtPath:packedRoot withIntermediateDirectories:YES attributes:nil error:nil];
  [[NSURL fileURLWithPath:cacheRoot] setResourceValue:@YES forKey:NSURLIsExcludedFromBackupKey error:nil];
  atomic_store(&preloadCached,0);
  pthread_mutex_lock(&preloadUnavailableLock);preloadUnavailable=nil;pthread_mutex_unlock(&preloadUnavailableLock);
  if(freedBytes)*freedBytes=cached;
  char line[128];snprintf(line,sizeof line,"Asset cache removed: %.1f MB of game files freed.",cached/1048576.0);pg_log(line);
  return true;
}
