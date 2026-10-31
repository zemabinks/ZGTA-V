#pragma once
#include <array>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <vector>

// Explicit local rendering capture only. No GPU waits, resource retention,
// producer-memory reads, file writes or work during ordinary FPS measurements.
struct PGRenderingObservation {
 uint64_t frame=0, snapshotFrame=0;
 uint32_t kind=0, count=0, instances=0, vertexBuffer=0, target=0, depth=0;
 uint32_t stipple=0, constantBuffer=0, version=0, first=0, num=0, metalIndex=0;
 uint32_t shadow[4]{}, bound[4]{};
 bool shadowValid=false, boundValid=false, encoded=false;
 char vertexShader[17]{}, pixelShader[17]{}, outcome[24]{};
};
class PGRenderingDiagnostics {
public:
 static constexpr size_t Limit=256;
 struct Snapshot {
  uint64_t generation=0, observedDraws=0, cbCopies=0, cbCopiesUpdated=0, cbCopiesUnsupported=0;
  std::vector<PGRenderingObservation> observations;
 };
private:
 std::atomic<bool> enabled{false};
 std::atomic<uint64_t> generation{0}, draws{0}, copies{0}, updated{0}, unsupported{0};
 uint64_t writerGeneration=0, startFrame=0, quotaFrame=UINT64_MAX;
 uint32_t fullCount=0, partialCount=0;
 std::mutex mutex;
 std::array<PGRenderingObservation,Limit> observations{};
 size_t count=0;
 void reset(uint64_t current, uint64_t frame) {
  std::lock_guard<std::mutex> lock(mutex);
  writerGeneration=current;startFrame=frame;quotaFrame=UINT64_MAX;count=0;
 }
public:
 void enable(bool value) {
  if(value && !enabled.load(std::memory_order_acquire)) {
   draws=0;copies=0;updated=0;unsupported=0;
   generation.fetch_add(1,std::memory_order_release);
  }
  enabled.store(value,std::memory_order_release);
 }
 bool active() const {return enabled.load(std::memory_order_relaxed);}
 bool wantsFrame(uint64_t frame) {
  if(!active())return false;
  draws.fetch_add(1,std::memory_order_relaxed);
  const uint64_t current=generation.load(std::memory_order_acquire);
  if(writerGeneration!=current)reset(current,frame);
  if(frame<startFrame || frame-startFrame>=16*60 || (frame-startFrame)%60)return false;
  if(quotaFrame!=frame){quotaFrame=frame;fullCount=partialCount=0;}
  return count<Limit && (fullCount<4 || partialCount<12);
 }
 void record(const PGRenderingObservation& value) {
  if(!active() || value.frame!=quotaFrame || count>=Limit)return;
  bool partial=value.stipple!=0;
  for(uint32_t word:value.shadow)if(word!=0x3f800000u)partial=true;
  if(partial ? partialCount>=12 : fullCount>=4)return;
  std::lock_guard<std::mutex> lock(mutex);
  if(writerGeneration!=generation.load(std::memory_order_acquire))return;
  observations[count++]=value;
  if(partial)++partialCount;else ++fullCount;
 }
 void copy(bool wasUpdated, bool wasUnsupported) {
  if(!active())return;
  copies.fetch_add(1,std::memory_order_relaxed);
  if(wasUpdated)updated.fetch_add(1,std::memory_order_relaxed);
  if(wasUnsupported)unsupported.fetch_add(1,std::memory_order_relaxed);
 }
 Snapshot read() {
  Snapshot result;result.generation=generation.load(std::memory_order_acquire);
  result.observedDraws=draws.load();result.cbCopies=copies.load();
  result.cbCopiesUpdated=updated.load();result.cbCopiesUnsupported=unsupported.load();
  std::lock_guard<std::mutex> lock(mutex);
  if(writerGeneration==result.generation)result.observations.assign(observations.begin(),observations.begin()+count);
  return result;
 }
};
