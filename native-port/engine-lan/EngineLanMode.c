#include "ZemaExperimental.h"
#include "ZemaLanBackend.h"
#include "MugoatOnline.h"
#include <stdatomic.h>

/* Process-local launch selection. A connected relay alone never enables LAN,
 * and a later disconnect never silently changes a running game into offline. */
static atomic_int selected_mode;
int ZemaLabSelectMode(int lan) {
  int desired=lan?2:1, current=atomic_load(&selected_mode);
  if(current)return current==desired;
  if(lan&&!ZemaLanGameReady())return 0;
  int expected=0;
  return atomic_compare_exchange_strong(&selected_mode,&expected,desired)||expected==desired;
}
int ZemaLabEnabled(void){return atomic_load(&selected_mode)==2;}
int ZemaGameIsOnline(void){return ZemaLabEnabled()||MugoatOnlineEnabled();}
