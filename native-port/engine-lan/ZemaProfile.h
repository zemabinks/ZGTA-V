#ifndef ZEMA_PROFILE_H
#define ZEMA_PROFILE_H
#include <stdint.h>
#include <stddef.h>
int32_t ZemaProfileConfigure(uint32_t,const uint8_t*,size_t);
/* Display-name change only, before first LAN admission; caller persists or rolls back. */
int32_t ZemaProfileRename(const uint8_t*,size_t);
int32_t ZemaProfileReady(void);
uint32_t ZemaProfileId(void);
int32_t ZemaProfileName(uint8_t*,size_t);
/* Read: -1 missing, -2 invalid/unconfigured, -3 short buffer. */
int32_t ZemaProfileRead(const uint8_t*,size_t,uint8_t*,size_t);
int32_t ZemaProfileWrite(const uint8_t*,size_t,const uint8_t*,size_t);
uint64_t ZemaProfileStat(const uint8_t*,size_t);
void ZemaProfileDeleteSlot(int32_t);
uint64_t ZemaProfileRevision(void);
/* Export: negative required size; import is before the first write only. */
int32_t ZemaProfileExport(uint8_t*,size_t);
int32_t ZemaProfileImport(const uint8_t*,size_t);
#endif
