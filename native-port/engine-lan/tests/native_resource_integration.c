#include "NativeResourceReclaim.c"
#include <assert.h>
#include <setjmp.h>
static jmp_buf trap;
void pg_log(const char *text){(void)text;}
typedef uint64_t u64;typedef uint32_t u32;
typedef struct {uint64_t size;} Memory;
typedef struct {Memory *w2c_env_memory;uint64_t pointer,block;int freed,allocated;} w2c_game;
#define WASM_RT_TRAP_UNREACHABLE 1
static void wasm_rt_trap(int reason){assert(reason==1);longjmp(trap,1);}
static u64 w2c_game_f3046(w2c_game *i,u64 h,u64 at){(void)h;assert(at==i->pointer);return i->block;}
static u64 pg_original_resource_allocate(w2c_game *i,u64 h,u64 size,u64 align,u32 bucket){(void)h;(void)size;(void)align;(void)bucket;i->allocated++;return i->pointer;}
static void pg_original_resource_free(w2c_game *i,u64 h,u64 at){(void)h;assert(at==i->pointer);assert(PGResourceBytesReleased()>0);i->freed++;}
#include ZGTA_RESOURCE_WRAPPERS
static void put64(uint8_t *m,uint64_t at,uint64_t n){memcpy(m+at,&n,8);}
static int fail_reuse(void *ctx,void *at,size_t len,bool reuse){return reuse?-1:resource_advice(ctx,at,len,reuse);}
int main(void){
 uint64_t cap=32ull<<20,page=(uint64_t)sysconf(_SC_PAGESIZE);
 uint8_t *base=mmap(NULL,(size_t)cap,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0);assert(base!=MAP_FAILED);
 pg_resource_reclaim_init(base,cap);assert(reclaimReady);
 uint64_t heap=RESOURCE_HEAP;uint32_t count=2;memcpy(base+heap+508,&count,4);
 put64(base,heap+16384,12ull<<20);put64(base,heap+512+24,4ull<<20);
 put64(base,heap+16384+8,16ull<<20);put64(base,heap+512+488+24,4ull<<20);
 uint64_t ptr=(16ull<<20)+17,size=4*page;
 pg_resource_reclaim_free(heap,ptr,size,cap);assert(!PGResourceBytesReleased());
 pg_resource_reclaim_pressure(true);pg_resource_reclaim_free(heap,(12ull<<20)+17,size,cap);assert(!PGResourceBytesReleased());
 pg_resource_reclaim_free(heap+8,ptr,size,cap);assert(!PGResourceBytesReleased());
 pg_resource_reclaim_free(heap,ptr,cap,cap);assert(!PGResourceBytesReleased());
 Memory memory={cap};w2c_game game={&memory,ptr,size,0,0};
 w2c_game_f3039(&game,heap,ptr);assert(game.freed==1&&atomic_load(&resourcePages.pending)==3);
 pg_resource_reclaim_pressure(false);
 assert(w2c_game_f3038(&game,heap,size,16,0)==ptr);assert(game.allocated==1);assert(!atomic_load(&resourcePages.pending));assert(PGResourceBytesReused()==3*page);
 memset(base+ptr,0x63,(size_t)size);pg_resource_reclaim_pressure(true);w2c_game_f3039(&game,heap,ptr);
 resourcePages.advise=fail_reuse;
 if(!setjmp(trap)){w2c_game_f3038(&game,heap,size,16,0);assert(!"Failed OS reuse was handed back to game");}
 assert(PGResourceReclaimFailures()==1&&atomic_load(&resourcePages.pending)==3);
 resourcePages.advise=resource_advice;assert(pg_resource_reclaim_reuse(heap,ptr,size,cap));
 pg_pages_destroy(&resourcePages);assert(!munmap(base,(size_t)cap));
 puts("PASS: pressure gating, first segment/live bounds, actual wrapper ordering, reuse after pressure ends, failed-reuse trap");return 0;
}
