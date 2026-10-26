#include "ZemaExperimental.h"
#include "ZemaOnlineNative.h"
#include "ZemaLanBackend.h"
#include "ZemaSocial.h"
extern int ZemaExperimentalCommit(void);
extern unsigned char* mugoat_memory_data(void*,uint64_t*);
static int commit(void* instance){(void)instance;return ZemaExperimentalCommit();}
int ZemaLabAttach(void* instance){
  (void)instance;
  const ZemaOnlineHost host={.version=1,.memory=mugoat_memory_data,.allocate=ZemaEngineAllocate,
    .release=ZemaEngineRelease,.prepare_interfaces=ZemaSocialPrepare,.commit_profile=commit};
  return ZemaLabEnabled()&&ZemaLanAttachOnlineEngine(&host);
}
