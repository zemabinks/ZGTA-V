/* Whole freed pages only. Adapted from Glue5 950a8ab (GPL-3.0).
 * The caller owns the block until the allocator's original Free runs. */
#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <pthread.h>
#include <stdatomic.h>

typedef int (*PGPageAdvice)(void *,void *,size_t,bool);
typedef struct {
 uint8_t *base;uint64_t capacity,page,words;uint64_t *bits;
 pthread_mutex_t lock;PGPageAdvice advise;void *context;
 _Atomic uint64_t pending,released,reused,failures;
} PGPageReclaim;
static inline bool pg_pages_init(PGPageReclaim *s,void *base,uint64_t capacity,uint64_t page,PGPageAdvice advise,void *context){
 if(!base||!page||(page&(page-1))||(uintptr_t)base%page||!capacity||capacity%page||capacity>16ull*1024*1024*1024||!advise)return false;
 s->base=base;s->capacity=capacity;s->page=page;s->words=(capacity/page+63)/64;s->advise=advise;s->context=context;
 s->bits=calloc((size_t)s->words,sizeof(uint64_t));if(!s->bits)return false;
 if(pthread_mutex_init(&s->lock,NULL)){free(s->bits);s->bits=NULL;return false;}return true;
}
static inline bool pg_pages_bounds(PGPageReclaim *s,uint64_t at,uint64_t len,uint64_t limit){
 return s->bits&&at&&len&&limit<=s->capacity&&at<=limit&&len<=limit-at;
}
static inline bool pg_pages_marked(PGPageReclaim *s,uint64_t n){return (s->bits[n/64]>>(n%64))&1;}
static inline bool pg_pages_release(PGPageReclaim *s,uint64_t at,uint64_t len,uint64_t limit){
 if(!pg_pages_bounds(s,at,len,limit))return false;
 uint64_t first=at/s->page+(at%s->page!=0),end=(at+len)/s->page;if(end<=first)return false;
 pthread_mutex_lock(&s->lock);
 uint64_t added=0;for(uint64_t n=first;n<end;n++)added+=!pg_pages_marked(s,n);
 if(!added){pthread_mutex_unlock(&s->lock);return false;}
 if(s->advise(s->context,s->base+first*s->page,(size_t)((end-first)*s->page),false)){
  atomic_fetch_add(&s->failures,1);pthread_mutex_unlock(&s->lock);return false;
 }
 for(uint64_t n=first;n<end;n++)s->bits[n/64]|=1ull<<(n%64);
 atomic_fetch_add(&s->pending,added);atomic_fetch_add(&s->released,added*s->page);
 pthread_mutex_unlock(&s->lock);return true;
}
static inline bool pg_pages_reuse(PGPageReclaim *s,uint64_t at,uint64_t len,uint64_t limit){
 if(!s->bits||!atomic_load_explicit(&s->pending,memory_order_acquire))return true;
 if(!pg_pages_bounds(s,at,len,limit))return false;
 uint64_t first=at/s->page,end=(at+len)/s->page+((at+len)%s->page!=0);
 pthread_mutex_lock(&s->lock);
 uint64_t taken=0;for(uint64_t n=first;n<end;n++)taken+=pg_pages_marked(s,n);
 if(taken&&s->advise(s->context,s->base+first*s->page,(size_t)((end-first)*s->page),true)){
  atomic_fetch_add(&s->failures,1);pthread_mutex_unlock(&s->lock);return false;
 }
 if(taken){for(uint64_t n=first;n<end;n++)s->bits[n/64]&=~(1ull<<(n%64));atomic_fetch_sub(&s->pending,taken);atomic_fetch_add(&s->reused,taken*s->page);}
 pthread_mutex_unlock(&s->lock);return true;
}
static inline void pg_pages_destroy(PGPageReclaim *s){if(s->bits){pthread_mutex_destroy(&s->lock);free(s->bits);s->bits=NULL;}}
