/* One immutable, verified UI archive. Bypasses old packed-cache sizes safely. */
#pragma once
#import <Foundation/Foundation.h>
#import <CommonCrypto/CommonDigest.h>
#include <stdatomic.h>
#include <stdint.h>
#include <string.h>
static _Atomic uint32_t pg_modern_map_id=UINT32_MAX;
static NSData *pg_modern_map_data;
static BOOL pg_modern_map_configure(const char *manifest,NSArray *existingFiles) {
 @synchronized(@"ZGTA.ModernMapArchive") {
  if(atomic_load_explicit(&pg_modern_map_id,memory_order_acquire)!=UINT32_MAX)return YES;
  @autoreleasepool {
    NSData *raw=[NSData dataWithContentsOfFile:@(manifest)];
    NSDictionary *root=raw?[NSJSONSerialization JSONObjectWithData:raw options:0 error:NULL]:nil;
    if(![root isKindOfClass:NSDictionary.class])return NO;
    NSDictionary *marker=root[@"_zemaModernMapIcons"];
    if(![marker isKindOfClass:NSDictionary.class])return NO;
    NSString *path=@"x64/data/cdimages/scaleform_minimap.rpf",*digest=marker[@"sha256"];
    NSArray *files=root[@"files"];NSDictionary *overrides=root[@"_mugoatOverrides"];
    if(![files isKindOfClass:NSArray.class]||![overrides isKindOfClass:NSDictionary.class]||![digest isKindOfClass:NSString.class]||digest.length!=64)return NO;
    NSUInteger identity=NSNotFound;
    for(NSUInteger i=0;i<files.count;i++){
      NSArray *row=files[i];if(![row isKindOfClass:NSArray.class]||row.count<2||![row[0] isKindOfClass:NSString.class])return NO;
      if([row[0] caseInsensitiveCompare:path]==NSOrderedSame){if(identity!=NSNotFound)return NO;identity=i;}
    }
    if(identity==NSNotFound||identity>=UINT32_MAX)return NO;
    if(existingFiles&&(identity>=existingFiles.count||![existingFiles[identity][0] isEqual:files[identity][0]]))return NO;
    NSString *file=overrides[files[identity][0]];
    if(![file isKindOfClass:NSString.class]||![files[identity][1] isKindOfClass:NSNumber.class])return NO;
    NSNumber *size=nil;NSError *error=nil;
    if(![[NSURL fileURLWithPath:file] getResourceValue:&size forKey:NSURLFileSizeKey error:&error]||size.unsignedLongLongValue>1048576)return NO;
    NSData *data=[NSData dataWithContentsOfFile:file];
    if(!data.length||data.length!=[files[identity][1] unsignedLongLongValue]||data.length>1048576)return NO;
    unsigned char hash[CC_SHA256_DIGEST_LENGTH];CC_SHA256(data.bytes,(CC_LONG)data.length,hash);
    NSMutableString *actual=[NSMutableString stringWithCapacity:64];for(unsigned i=0;i<sizeof hash;i++)[actual appendFormat:@"%02x",hash[i]];
    if(![actual isEqualToString:digest])return NO;
    pg_modern_map_data=data;atomic_store_explicit(&pg_modern_map_id,(uint32_t)identity,memory_order_release);return YES;
  }
 }
}
static BOOL pg_modern_map_read(uint32_t identity,uint64_t offset,void *destination,uint32_t length,int64_t *result) {
  uint32_t configured=atomic_load_explicit(&pg_modern_map_id,memory_order_acquire);
  if(configured==UINT32_MAX||identity!=configured)return NO;
  uint64_t size=pg_modern_map_data.length;
  if(offset>=size||!length){*result=0;return YES;}
  size_t count=(size_t)MIN((uint64_t)length,size-offset);memcpy(destination,(const uint8_t *)pg_modern_map_data.bytes+offset,count);*result=(int64_t)count;return YES;
}
