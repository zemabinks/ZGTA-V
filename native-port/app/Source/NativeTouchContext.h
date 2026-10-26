#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <stdatomic.h>

// Read-only snapshots of the pinned engine's PLAYER_PED_ID and
// IS_PED_IN_ANY_HELI / IS_PED_IN_ANY_PLANE implementation. No script native is
// invoked from UIKit's thread, and no engine object is retained or modified.
static inline bool pg_context_u64(const uint8_t *memory,uint64_t size,uint64_t address,uint64_t *value){
 if(!memory || size<8 || address>size-8 || (address&7))return false;
 *value=atomic_load_explicit((const _Atomic uint64_t *)(memory+address),memory_order_relaxed);return true;
}
static inline bool pg_context_u32(const uint8_t *memory,uint64_t size,uint64_t address,uint32_t *value){
 if(!memory || size<4 || address>size-4 || (address&3))return false;
 *value=atomic_load_explicit((const _Atomic uint32_t *)(memory+address),memory_order_relaxed);return true;
}
static inline uint32_t pg_touch_context(const uint8_t *memory,uint64_t size){
 uint64_t info,ped,vehicle,check;uint32_t kind;
 if(!pg_context_u64(memory,size,20159720,&info) || !info || info>size || size-info<16)return 0;
 if(!pg_context_u64(memory,size,info+8,&ped) || !ped || ped>size || size-ped<5584)return 0;
 uint8_t flags=atomic_load_explicit((const _Atomic uint8_t *)(memory+ped+5291),memory_order_relaxed);
 if(!(flags&64))return 0;
 if(!pg_context_u64(memory,size,ped+5576,&vehicle) || !vehicle || vehicle>size || size-vehicle<3092)return 0;
 if(!pg_context_u32(memory,size,vehicle+3088,&kind) || kind>31)return 0;
 // Discard snapshots taken while the player or vehicle link is changing.
 if(!pg_context_u64(memory,size,info+8,&check) || check!=ped)return 0;
 if(!pg_context_u64(memory,size,ped+5576,&check) || check!=vehicle)return 0;
 if(!(atomic_load_explicit((const _Atomic uint8_t *)(memory+ped+5291),memory_order_relaxed)&64))return 0;
 // 0 on foot, otherwise the engine's vehicle type + 1 (car 1, plane 2, heli 9,
 // blimp 10, bike 12, bicycle 13, boat 14, submarine 16, ...).
 return kind + 1;
}
