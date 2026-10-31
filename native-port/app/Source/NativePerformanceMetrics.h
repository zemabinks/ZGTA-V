#pragma once
#include <stdint.h>
// Local, opt-in renderer aggregates. Wait times are CPU waits, not GPU execution
// timestamps. Allocated bytes are Metal's estimate, not the process footprint.
typedef struct {
 uint64_t frames;
 double timeMS, frameMS, p95MS, maxMS;
 double pipelineWaitMS, gpuFenceWaitMS, uploadMS, uploadBytesPerFrame;
 uint64_t metalBytes, textureBytes, textureShadowBytes, pooledBufferBytes;
 uint64_t bufferArenaBytes, cacheTrimmedBytes, pendingPipelines;
 uint64_t arenaLiveBytes, arenaRequestedBytes, arenaPendingBytes, arenaReusableBytes;
 uint64_t textureCreateFailures, textureDecodeFailures;
} PGNativePerformanceMetrics;
