#include "NativeFrameRate.h"
#include <cassert>
#include <cstdio>
#include <initializer_list>
int main(){
 for(double target:{30.0,60.0,120.0}){
  PGFrameRateWindow window;for(unsigned i=0;i<600;i++)window.record(i/target);
  assert(std::abs(window.rate-target)<0.001);
  assert(!window.record(window.last));assert(!window.record(NAN));
  assert(window.record(window.last+2)&&window.rate<target/2);
  assert(!window.record(0)&&window.rate==0);
 }
 puts("PASS: actual presentation FPS at 30/60/120 Hz, duplicates, nonfinite times, stalls and clock resets.");
}
