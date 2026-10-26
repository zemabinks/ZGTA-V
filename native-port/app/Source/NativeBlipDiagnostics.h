/* Bounded diagnostics and approved asset-name compatibility. No game-memory writes. */
#ifndef PG_NATIVE_BLIP_DIAGNOSTICS_H
#define PG_NATIVE_BLIP_DIAGNOSTICS_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "NativeBlipFallbacks.inc"
#define PG_BLIP_TABLE_ADDRESS UINT64_C(19520936)
#define PG_BLIP_DIAGNOSTIC_LIMIT 128
#define PG_BLIP_TABLE_COUNT_ADDRESS UINT64_C(19520944)
typedef struct { uint32_t seen[PG_BLIP_DIAGNOSTIC_LIMIT];unsigned count; } PGBlipDiagnosticCache;
typedef void (*PGBlipDiagnosticReporter)(void *,int32_t,uint16_t);
static inline uint64_t pg_blip_diagnostic(PGBlipDiagnosticCache *cache,const unsigned char *memory,
    uint64_t size,uint64_t reference,uint64_t original,PGBlipDiagnosticReporter report,void *context) {
    if(original||!cache||!memory||!report||!reference||reference>size||size-reference<4||size<PG_BLIP_TABLE_COUNT_ADDRESS+2)return original;
    uint16_t count=(uint16_t)(memory[PG_BLIP_TABLE_COUNT_ADDRESS]|((uint16_t)memory[PG_BLIP_TABLE_COUNT_ADDRESS+1]<<8));
    if(!count||cache->count>=PG_BLIP_DIAGNOSTIC_LIMIT)return original;
    uint32_t sprite=(uint32_t)memory[reference]|((uint32_t)memory[reference+1]<<8)|
        ((uint32_t)memory[reference+2]<<16)|((uint32_t)memory[reference+3]<<24);
    for(unsigned i=0;i<cache->count;i++)if(cache->seen[i]==sprite)return original;
    cache->seen[cache->count++]=sprite;report(context,(int32_t)sprite,count);return original;
}
static inline uint64_t pg_blip_read64(const unsigned char *p) {
    uint64_t out=0;for(unsigned i=0;i<8;i++)out|=(uint64_t)p[i]<<(i*8);return out;
}
static inline uint32_t pg_blip_read32(const unsigned char *p) {
    uint32_t out=0;for(unsigned i=0;i<4;i++)out|=(uint32_t)p[i]<<(i*8);return out;
}
static inline uint64_t pg_blip_fallback(const unsigned char *memory,uint64_t size,
    uint64_t reference,uint64_t original,int32_t *target) {
    if(target)*target=-1;
    if(original||!memory||!reference||reference>size||size-reference<4||size<PG_BLIP_TABLE_COUNT_ADDRESS+2)return original;
    int32_t sprite=(int32_t)pg_blip_read32(memory+reference);
    const struct PGBlipFallback *row=NULL;
    for(size_t i=0;i<sizeof(pg_blip_fallbacks)/sizeof(*pg_blip_fallbacks);i++)
        if(pg_blip_fallbacks[i].requested==sprite){row=&pg_blip_fallbacks[i];break;}
    if(!row)return original;
    uint16_t count=(uint16_t)(memory[PG_BLIP_TABLE_COUNT_ADDRESS]|((uint16_t)memory[PG_BLIP_TABLE_COUNT_ADDRESS+1]<<8));
    uint64_t base=pg_blip_read64(memory+PG_BLIP_TABLE_ADDRESS);
    if(!count||count>1024||!base||base>size||size-base<(uint64_t)count*16)return original;
    unsigned low=0,high=count;
    while(low<high){unsigned mid=(low+high)/2;int32_t id=(int32_t)pg_blip_read32(memory+base+mid*16);if(id<row->target)low=mid+1;else high=mid;}
    if(low==count||(int32_t)pg_blip_read32(memory+base+low*16)!=row->target)return original;
    uint64_t name=pg_blip_read64(memory+base+low*16+8);size_t length=strlen(row->asset);
    if(!name||name>size||size-name<length+1||memcmp(memory+name,row->asset,length+1))return original;
    uint16_t after=(uint16_t)(memory[PG_BLIP_TABLE_COUNT_ADDRESS]|((uint16_t)memory[PG_BLIP_TABLE_COUNT_ADDRESS+1]<<8));
    if(count!=after||base!=pg_blip_read64(memory+PG_BLIP_TABLE_ADDRESS))return original;
    if(target)*target=row->target;
    return name;
}
#endif
