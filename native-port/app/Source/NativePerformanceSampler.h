#pragma once
#include "NativePerformanceMetrics.h"
#include "NativeFrameMetrics.h"
#include <atomic>
#include <mutex>

// The renderer alone owns the accumulator. Readers copy a small published
// snapshot under a short mutex; no command buffer, fence, file or network wait.
class PGNativePerformanceSampler {
 std::atomic<bool> enabled{false};
 std::atomic<uint64_t> generation{0};
 uint64_t writerGeneration=UINT64_MAX, publishedGeneration=UINT64_MAX;
 double start=0;
 PGFrameMetricsWindow window;
 std::mutex mutex;
 PGNativePerformanceMetrics published{};
public:
 void enable(bool value) {
  if(enabled.exchange(value)!=value) generation.fetch_add(1);
 }
 template<class Gauges> void record(double now, double frameMS, uint64_t draws, const PGFrameWork& work, Gauges gauges) {
  if(!enabled.load())return;
  const auto current=generation.load();
  if(writerGeneration!=current||now<start) {writerGeneration=current;start=now;window.reset();}
  if(!window.record(frameMS,draws,work))return;
  if(now-start<1000)return;
  const auto s=window.snapshot();auto value=gauges();
  value.frames=s.frames;value.timeMS=now;value.frameMS=s.totalMs/s.frames;
  value.p95MS=s.p95Ms;value.maxMS=s.maxMs;
  value.pipelineWaitMS=s.work.pipeline/s.frames;value.gpuFenceWaitMS=s.work.gpuWait/s.frames;
  value.uploadMS=s.work.uploads/s.frames;value.uploadBytesPerFrame=s.work.uploadBytes/s.frames;
  {std::lock_guard<std::mutex> lock(mutex);published=value;publishedGeneration=current;}
  start=now;window.reset();
 }
 bool read(PGNativePerformanceMetrics* value) {
  if(!value||!enabled.load())return false;
  std::lock_guard<std::mutex> lock(mutex);
  if(publishedGeneration!=generation.load()||!published.frames)return false;
  *value=published;return true;
 }
};
