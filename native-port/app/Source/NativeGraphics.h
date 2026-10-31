#pragma once
#include <stdint.h>
#include "NativePerformanceMetrics.h"
#ifdef __cplusplus
extern "C" {
#endif
void PGCaptureNativeFrame(const char *name);
double PGRenderedFramesPerSecond(void);
// One snapshot per call; intended for the existing zero-FPS health report.
void PGLogNativeGraphicsProgress(void);
void PGSetPresentPacing(double seconds);
void PGSetPerformanceSampling(int enabled);
int PGReadPerformanceMetrics(PGNativePerformanceMetrics *metrics);
void PGSetRenderingDiagnostics(int enabled);
uint32_t PGCopyRenderingDiagnostics(char *output, uint32_t capacity);
void PGRequestGraphicsMemoryTrim(void);
void PGAttachMetalLayer(void *layer);
void PGStartGraphics(void *memory,uint64_t memorySize,uint64_t ring,uint64_t ringSize,uint64_t debug);
// The GPU samples BC textures as they are (otherwise they are decoded, about 4 times larger).
int PGGPUReadsBC(void);
int PGIsLowMemoryDevice(void);
void PGSetMemoryProfile(int mode);
#ifdef __cplusplus
}
#endif
