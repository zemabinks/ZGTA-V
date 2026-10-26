#pragma once
#include <stdint.h>
#include <stddef.h>
typedef struct {
  uint32_t version;
  uint8_t* (*memory)(void*, uint64_t*);
  uint32_t (*create)(void*,uint64_t,uint32_t,uint32_t,uint32_t,uint32_t);
  uint32_t (*profiler)(void*,uint64_t,uint64_t,uint32_t);
  uint32_t (*select)(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t);
} ZemaLanHost;
int32_t ZemaLanInstallHost(const ZemaLanHost*,size_t);
int32_t ZemaLanConfigure(uint32_t,uint64_t);
void ZemaLanConnected(int32_t);
int32_t ZemaLanTransportReady(void);
/* Must also be true before enabling experimental game launch. */
int32_t ZemaLanGameReady(void);
void ZemaLanPrepared(int32_t);
int32_t ZemaLanDeliver(const uint8_t*,size_t);
int32_t ZemaLanTakeOutgoing(uint8_t*,size_t);
uint32_t ZemaLanNetworkUp(void*);
uint32_t ZemaLanCreateSocket(void*,uint64_t,uint32_t,uint32_t,uint32_t,uint32_t);
uint32_t ZemaLanBind(void*,uint64_t);
uint32_t ZemaLanClose(void*,uint64_t);
uint32_t ZemaLanSend(void*,uint64_t,uint64_t,uint64_t,uint32_t,uint64_t);
uint32_t ZemaLanReceive(void*,uint64_t,uint64_t,uint64_t,uint32_t,uint64_t);
uint32_t ZemaLanLocalIp(void*,uint64_t);
uint32_t ZemaLanProfiler(void*,uint64_t,uint64_t,uint32_t);
uint32_t ZemaLanSelect(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t);
