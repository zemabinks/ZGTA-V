#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <errno.h>
#include <limits.h>

// Two sparse files per archive replace thousands of 4 KB filesystem objects.
// The bitmap is published only after the corresponding data is durable.
// Writers hold the per-archive lock for the mapping's lifetime. Completed
// blocks are immutable; independent readers use pread on published bitmap bytes.
typedef struct {
 int dataFD,mapFD;
 uint8_t *bits;
 uint64_t size,blocks;
 size_t mapBytes;
} PGPackedAssetCache;

static inline void pg_packed_close(PGPackedAssetCache *cache){
 if(cache->bits)munmap(cache->bits,cache->mapBytes);
 if(cache->mapFD>=0)close(cache->mapFD);
 if(cache->dataFD>=0)close(cache->dataFD);
 cache->bits=NULL;cache->mapFD=cache->dataFD=-1;
}
static inline bool pg_packed_open(PGPackedAssetCache *cache,const char *dataPath,const char *mapPath,uint64_t size){
 memset(cache,0,sizeof *cache);cache->dataFD=cache->mapFD=-1;
 if(!size||size>INT64_MAX)return false;
 cache->size=size;cache->blocks=(size+4095)/4096;cache->mapBytes=(size_t)((cache->blocks+7)/8);
 cache->dataFD=open(dataPath,O_RDWR|O_CREAT,0600);if(cache->dataFD<0)return false;
 cache->mapFD=open(mapPath,O_RDWR|O_CREAT,0600);if(cache->mapFD<0){pg_packed_close(cache);return false;}
 struct stat dataStat,mapStat;
 if(fstat(cache->dataFD,&dataStat)||fstat(cache->mapFD,&mapStat)){pg_packed_close(cache);return false;}
 bool reset=(uint64_t)dataStat.st_size!=size||(uint64_t)mapStat.st_size!=cache->mapBytes;
 // Withdraw old presence bits before repairing a mismatched data file; an
 // independent reader must never observe a repaired sparse file with old bits.
 if((reset&&ftruncate(cache->mapFD,0))||ftruncate(cache->dataFD,(off_t)size)||ftruncate(cache->mapFD,(off_t)cache->mapBytes)){pg_packed_close(cache);return false;}
 void *mapping=mmap(NULL,cache->mapBytes,PROT_READ|PROT_WRITE,MAP_SHARED,cache->mapFD,0);
 if(mapping==MAP_FAILED){pg_packed_close(cache);return false;}
 cache->bits=mapping;return true;
}
static inline bool pg_packed_has(const PGPackedAssetCache *cache,uint64_t block){
 return cache->bits&&block<cache->blocks&&(cache->bits[block/8]&(1u<<(block%8)))!=0;
}
static inline bool pg_packed_store(PGPackedAssetCache *cache,uint64_t offset,const void *input,size_t length){
 if(!cache->bits||offset>cache->size||length>cache->size-offset||(offset%4096)||(length%4096&&offset+length!=cache->size)||(!input&&length))return false;
 if(!length)return true;
 size_t written=0;while(written<length){ssize_t n=pwrite(cache->dataFD,(const uint8_t *)input+written,length-written,(off_t)(offset+written));if(n<0&&errno==EINTR)continue;if(n<=0)return false;written+=(size_t)n;}
 if(fsync(cache->dataFD))return false;
 uint64_t first=offset/4096,last=(offset+length-1)/4096;
 for(uint64_t block=first;block<=last;block++)cache->bits[block/8]|=1u<<(block%8);
 // A failed metadata flush cannot make the already synced data incorrect.
 // It can only cause a cache miss after a later restart.
 msync(cache->bits,cache->mapBytes,MS_SYNC);return true;
}
static inline int64_t pg_packed_read(PGPackedAssetCache *cache,uint64_t offset,void *destination,size_t length){
 if(!cache->bits||offset>cache->size||length>cache->size-offset||(!destination&&length))return -1;
 if(!length)return 0;
 uint64_t first=offset/4096,last=(offset+length-1)/4096;
 for(uint64_t block=first;block<=last;block++)if(!pg_packed_has(cache,block))return -1;
 size_t read=0;while(read<length){ssize_t n=pread(cache->dataFD,(uint8_t *)destination+read,length-read,(off_t)(offset+read));if(n<0&&errno==EINTR)continue;if(n<=0)return -1;read+=(size_t)n;}
 return (int64_t)read;
}

// Read only already published blocks without acquiring a writer's archive
// lock. No file creation, truncation or shared writable mapping occurs here.
// Writers sync data before publishing bits and never rewrite present blocks.
static inline int64_t pg_packed_read_existing(const char *dataPath,const char *mapPath,uint64_t size,uint64_t offset,void *destination,size_t length){
 if(!size||size>INT64_MAX||offset>size||length>size-offset||(!destination&&length))return -1;
 if(!length)return 0;
 int dataFD=open(dataPath,O_RDONLY);if(dataFD<0)return -1;
 int mapFD=open(mapPath,O_RDONLY);if(mapFD<0){close(dataFD);return -1;}
 int64_t result=-1;struct stat dataStat,mapStat;
 uint64_t blocks=(size+4095)/4096,mapBytes=(blocks+7)/8;
 if(fstat(dataFD,&dataStat)||fstat(mapFD,&mapStat)||(uint64_t)dataStat.st_size!=size||(uint64_t)mapStat.st_size!=mapBytes)goto done;
 uint64_t first=offset/4096,last=(offset+length-1)/4096,firstByte=first/8,lastByte=last/8;
 for(uint64_t at=firstByte;at<=lastByte;){
  uint8_t bits[256];size_t wanted=(size_t)((lastByte-at+1)<sizeof bits?(lastByte-at+1):sizeof bits),received=0;
  while(received<wanted){ssize_t n=pread(mapFD,bits+received,wanted-received,(off_t)(at+received));if(n<0&&errno==EINTR)continue;if(n<=0)goto done;received+=(size_t)n;}
  for(size_t i=0;i<wanted;i++){
   uint64_t byte=at+i;unsigned low=byte==firstByte?(unsigned)(first%8):0,high=byte==lastByte?(unsigned)(last%8):7;
   unsigned mask=((1u<<(high+1))-1)&~((1u<<low)-1);
   if((bits[i]&mask)!=mask)goto done;
  }
  at+=wanted;
 }
 size_t copied=0;
 while(copied<length){ssize_t n=pread(dataFD,(uint8_t *)destination+copied,length-copied,(off_t)(offset+copied));if(n<0&&errno==EINTR)continue;if(n<=0)goto done;copied+=(size_t)n;}
 result=(int64_t)copied;
done:
 close(mapFD);close(dataFD);return result;
}

// Storage planning reads only the tiny presence map, without reading all of
// the cached asset bytes. Missing or mismatched files conservatively count zero.
static inline uint64_t pg_packed_present_bytes(const char *dataPath,const char *mapPath,uint64_t size,uint64_t offset,uint64_t length){
 if(!size||size>INT64_MAX||offset>size||length>size-offset||!length)return 0;
 int dataFD=open(dataPath,O_RDONLY);if(dataFD<0)return 0;
 int mapFD=open(mapPath,O_RDONLY);if(mapFD<0){close(dataFD);return 0;}
 uint64_t cached=0;struct stat dataStat,mapStat;
 uint64_t blocks=(size+4095)/4096,mapBytes=(blocks+7)/8;
 if(fstat(dataFD,&dataStat)||fstat(mapFD,&mapStat)||(uint64_t)dataStat.st_size!=size||(uint64_t)mapStat.st_size!=mapBytes)goto done;
 uint64_t first=offset/4096,last=(offset+length-1)/4096,lastByte=last/8;
 for(uint64_t at=first/8;at<=lastByte;){
  uint8_t bits[256];size_t wanted=(size_t)((lastByte-at+1)<sizeof bits?(lastByte-at+1):sizeof bits),received=0;
  while(received<wanted){ssize_t n=pread(mapFD,bits+received,wanted-received,(off_t)(at+received));if(n<0&&errno==EINTR)continue;if(n<=0)goto done;received+=(size_t)n;}
  for(size_t i=0;i<wanted;i++)for(unsigned bit=0;bit<8;bit++){
   uint64_t block=(at+i)*8+bit;if(block<first||block>last||!(bits[i]&(1u<<bit)))continue;
   uint64_t low=block*4096>offset?block*4096:offset,high=(block+1)*4096<offset+length?(block+1)*4096:offset+length;
   cached+=high-low;
  }
  at+=wanted;
 }
done:
 close(mapFD);close(dataFD);return cached;
}
