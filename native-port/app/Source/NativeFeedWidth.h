/* Same length-preserving GameStream correction as engine-lan/data_overlay.py.
 * Mutates only a caller-owned copy of the small frontend XML, never an asset file.
 */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
static inline bool pg_feed_width(unsigned char *bytes,size_t length) {
  const char begin[]="<GameStream>",end[]="</GameStream>";
  const char old[]="sizeX=\"0.19890859375\"",replacement[]="sizeX=\"0.15000000000\"";
  if(!bytes || length>1024*1024 || memchr(bytes,0,length))return false;
  size_t start=length,stop=length;
  for(size_t i=0;i+sizeof begin-1<=length;i++)if(!memcmp(bytes+i,begin,sizeof begin-1)){start=i;break;}
  if(start==length)return false;
  for(size_t i=start;i+sizeof end-1<=length;i++)if(!memcmp(bytes+i,end,sizeof end-1)){stop=i;break;}
  if(stop==length)return false;
  bool changed=false;
  for(size_t i=start;i+sizeof old-1<=stop;i++)if(!memcmp(bytes+i,old,sizeof old-1)) {
    memcpy(bytes+i,replacement,sizeof replacement-1);changed=true;i+=sizeof old-2;
  }
  return changed;
}

static inline void pg_feed_width_read(unsigned char *destination,int64_t count,uint64_t offset,
    const unsigned char *patched,size_t length) {
  if(count<=0 || offset>=length)return;
  size_t available=length-(size_t)offset;
  size_t size=(uint64_t)count<available?(size_t)count:available;
  memcpy(destination,patched+(size_t)offset,size);
}
