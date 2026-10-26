#pragma once
#include <cmath>
struct PGFrameRateWindow {
 double start=0,last=0,rate=0;
 unsigned frames=0;
 bool initialized=false;
 bool record(double now){
  if(!std::isfinite(now))return false;
  if(!initialized||now<last){start=last=now;frames=0;rate=0;initialized=true;return false;}
  if(now==last)return false;
  last=now;frames++;
  double elapsed=now-start;if(elapsed<0.5)return false;
  rate=frames/elapsed;start=now;frames=0;return true;
 }
};
