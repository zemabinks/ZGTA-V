/* Typed glue between the pinned engine adapter and Rust virtual sockets.
 * Not included in the standard app target; opt-in experimental integration.
 */
#include "ZemaEngineLAN.h"
#include "ZemaLanBackend.h"
#include "ZemaOnlineNative.h"
_Static_assert(sizeof(ZemaLanHost)==40,"Unexpected 64-bit native callback ABI");
extern uint8_t* mugoat_memory_data(void*,uint64_t*);
static u32 original_create(void* i,u64 s,u32 p,u32 n,u32 b,u32 f) {
  return w2c_game_f13822_zema_lan_original((w2c_game*)i,s,p,n,b,f);
}
static u32 original_profiler(void* i,u64 p,u64 n,u32 f) {
  return w2c_game_f13579_zema_lan_original((w2c_game*)i,p,n,f);
}
static u32 original_select(void* i,u32 c,u64 r,u64 w,u64 e,u64 t) {
  return w2c_game_f13828_zema_lan_original((w2c_game*)i,c,r,w,e,t);
}
static u32 create(w2c_game* i,u64 s,u32 p,u32 n,u32 b,u32 f) {return ZemaLanCreateSocket(i,s,p,n,b,f);}
static u32 bind_socket(w2c_game* i,u64 s) {return ZemaLanBind(i,s);}
/* The pinned NativeClose takes this same engine lock, invalidates +8, then
 * unlocks. Reclaim the virtual handle inside that critical section. */
extern void w2c_game_f111(w2c_game*,u64);
extern void w2c_game_f113(w2c_game*,u64);
static void close_socket(w2c_game* i,u64 s) {
  w2c_game_f111(i,s+32);ZemaLanClose(i,s);w2c_game_f113(i,s+32);
}
static u32 send_socket(w2c_game* i,u64 s,u64 t,u64 d,u32 n,u64 e) {return ZemaLanSend(i,s,t,d,n,e);}
static u32 receive_socket(w2c_game* i,u64 s,u64 f,u64 b,u32 n,u64 e) {return ZemaLanReceive(i,s,f,b,n,e);}
static u32 select_socket(w2c_game* i,u32 c,u64 r,u64 w,u64 e,u64 t) {return ZemaLanSelect(i,c,r,w,e,t);}
static u32 ip(w2c_game* i,u64 p) {return ZemaLanLocalIp(i,p);}
static u32 profiler(w2c_game* i,u64 p,u64 n,u32 f) {return ZemaLanProfiler(i,p,n,f);}
static int attach(const ZemaOnlineHost* online) {
  if(!ZemaLanTransportReady())return 0;
  const ZemaLanHost host={.version=1,.memory=mugoat_memory_data,.create=original_create,
    .profiler=original_profiler,.select=original_select};
  if(!ZemaLanInstallHost(&host,sizeof host))return 0;
  ZemaEngineLANHooks hooks={.create_socket=create,.socket_bind=bind_socket,.socket_close=close_socket,
    .socket_send=send_socket,.socket_receive=receive_socket,.socket_select=select_socket,
    .local_ip_address=ip,.public_ip_address=ip,.profiler_push=profiler};
  if(online) {
    ZemaOnlineHost services=*online;
    services.memory=mugoat_memory_data;
    ZemaOnlineBindOriginals(&services.originals,&hooks);
    if(!ZemaOnlineInstallHost(&services,sizeof services))return 0;
  }
  return ZemaEngineLANInstall(&hooks);
}
/* Transport-only boundary, retained for the preceding isolated milestone. */
int ZemaLanAttachEngine(void) { return attach(NULL); }
/* Caller supplies verified typed Social Club tables, engine allocator and the
 * isolated durable profile host. The standard app never invokes this entry. */
int ZemaLanAttachOnlineEngine(const ZemaOnlineHost* online) {
  if(!online||!ZemaProfileReady())return 0;
  return attach(online);
}
