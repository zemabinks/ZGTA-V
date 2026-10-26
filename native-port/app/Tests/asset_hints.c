#include "NativeAssetHints.h"
#include <assert.h>
#include <stdio.h>
int main(void){
 PGAssetHint h;assert(pg_asset_hint_decode(7,((uint64_t)1<<32)+19,0x40000123,&h));assert(h.id==7&&h.offset==((uint64_t)1<<32)+19&&h.length==0x123&&h.speculative);
 assert(pg_asset_hint_decode(8,0,2*1024*1024,&h)&&h.length==2*1024*1024&&!h.speculative);
 assert(!pg_asset_hint_decode(0,0,0,&h)&&!pg_asset_hint_decode(0,0,0x40000000,&h));
 assert(pg_asset_hint_oldest(100,90,32)==90&&pg_asset_hint_oldest(100,2,32)==68);
 assert(pg_asset_hint_oldest(3,UINT32_MAX-2,32)==UINT32_MAX-2&&pg_asset_hint_oldest(3,UINT32_MAX-100,32)==(uint32_t)(3-32));
 static PGAssetHintQueue normal,low;
 for(unsigned i=0;i<PG_ASSET_HINT_QUEUE_CAPACITY+10;i++)pg_asset_hint_push(&low,(PGAssetHint){.id=i,.speculative=true});
 assert(low.count==PG_ASSET_HINT_QUEUE_CAPACITY&&pg_asset_hint_pop(&low,&h)&&h.id==10);
 pg_asset_hint_push(&normal,(PGAssetHint){.id=99});
 assert(!pg_asset_hint_next(&normal,&low,16,0,16,4,&h));
 assert(pg_asset_hint_next(&normal,&low,15,4,16,4,&h)&&h.id==99);
 assert(!pg_asset_hint_next(&normal,&low,4,4,16,4,&h));
 assert(pg_asset_hint_next(&normal,&low,3,3,16,4,&h)&&h.id==11&&h.speculative);
 puts("PASS: actual hint flag/length protocol, full announced ranges, 64-bit offsets, bounded newest-first overflow retention, FIFO priority, concurrency caps and unsigned ring wrap/lapping.");
}
