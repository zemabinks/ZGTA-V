#include "../Source/NativeFrameMetrics.h"
#include <cassert>
#include <cstdio>
#include <limits>
int main(){
 PGFrameMetricsWindow window;
 for(int i=0;i<95;i++)assert(window.record(30,500,{10,1,2,3,1024,4,5}));
 for(int i=0;i<4;i++)assert(window.record(60,600,{20,2,4,6,2048,8,10}));
 assert(window.record(1234,700,{1000,30,20,100,1048576,40,44}));
 auto s=window.snapshot();assert(s.frames==100&&s.draws==50600&&s.totalMs==4324);assert(s.p95Ms==30&&s.p99Ms==60&&s.maxMs==1234);assert(s.over33==5&&s.over50==5&&s.over100==1&&s.over250==1);assert(s.worstWork.uploads==100&&s.worstWork.idle==1000);assert(s.work.uploadBytes==95*1024+4*2048+1048576);assert(std::abs(s.fps()-100000.0/4324)<.0001);
 auto before=window.snapshot();assert(!window.record(0,1,{}));assert(!window.record(-1,1,{}));assert(!window.record(std::numeric_limits<double>::infinity(),1,{}));assert(!window.record(1,1,{-1,0,0,0,0,0,0}));assert(!window.record(1,1,{0,0,0,0,std::numeric_limits<double>::quiet_NaN(),0,0}));assert(window.snapshot().frames==before.frames);
 window.reset();assert(window.snapshot().frames==0&&window.percentile(.99)==0);assert(window.record(33.33333333333333,100,{}));assert(window.snapshot().over33==0);assert(window.record(33.334,100,{}));assert(window.snapshot().over33==1);
 window.reset();for(int i=0;i<2000;i++)assert(window.record(33.333333,100,{}));assert(window.snapshot().p95Ms==34&&window.snapshot().p99Ms==34);
 window.reset();for(int i=0;i<100;i++)assert(window.record(2000+i,100,{}));assert(window.snapshot().p95Ms==2099);assert(window.snapshot().maxMs==2099);
 puts("PASS: bounded frame metrics, 1 ms percentile upper bounds, overflow upper bound, 30 FPS threshold, long stalls, exact worst-frame work, totals, invalid data and reset.");
}
