// The app's graphics entry points (NativeGraphics.h), served by the native Metal renderer.
#include "NativeGraphics.h"
#include "MetalRenderer/MetalRenderer.h"
#import <Metal/Metal.h>
#include <stdlib.h>

extern "C" void pg_log(const char *);

void PGAttachMetalLayer(void *layer) { PGMetalRendererAttachLayer(layer); }
double PGRenderedFramesPerSecond(void) { return PGMetalRendererFPS(); }
void PGLogNativeGraphicsProgress(void) { PGMetalRendererLogProgress(); }
void PGSetPresentPacing(double seconds) { PGMetalRendererSetPresentInterval(seconds); }
void PGCaptureNativeFrame(const char *name) { PGMetalRendererCapture(name); }
void PGStartGraphics(void *memory, uint64_t memorySize, uint64_t ring, uint64_t ringSize, uint64_t) {
	if (!PGMetalRendererAvailable()) { pg_log("The Metal shader library is missing from the app: rebuild with the game's shaders."); return; }
	PGStartMetalRenderer(memory, memorySize, ring, ringSize);
}

int PGGPUReadsBC(void) {
	static int answer = -1;
	if (answer < 0) { id<MTLDevice> device = MTLCreateSystemDefaultDevice(); answer = 0; if (@available(iOS 16.4, *)) answer = device && device.supportsBCTextureCompression && !getenv("PG_FORCE_BC_DECODE"); }
	return answer;
}
