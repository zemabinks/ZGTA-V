#include "NativePackedAssetCache.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
int main(void){
 char directory[]="/tmp/playgta-packed-cache-XXXXXX";assert(mkdtemp(directory));
 char data[256],map[256];snprintf(data,sizeof data,"%s/data",directory);snprintf(map,sizeof map,"%s/map",directory);
 PGPackedAssetCache cache;uint8_t source[4096],copy[8192];for(unsigned i=0;i<4096;i++)source[i]=(uint8_t)i;
 assert(pg_packed_open(&cache,data,map,8192+123));assert(!pg_packed_has(&cache,0)&&!pg_packed_has(&cache,3));
 assert(pg_packed_read(&cache,0,copy,4)==-1);
 assert(!pg_packed_store(&cache,1,source,4096)&&!pg_packed_store(&cache,0,source,123));
 assert(pg_packed_store(&cache,0,source,4096)&&pg_packed_has(&cache,0)&&!pg_packed_has(&cache,1));
 assert(pg_packed_read(&cache,7,copy,100)==100&&!memcmp(copy,source+7,100));assert(pg_packed_read(&cache,4000,copy,200)==-1);
 assert(pg_packed_read_existing(data,map,8315,7,copy,100)==100&&!memcmp(copy,source+7,100));
 assert(pg_packed_read_existing(data,map,8315,4000,copy,200)==-1);
 assert(pg_packed_present_bytes(data,map,8315,0,8315)==4096);
 assert(pg_packed_present_bytes(data,map,8315,4000,200)==96);
 assert(pg_packed_present_bytes(data,map,8314,0,8314)==0);
 assert(pg_packed_read_existing(data,map,8314,7,copy,100)==-1);
 assert(pg_packed_read_existing(data,map,8315,8314,copy,2)==-1);
 assert(pg_packed_store(&cache,8192,source,123)&&pg_packed_read(&cache,8192,copy,123)==123&&!memcmp(copy,source,123));
 assert(pg_packed_present_bytes(data,map,8315,0,8315)==4096+123);
 assert(pg_packed_read(&cache,8314,copy,2)==-1&&pg_packed_read(&cache,8315,copy,0)==0);
 pg_packed_close(&cache);assert(pg_packed_open(&cache,data,map,8315));assert(pg_packed_has(&cache,0)&&pg_packed_has(&cache,2)&&!pg_packed_has(&cache,1));
 assert(pg_packed_store(&cache,4096,source,4096));assert(pg_packed_read(&cache,4000,copy,200)==200&&!memcmp(copy,source+4000,96)&&!memcmp(copy+96,source,104));pg_packed_close(&cache);
 assert(pg_packed_read_existing(data,map,8315,4000,copy,200)==200&&!memcmp(copy,source+4000,96)&&!memcmp(copy+96,source,104));
 assert(pg_packed_present_bytes(data,map,8315,0,8315)==8315);
 // A missing/truncated data file must invalidate old presence bits.
 assert(truncate(data,0)==0&&pg_packed_open(&cache,data,map,8315));assert(!pg_packed_has(&cache,0)&&!pg_packed_has(&cache,2));pg_packed_close(&cache);
 assert(pg_packed_read_existing(data,map,8315,7,copy,100)==-1);
 assert(pg_packed_present_bytes(data,map,8315,0,8315)==0);
 // Sparse allocation permits large archives without downloading all bytes.
 assert(pg_packed_open(&cache,data,map,((uint64_t)1<<32)+123));assert(pg_packed_store(&cache,(uint64_t)1<<32,source,123));assert(pg_packed_read(&cache,((uint64_t)1<<32)+9,copy,80)==80&&!memcmp(copy,source+9,80));
 assert(pg_packed_read_existing(data,map,((uint64_t)1<<32)+123,((uint64_t)1<<32)+9,copy,80)==80&&!memcmp(copy,source+9,80));
 assert(pg_packed_read_existing(data,map,((uint64_t)1<<32)+123,((uint64_t)1<<32)-1,copy,80)==-1);
 // A broad cached range spans several bitmap read chunks.
 size_t broadLength=9*1024*1024;uint8_t *broad=malloc(broadLength),*broadCopy=malloc(broadLength);assert(broad&&broadCopy);
 for(size_t i=0;i<broadLength;i++)broad[i]=(uint8_t)(i*17^(i>>8));
 assert(pg_packed_store(&cache,0,broad,broadLength));
 assert(pg_packed_read_existing(data,map,cache.size,7,broadCopy,broadLength-13)==broadLength-13&&!memcmp(broadCopy,broad+7,broadLength-13));
 assert(pg_packed_present_bytes(data,map,cache.size,7,broadLength-13)==broadLength-13);
 assert(pg_packed_read_existing(data,map,cache.size,broadLength-10,broadCopy,20)==-1);free(broad);free(broadCopy);
 struct stat status;assert(!fstat(cache.dataFD,&status)&&status.st_blocks*512<16*1024*1024);pg_packed_close(&cache);
 unlink(data);unlink(map);rmdir(directory);
 puts("PASS: packed cache holes, exact/partial ranges, missing/truncated files, persistence, boundaries and sparse offsets above 4 GB.");
}
