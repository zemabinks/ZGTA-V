#pragma once
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstddef>

// Diagnostic shadows only. No renderer object, Metal resource or lock is read
// by the reporting thread. Values are an independent atomic sample, not a
// transaction: only phase + operation are published together.
class PGGraphicsProgress {
 static_assert(std::atomic<uint64_t>::is_always_lock_free && std::atomic<uint32_t>::is_always_lock_free && std::atomic<std::atomic<uint32_t> *>::is_always_lock_free,"Progress reporting must remain lock-free");
public:
 enum Phase : uint32_t { NotStarted, Setup, RingIdle, Executing, NextDrawable, WaitSerial, SetupFailed,
  BufferShadow, BufferAllocate, BufferZero, BufferInstall, BufferArenaAcquire, BufferSlabCreate };
 struct Snapshot {
  Phase phase; uint32_t operation,head,tail,cursor;
  uint64_t submitted,completed,waitTarget,lastPresentNs;
  bool ringBound;
  uint32_t bufferId,bufferBytes,bufferBind,bufferMisc;
 };
 void buffer(uint32_t id,uint32_t bytes,uint32_t bind,uint32_t misc) {
  bid.store(id,std::memory_order_relaxed);bbytes.store(bytes,std::memory_order_relaxed);
  bbind.store(bind,std::memory_order_relaxed);bmisc.store(misc,std::memory_order_relaxed);
 }
 void bindRing(std::atomic<uint32_t> *header) { ring.store(header,std::memory_order_release); }
 void executing(uint32_t operation,uint32_t cursor) {
  at.store(cursor,std::memory_order_relaxed);
  activity.store((uint64_t(Executing)<<32)|operation,std::memory_order_relaxed);
 }
 void phase(Phase phase) {
  uint64_t old=activity.load(std::memory_order_relaxed);
  activity.store((uint64_t(phase)<<32)|uint32_t(old),std::memory_order_relaxed);
 }
 void waiting(uint64_t target) { waitTarget.store(target,std::memory_order_relaxed);phase(WaitSerial); }
 void waited() { waitTarget.store(0,std::memory_order_relaxed);phase(Executing); }
 void submitted(uint64_t serial) { sent.store(serial,std::memory_order_relaxed); }
 void completed(uint64_t serial) {
  uint64_t prior=done.load(std::memory_order_relaxed);
  while(prior<serial&&!done.compare_exchange_weak(prior,serial,std::memory_order_relaxed)){}
 }
 void presented(uint64_t ns) { presentNs.store(ns,std::memory_order_relaxed); }
 Snapshot snapshot() const {
  uint64_t a=activity.load(std::memory_order_relaxed);
  auto *header=ring.load(std::memory_order_acquire);
  return {Phase(a>>32),uint32_t(a),header?header[0].load(std::memory_order_acquire):0,
   header?header[1].load(std::memory_order_acquire):0,at.load(std::memory_order_relaxed),
   sent.load(std::memory_order_relaxed),done.load(std::memory_order_relaxed),
   waitTarget.load(std::memory_order_relaxed),presentNs.load(std::memory_order_relaxed),header!=nullptr,
   bid.load(std::memory_order_relaxed),bbytes.load(std::memory_order_relaxed),
   bbind.load(std::memory_order_relaxed),bmisc.load(std::memory_order_relaxed)};
 }
 static const char *name(Phase p) {
  switch(p){case Setup:return "setup";case RingIdle:return "ring-idle";case Executing:return "executing";
   case NextDrawable:return "nextDrawable";case WaitSerial:return "waitSerial";case SetupFailed:return "setup-failed";
   case BufferShadow:return "buffer-shadow";case BufferAllocate:return "buffer-allocate";
   case BufferZero:return "buffer-zero";case BufferInstall:return "buffer-install";
   case BufferArenaAcquire:return "buffer-arena";case BufferSlabCreate:return "buffer-slab-create";default:return "not-started";}
 }
 static int format(char *out,size_t size,const Snapshot &s,uint64_t nowNs) {
  int64_t age=s.lastPresentNs?(nowNs>=s.lastPresentNs?int64_t((nowNs-s.lastPresentNs)/1000000):0):-1;
  return std::snprintf(out,size,"[metal-progress] phase=%s op=%u ring=%u/%u bound=%u cursor=%u submitted=%llu completed=%llu waitSerial=%llu presentAgeMs=%lld lastBuffer=%u/%u bind=%u misc=%u (atomic sample)",
   name(s.phase),s.operation,s.head,s.tail,unsigned(s.ringBound),s.cursor,
   (unsigned long long)s.submitted,(unsigned long long)s.completed,(unsigned long long)s.waitTarget,(long long)age,
   s.bufferId,s.bufferBytes,s.bufferBind,s.bufferMisc);
 }
private:
 std::atomic<std::atomic<uint32_t> *> ring{nullptr};
 std::atomic<uint64_t> activity{0},sent{0},done{0},waitTarget{0},presentNs{0};
 std::atomic<uint32_t> at{0};
 std::atomic<uint32_t> bid{0},bbytes{0},bbind{0},bmisc{0};
};
