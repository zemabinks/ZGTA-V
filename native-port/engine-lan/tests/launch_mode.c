#include "ZemaExperimental.h"
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
static int ready, readiness_calls;
static bool legacy;
int ZemaLanGameReady(void){readiness_calls++;return ready;}
bool MugoatOnlineEnabled(void){return legacy;}
int main(int argc,char** argv){
  assert(argc==2);assert(!ZemaLabEnabled()&&!ZemaGameIsOnline());
  if(!strcmp(argv[1],"offline")){
    assert(ZemaLabSelectMode(0));assert(readiness_calls==0);
    ready=1;assert(!ZemaLabEnabled()&&!ZemaGameIsOnline());
    assert(!ZemaLabSelectMode(1));assert(ZemaLabSelectMode(0));
  }else if(!strcmp(argv[1],"lan")){
    assert(!ZemaLabSelectMode(1));assert(!ZemaLabEnabled());
    ready=1;assert(ZemaLabSelectMode(1));assert(ZemaLabEnabled()&&ZemaGameIsOnline());
    ready=0;assert(ZemaLabEnabled()&&ZemaGameIsOnline());
    assert(!ZemaLabSelectMode(0));assert(ZemaLabSelectMode(1));
  }else if(!strcmp(argv[1],"legacy")){
    legacy=true;assert(ZemaGameIsOnline()&&!ZemaLabEnabled());
    legacy=false;assert(!ZemaGameIsOnline());
  }else assert(0);
  puts("EXPLICIT_LAUNCH_MODE_OFFLINE_NO_RELAY_AND_DISCONNECT_STABILITY_PASS");
}
