#pragma once
#include <stdint.h>
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
// Native Metal renderer (Source/MetalRenderer): executes the game's graphics command ring directly on Metal.
bool PGMetalRendererAvailable(void);
void PGMetalRendererAttachLayer(void *layer);
void PGStartMetalRenderer(void *memory, uint64_t memorySize, uint64_t ring, uint64_t ringSize);
double PGMetalRendererFPS(void);
// One atomic diagnostic snapshot; caller supplies the existing health cadence.
void PGMetalRendererLogProgress(void);
// Minimum time each frame stays on screen (1/cap), 0 to present as soon as possible.
void PGMetalRendererSetPresentInterval(double seconds);
void PGMetalRendererCapture(const char *name);
#ifdef __cplusplus
}
#endif
