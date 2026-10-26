#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#define PG_ASSET_HINT_QUEUE_CAPACITY 2048u
typedef struct {uint64_t offset;uint32_t id,length;bool speculative;} PGAssetHint;
typedef struct {PGAssetHint items[PG_ASSET_HINT_QUEUE_CAPACITY];uint32_t head,count;} PGAssetHintQueue;
static inline bool pg_asset_hint_decode(uint32_t id,uint64_t offset,uint32_t raw,PGAssetHint *hint){
 uint32_t length=raw&0x3fffffffu;if(!length||!hint)return false;
 *hint=(PGAssetHint){.offset=offset,.id=id,.length=length,.speculative=(raw&0x40000000u)!=0};return true;
}
static inline uint32_t pg_asset_hint_oldest(uint32_t head,uint32_t tail,uint32_t capacity){
 return (uint32_t)(head-tail)>capacity?head-capacity:tail;
}
static inline void pg_asset_hint_push(PGAssetHintQueue *queue,PGAssetHint hint){
 if(queue->count==PG_ASSET_HINT_QUEUE_CAPACITY){queue->head=(queue->head+1)%PG_ASSET_HINT_QUEUE_CAPACITY;queue->count--;}
 queue->items[(queue->head+queue->count)%PG_ASSET_HINT_QUEUE_CAPACITY]=hint;queue->count++;
}
static inline bool pg_asset_hint_pop(PGAssetHintQueue *queue,PGAssetHint *hint){
 if(!queue->count||!hint)return false;*hint=queue->items[queue->head];queue->head=(queue->head+1)%PG_ASSET_HINT_QUEUE_CAPACITY;queue->count--;return true;
}
static inline bool pg_asset_hint_next(PGAssetHintQueue *normal,PGAssetHintQueue *low,unsigned active,unsigned lowActive,unsigned limit,unsigned lowLimit,PGAssetHint *hint){
 if(active>=limit)return false;
 if(normal->count)return pg_asset_hint_pop(normal,hint);
 if(lowActive>=lowLimit)return false;return pg_asset_hint_pop(low,hint);
}
