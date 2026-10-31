#pragma once
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
void *PGDecodeBC(int format,uint32_t width,uint32_t height,uint32_t depth,uint32_t rowPitch,uint32_t rowsPerImage,const void *source,size_t sourceSize,size_t *decodedSize);
// Existing BC1 UNORM fallback pixels packed as Metal A1BGR5 words. This is
// byte-identical to PGDecodeBC(1, ...) followed by the renderer's 16-bit pack;
// it allocates only the packed output. The caller owns/free()s that output.
void *PGDecodeBC1Packed(uint32_t width,uint32_t height,uint32_t depth,uint32_t rowPitch,uint32_t rowsPerImage,const void *source,size_t sourceSize,size_t *decodedSize);
// Original decoder used only by the explicit benchmark reference option.
void *PGDecodeBCReference(int format,uint32_t width,uint32_t height,uint32_t depth,uint32_t rowPitch,uint32_t rowsPerImage,const void *source,size_t sourceSize,size_t *decodedSize);
#ifdef __cplusplus
}
#endif
