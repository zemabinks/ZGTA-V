#import <Foundation/Foundation.h>
#include "../Source/MetalRenderer/MRFallbackTextures.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <initializer_list>

int main() { @autoreleasepool {
    id<MTLDevice> device = MTLCreateSystemDefaultDevice();
    if (!device) { puts("SKIP: no Metal GPU on this runner; fallback texture test compiled only"); return 0; }
    id<MTLCommandQueue> queue = [device newCommandQueue];
    const MTLTextureType shapes[] = {MTLTextureType2D, MTLTextureType2DArray, MTLTextureType3D, MTLTextureTypeCube, MTLTextureTypeCubeArray};
    const MTLPixelFormat formats[] = {MTLPixelFormatRGBA8Unorm, MTLPixelFormatRGBA8Uint, MTLPixelFormatRGBA8Sint, MTLPixelFormatRGBA32Float};
    for (MTLTextureType shape : shapes) for (MTLPixelFormat format : formats) {
        MTLTextureDescriptor *desc = [MTLTextureDescriptor new];
        desc.textureType = shape; desc.pixelFormat = format;
        desc.width = desc.height = desc.depth = 1;
        desc.arrayLength = shape == MTLTextureType2DArray || shape == MTLTextureTypeCubeArray ? 2 : 1;
        desc.storageMode = MTLStorageModeShared; desc.usage = MTLTextureUsageShaderRead;
        id<MTLTexture> texture = [device newTextureWithDescriptor:desc]; assert(texture);
        NSUInteger slices = desc.arrayLength * (shape == MTLTextureTypeCube || shape == MTLTextureTypeCubeArray ? 6 : 1);
        NSUInteger bytes = format == MTLPixelFormatRGBA32Float ? 16 : 4;
        uint32_t poison[4] = {0x3f800000, 0x3f800000, 0x3f800000, 0x3f800000};
        for (NSUInteger slice = 0; slice < slices; slice++)
            [texture replaceRegion:MTLRegionMake3D(0,0,0,1,1,1) mipmapLevel:0 slice:slice withBytes:poison bytesPerRow:bytes bytesPerImage:shape == MTLTextureType3D ? bytes : 0];
        assert(PGInitializeFallbackTexture(texture, queue));
        for (NSUInteger slice = 0; slice < slices; slice++) {
            uint32_t pixel[4] = {1,1,1,1}, zero[4] = {};
            [texture getBytes:pixel bytesPerRow:bytes bytesPerImage:shape == MTLTextureType3D ? bytes : 0 fromRegion:MTLRegionMake3D(0,0,0,1,1,1) mipmapLevel:0 slice:slice];
            assert(!memcmp(pixel, zero, bytes));
        }
    }
    NSError *error = nil;
    NSString *source = @"#include <metal_stdlib>\nusing namespace metal;\n"
        "kernel void readDepth(depth2d<float> t [[texture(0)]], device float* out [[buffer(0)]]) {out[0]=t.read(uint2(0));}\n"
        "kernel void readMS(texture2d_ms<float> t [[texture(0)]], device float* out [[buffer(0)]]) {for(uint s=0;s<4;s++)out[s]=t.read(uint2(0),s).r;}\n";
    id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error]; assert(library);
    for (bool depth : {true, false}) {
        if (!depth && ![device supportsTextureSampleCount:4]) continue;
        MTLTextureDescriptor *desc = [MTLTextureDescriptor new];
        desc.textureType = depth ? MTLTextureType2D : MTLTextureType2DMultisample;
        desc.pixelFormat = depth ? MTLPixelFormatDepth32Float : MTLPixelFormatRGBA8Unorm;
        desc.width = desc.height = 1; desc.sampleCount = depth ? 1 : 4;
        desc.storageMode = MTLStorageModePrivate; desc.usage = MTLTextureUsageShaderRead | MTLTextureUsageRenderTarget;
        id<MTLTexture> texture = [device newTextureWithDescriptor:desc]; assert(texture);
        id<MTLCommandBuffer> poisonCommand = [queue commandBuffer];
        MTLRenderPassDescriptor *poison = [MTLRenderPassDescriptor renderPassDescriptor];
        if (depth) { poison.depthAttachment.texture=texture; poison.depthAttachment.loadAction=MTLLoadActionClear; poison.depthAttachment.storeAction=MTLStoreActionStore; poison.depthAttachment.clearDepth=0.75; }
        else { poison.colorAttachments[0].texture=texture; poison.colorAttachments[0].loadAction=MTLLoadActionClear; poison.colorAttachments[0].storeAction=MTLStoreActionStore; poison.colorAttachments[0].clearColor=MTLClearColorMake(1,1,1,1); }
        [[poisonCommand renderCommandEncoderWithDescriptor:poison] endEncoding]; [poisonCommand commit];
        assert(PGInitializeFallbackTexture(texture, queue));
        id<MTLBuffer> output = [device newBufferWithLength:16 options:MTLResourceStorageModeShared];
        memset(output.contents, 0xff, 16);
        id<MTLFunction> function = [library newFunctionWithName:depth ? @"readDepth" : @"readMS"];
        id<MTLComputePipelineState> pipeline = [device newComputePipelineStateWithFunction:function error:&error]; assert(pipeline);
        id<MTLCommandBuffer> read = [queue commandBuffer];
        id<MTLComputeCommandEncoder> encoder = [read computeCommandEncoder];
        [encoder setComputePipelineState:pipeline]; [encoder setTexture:texture atIndex:0]; [encoder setBuffer:output offset:0 atIndex:0];
        [encoder dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)]; [encoder endEncoding];
        [read commit]; [read waitUntilCompleted]; assert(read.status == MTLCommandBufferStatusCompleted);
        for (int s=0; s<(depth ? 1 : 4); s++) assert(((float *)output.contents)[s] == 0);
    }
    puts("PASS: poisoned color/array/cube/3D fallbacks cleared; private depth and multisample GPU reads are zero");
    return 0;
} }
