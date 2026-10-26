#pragma once
#import <Metal/Metal.h>
#include <stdint.h>

// D3D11 unbound resources read zero. A newly allocated Metal texture is not
// a substitute until its contents have been explicitly initialized.
static inline bool PGInitializeFallbackTexture(id<MTLTexture> texture, id<MTLCommandQueue> queue) {
    if (!texture) return false;
    NSUInteger slices = texture.arrayLength;
    if (texture.textureType == MTLTextureTypeCube || texture.textureType == MTLTextureTypeCubeArray) slices *= 6;
    if (texture.storageMode == MTLStorageModeShared) {
        const uint32_t zero[4] = {};
        NSUInteger bytes = texture.pixelFormat == MTLPixelFormatRGBA32Float ? 16 : 4;
        for (NSUInteger slice = 0; slice < slices; slice++) {
            [texture replaceRegion:MTLRegionMake3D(0, 0, 0, 1, 1, 1) mipmapLevel:0 slice:slice
                         withBytes:zero bytesPerRow:bytes bytesPerImage:texture.textureType == MTLTextureType3D ? bytes : 0];
        }
        return true;
    }
    // Depth and multisample textures require GPU initialization. Use a separate
    // command buffer on the SAME queue, committed before the sampling buffer.
    // This must not end or replace an active renderer pass during bindStage().
    id<MTLCommandBuffer> command = [queue commandBuffer];
    if (!command) return false;
    command.label = @"Initialize zero fallback texture";
    for (NSUInteger slice = 0; slice < slices; slice++) {
        MTLRenderPassDescriptor *pass = [MTLRenderPassDescriptor renderPassDescriptor];
        if (texture.pixelFormat == MTLPixelFormatDepth32Float) {
            pass.depthAttachment.texture = texture;
            pass.depthAttachment.slice = slice;
            pass.depthAttachment.loadAction = MTLLoadActionClear;
            pass.depthAttachment.storeAction = MTLStoreActionStore;
            pass.depthAttachment.clearDepth = 0;
        } else {
            pass.colorAttachments[0].texture = texture;
            pass.colorAttachments[0].slice = slice;
            pass.colorAttachments[0].loadAction = MTLLoadActionClear;
            pass.colorAttachments[0].storeAction = MTLStoreActionStore;
            pass.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 0);
        }
        id<MTLRenderCommandEncoder> encoder = [command renderCommandEncoderWithDescriptor:pass];
        if (!encoder) return false;
        [encoder endEncoding];
    }
    [command commit];
    return true;
}
