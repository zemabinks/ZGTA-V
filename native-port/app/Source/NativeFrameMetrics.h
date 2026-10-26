#pragma once
#include <array>
#include <cmath>
#include <cstdint>
#include <algorithm>

struct PGFrameWork {
 double idle=0,pipeline=0,modules=0,uploads=0,uploadBytes=0,gpuWait=0,submit=0;
 void add(const PGFrameWork &other){idle+=other.idle;pipeline+=other.pipeline;modules+=other.modules;uploads+=other.uploads;uploadBytes+=other.uploadBytes;gpuWait+=other.gpuWait;submit+=other.submit;}
};
struct PGFrameMetricsSnapshot {
 uint64_t frames=0,draws=0,over33=0,over50=0,over100=0,over250=0;
 double totalMs=0,maxMs=0,p95Ms=0,p99Ms=0;
 PGFrameWork work,worstWork;
 double fps()const{return totalMs>0?frames*1000.0/totalMs:0;}
};
struct PGFrameMetricsWindow {
 std::array<uint32_t,1002> histogram{}; // ceil milliseconds, final bucket overflow
 PGFrameMetricsSnapshot totals;
 bool record(double frameMs,uint64_t draws,const PGFrameWork &work){
  if(!std::isfinite(frameMs)||frameMs<=0)return false;
  const double fields[]={work.idle,work.pipeline,work.modules,work.uploads,work.uploadBytes,work.gpuWait,work.submit};
  for(double value:fields)if(!std::isfinite(value)||value<0)return false;
  totals.frames++;totals.draws+=draws;totals.totalMs+=frameMs;
  totals.over33+=frameMs>1000.0/30;totals.over50+=frameMs>50;totals.over100+=frameMs>100;totals.over250+=frameMs>250;
  if(frameMs>totals.maxMs){totals.maxMs=frameMs;totals.worstWork=work;}
  totals.work.add(work);histogram[(size_t)std::min(1001.0,std::ceil(frameMs))]++;return true;
 }
 double percentile(double p)const{
  if(!totals.frames)return 0;
  uint64_t target=(uint64_t)std::ceil(totals.frames*p),count=0;
  for(size_t i=0;i<histogram.size();i++){count+=histogram[i];if(count>=target)return i==histogram.size()-1?totals.maxMs:(double)i;}
  return totals.maxMs;
 }
 PGFrameMetricsSnapshot snapshot()const{auto value=totals;value.p95Ms=percentile(.95);value.p99Ms=percentile(.99);return value;}
 void reset(){histogram.fill(0);totals={};}
};
