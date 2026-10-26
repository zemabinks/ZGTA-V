#pragma once
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
void PGCaptureNativeFrame(const char *name);
double PGRenderedFramesPerSecond(void);
// One snapshot per call; intended for the existing zero-FPS health report.
void PGLogNativeGraphicsProgress(void);
void PGSetPresentPacing(double seconds);
void PGAttachMetalLayer(void *layer);
void PGStartGraphics(void *memory,uint64_t memorySize,uint64_t ring,uint64_t ringSize,uint64_t debug);
// The GPU samples BC textures as they are (otherwise they are decoded, about 4 times larger).
int PGGPUReadsBC(void);
#ifdef __cplusplus
}
#endif
