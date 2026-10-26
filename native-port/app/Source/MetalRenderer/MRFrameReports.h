#pragma once
#import <Metal/Metal.h>
#include <stdint.h>

namespace mr {
// Renderer-thread time per frame by kind (milliseconds; uploadBytes in bytes).
struct FrameWork { double idle = 0, pipeline = 0, uploads = 0, uploadBytes = 0, gpuWait = 0, submit = 0; };
void frameReportsInstall(id<MTLDevice> device);
void frameReportsRecord(double timeMs, double frameMs, uint64_t draws, bool world, const FrameWork &work);
}  // namespace mr
