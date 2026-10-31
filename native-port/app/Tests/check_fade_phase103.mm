// Bounded Mac offscreen check: translated fallback versus the original owner's
// globalFade identity-vector predicate. No game or app execution.
// Usage: check-fade-phase103 <one-record-translated-white-fragment.jsonl>
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <array>
#include <cstring>
#include <iostream>

int main(int argc, char **argv) {
 @autoreleasepool {
  if (argc != 2) return 2;
  id<MTLDevice> device=MTLCreateSystemDefaultDevice();
  if (!device) { std::cerr << "No Metal device available\n";return 3; }
  NSData *input=[NSData dataWithContentsOfFile:[NSString stringWithUTF8String:argv[1]]];
  NSDictionary *record=input?[NSJSONSerialization JSONObjectWithData:input options:0 error:nil]:nil;
  if (!record || ![record[@"h"] isEqual:@"phase103"]) return 4;
  NSString *oracle=@"#include <metal_stdlib>\nusing namespace metal;\n"
   "vertex float4 zgta_fade_quad(uint i [[vertex_id]]) { float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};return float4(p[i],0,1); }\n"
   "fragment float4 original(float4 p [[position]],constant float4& globalFade [[buffer(0)]]) {\n"
   " float4 identity[4]={float4(1,0,0,0),float4(0,1,0,0),float4(0,0,1,0),float4(0,0,0,1)};\n"
   " uint2 xy=uint2(max(p.xy,float2(0)));uint phase=(xy.x&1)+2*(xy.y&1);\n"
   " if(dot(globalFade,identity[phase])<1.0) discard_fragment();return float4(1); }\n";
  MTLCompileOptions *options=[MTLCompileOptions new];options.languageVersion=MTLLanguageVersion2_4;
  NSError *error=nil;
  id<MTLLibrary> original=[device newLibraryWithSource:oracle options:options error:&error];
  if (!original) {std::cerr<<"oracle compile: "<<(error.localizedDescription.UTF8String ?: "no compiler error")<<"\n";return 5;}
  id<MTLLibrary> fallback=[device newLibraryWithSource:record[@"source"] options:options error:&error];
  if (!fallback) {std::cerr<<"fallback compile: "<<(error.localizedDescription.UTF8String ?: "no compiler error")<<"\n";return 5;}
  id<MTLCommandQueue> queue=[device newCommandQueue];
  MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:8 height:8 mipmapped:NO];
  td.storageMode=MTLStorageModeManaged;td.usage=MTLTextureUsageRenderTarget;
  id<MTLTexture> texture=[device newTextureWithDescriptor:td];
  auto pipeline=[&](id<MTLFunction> fragment){
   MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];
   pd.vertexFunction=[original newFunctionWithName:@"zgta_fade_quad"];pd.fragmentFunction=fragment;
   pd.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA8Unorm;
   return [device newRenderPipelineStateWithDescriptor:pd error:&error];
  };
  id<MTLRenderPipelineState> oraclePipeline=pipeline([original newFunctionWithName:@"original"]);
  if (!texture || !oraclePipeline) return 6;
  std::array<id<MTLRenderPipelineState>,32> pipelines{};
  for(uint32_t code=1;code<32;code++){
   MTLFunctionConstantValues *values=[MTLFunctionConstantValues new];
   [values setConstantValue:&code type:MTLDataTypeUInt atIndex:0];
   id<MTLFunction> function=[fallback newFunctionWithName:@"s_phase103_stipple" constantValues:values error:&error];
   pipelines[code]=function?pipeline(function):nil;
   if(!pipelines[code]) {std::cerr<<"code "<<code<<": "<<(error.localizedDescription.UTF8String ?: "no compiler error")<<"\n";return 7;}
  }
  auto render=[&](id<MTLRenderPipelineState> state,const float* fade){
   MTLRenderPassDescriptor *pass=[MTLRenderPassDescriptor renderPassDescriptor];
   pass.colorAttachments[0].texture=texture;pass.colorAttachments[0].loadAction=MTLLoadActionClear;
   pass.colorAttachments[0].storeAction=MTLStoreActionStore;pass.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);
   id<MTLCommandBuffer> command=[queue commandBuffer];id<MTLRenderCommandEncoder> encoder=[command renderCommandEncoderWithDescriptor:pass];
   [encoder setRenderPipelineState:state];if(fade)[encoder setFragmentBytes:fade length:16 atIndex:0];
   [encoder drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];[encoder endEncoding];
   id<MTLBlitCommandEncoder> blit=[command blitCommandEncoder];[blit synchronizeResource:texture];[blit endEncoding];
   [command commit];[command waitUntilCompleted];
   if(command.status!=MTLCommandBufferStatusCompleted){std::cerr<<(command.error.localizedDescription.UTF8String ?: "no command error")<<"\n";exit(8);}
   std::array<uint8_t,256> pixels{};[texture getBytes:pixels.data() bytesPerRow:32 fromRegion:MTLRegionMake2D(0,0,8,8) mipmapLevel:0];return pixels;
  };
  size_t compared=0;
  // All 16 phase masks include the original five masks and their complements;
  // arbitrary masks make x/y ordering and all exact specialization codes visible.
  for(uint32_t mask=0;mask<16;mask++){
   float fade[4];for(uint32_t k=0;k<4;k++)fade[k]=(mask>>k)&1;
   auto expected=render(oraclePipeline,fade),actual=render(pipelines[16|mask],nullptr);
   if(expected!=actual){std::cerr<<"oracle mismatch phase mask "<<mask<<"\n";return 9;}
   for(uint32_t y=0;y<8;y++)for(uint32_t x=0;x<8;x++){
    uint8_t wanted=((mask>>((x&1)+2*(y&1)))&1)?255:0;
    if(actual[(y*8+x)*4]!=wanted){std::cerr<<"coordinate mismatch\n";return 10;}compared++;
   }
  }
  for(uint32_t code=1;code<16;code++){
   auto actual=render(pipelines[code],nullptr);
   for(uint32_t y=0;y<8;y++)for(uint32_t x=0;x<8;x++){
    uint32_t rank=4*((((x^y)&1)<<1)|(y&1))+(((((x^y)>>1)&1)<<1)|((y>>1)&1));
    if(actual[(y*8+x)*4]!=(rank<code?255:0)){std::cerr<<"legacy mismatch\n";return 11;}compared++;
   }
  }
  std::cout<<"Mac Metal offscreen PASS; device="<<device.name.UTF8String<<"; exact masks=16; legacy levels=15; compared pixels="<<compared<<"\n";
  return 0;
 }
}
