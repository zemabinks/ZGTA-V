#pragma once
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
void *PGDecodeBC(int format,uint32_t width,uint32_t height,uint32_t depth,uint32_t rowPitch,uint32_t rowsPerImage,const void *source,size_t sourceSize,size_t *decodedSize);
// Original decoder used only by the explicit benchmark reference option.
void *PGDecodeBCReference(int format,uint32_t width,uint32_t height,uint32_t depth,uint32_t rowPitch,uint32_t rowsPerImage,const void *source,size_t sourceSize,size_t *decodedSize);
#ifdef __cplusplus
}
#endif
