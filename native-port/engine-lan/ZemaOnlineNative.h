#ifndef ZEMA_ONLINE_NATIVE_H
#define ZEMA_ONLINE_NATIVE_H
#include "ZemaOnlineHost.h"
#include "ZemaProfile.h"
typedef struct ZemaEngineLANHooks ZemaEngineLANHooks;
void ZemaOnlineBindOriginals(ZemaOnlineOriginals*,ZemaEngineLANHooks*);
int ZemaLanAttachOnlineEngine(const ZemaOnlineHost*);
#endif
