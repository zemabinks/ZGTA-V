#include "BCTextureDecoder.h"
#include <stdlib.h>
#include <string.h>
#define BCDEC_STATIC
#define BCDEC_IMPLEMENTATION
#include "../Tools/bcdec/bcdec.h"
#include "BCTextureDecoderReference.inc"

static void decodeBlock(int format,const void *compressed,void *destination,int pitch){
  switch(format){
    case 1:bcdec_bc1(compressed,destination,pitch);break;
    case 2:bcdec_bc2(compressed,destination,pitch);break;
    case 3:bcdec_bc3(compressed,destination,pitch);break;
    case 4:bcdec_bc4(compressed,destination,pitch);break;
    case 5:bcdec_bc5(compressed,destination,pitch);break;
    case 7:bcdec_bc7(compressed,destination,pitch);break;
  }
}

void *PGDecodeBC(int format,uint32_t width,uint32_t height,uint32_t depth,uint32_t rowPitch,uint32_t rowsPerImage,const void *source,size_t sourceSize,size_t *decodedSize){
  if(decodedSize)*decodedSize=0;
  if(format<1||format>7||!width||!height||!depth||!source||!decodedSize)return NULL;
  size_t pixelBytes=format==4?1:format==5?2:format==6?8:4;
  const size_t limit=256*1024*1024;
  // Bound each multiplication before computing the complete output size.
  if(width>limit/pixelBytes)return NULL;
  size_t destinationPitch=(size_t)width*pixelBytes;
  if(height>limit/destinationPitch)return NULL;
  size_t destinationSlice=destinationPitch*height;
  if(depth>limit/destinationSlice)return NULL;
  size_t bytes=destinationSlice*depth;
  uint32_t blocksX=width/4+(width%4!=0),blocksY=height/4+(height%4!=0);
  size_t blockBytes=format==1||format==4?8:16;
  if(!rowPitch)rowPitch=blocksX*blockBytes;
  if(rowPitch<blocksX*blockBytes)return NULL;
  size_t rowEnd=(size_t)(blocksY-1)*rowPitch+blocksX*blockBytes;
  if(rowEnd>sourceSize)return NULL;
  size_t slicePitch=(size_t)rowPitch*(rowsPerImage?rowsPerImage:blocksY);
  // Preserve the original tightly packed depth fallback, without overflow.
  if(depth>1&&slicePitch>(sourceSize-rowEnd)/(depth-1))slicePitch=sourceSize/depth;
  if(depth>1&&slicePitch>(sourceSize-rowEnd)/(depth-1))return NULL;
  uint8_t *decoded=malloc(bytes);if(!decoded)return NULL;
  for(uint32_t z=0;z<depth;z++)for(uint32_t by=0;by<blocksY;by++)for(uint32_t bx=0;bx<blocksX;bx++){
    const uint8_t *compressed=(const uint8_t *)source+z*slicePitch+by*(size_t)rowPitch+bx*blockBytes;
    uint8_t *destination=decoded+z*destinationSlice+(size_t)by*4*destinationPitch+(size_t)bx*4*pixelBytes;
    uint32_t rows=height-by*4;if(rows>4)rows=4;
    uint32_t columns=width-bx*4;if(columns>4)columns=4;
    if(format!=6&&rows==4&&columns==4){
      // bcdec accepts the complete texture's byte pitch. Interior blocks can
      // write directly, avoiding a scratch block and four separate copies.
      decodeBlock(format,compressed,destination,(int)destinationPitch);
    }else{
      _Alignas(16) uint8_t block[128];
      if(format==6){uint16_t rgb[48];bcdec_bc6h_half(compressed,rgb,12,0);uint16_t *rgba=(uint16_t *)block;for(int p=0;p<16;p++){memcpy(rgba+p*4,rgb+p*3,6);rgba[p*4+3]=0x3c00;}}
      else decodeBlock(format,compressed,block,(int)(4*pixelBytes));
      for(uint32_t y=0;y<rows;y++)memcpy(destination+y*destinationPitch,block+y*4*pixelBytes,columns*pixelBytes);
    }
  }
  *decodedSize=bytes;return decoded;
}

static uint16_t packBC1Color(uint32_t r,uint32_t g,uint32_t b){
  return (uint16_t)((r>>3)<<11 | (g>>3)<<6 | (b>>3)<<1 | 1);
}

static void packedBC1Palette(const uint8_t *source,uint16_t colors[4]){
  // Preserve the bundled bcdec__color_block's exact endpoint expansion and
  // interpolation, then apply the renderer's existing A1BGR5 quantization.
  // Pack the FOUR palette entries rather than sixteen intermediate pixels.
  const uint32_t c0=source[0]|((uint32_t)source[1]<<8),c1=source[2]|((uint32_t)source[3]<<8);
  const uint32_t r0=(c0>>11)&31,g0=(c0>>5)&63,b0=c0&31;
  const uint32_t r1=(c1>>11)&31,g1=(c1>>5)&63,b1=c1&31;
  colors[0]=packBC1Color((r0*527+23)>>6,(g0*259+33)>>6,(b0*527+23)>>6);
  colors[1]=packBC1Color((r1*527+23)>>6,(g1*259+33)>>6,(b1*527+23)>>6);
  if(c0>c1){
    colors[2]=packBC1Color(((2*r0+r1)*351+61)>>7,((2*g0+g1)*2763+1039)>>11,((2*b0+b1)*351+61)>>7);
    colors[3]=packBC1Color(((r0+2*r1)*351+61)>>7,((g0+2*g1)*2763+1039)>>11,((b0+2*b1)*351+61)>>7);
  }else{
    colors[2]=packBC1Color(((r0+r1)*1053+125)>>8,((g0+g1)*4145+1019)>>11,((b0+b1)*1053+125)>>8);
    colors[3]=0; // The BC1 transparent selector remains transparent black.
  }
}

void *PGDecodeBC1Packed(uint32_t width,uint32_t height,uint32_t depth,uint32_t rowPitch,uint32_t rowsPerImage,const void *source,size_t sourceSize,size_t *decodedSize){
  if(decodedSize)*decodedSize=0;
  if(!width||!height||!depth||!source||!decodedSize)return NULL;
  // Retain PGDecodeBC(1)'s RGBA-sized validation limit even though this
  // output uses half the memory. Do not silently admit larger uploads.
  const size_t limit=256*1024*1024;
  if(width>limit/4)return NULL;
  size_t rgbaPitch=(size_t)width*4;
  if(height>limit/rgbaPitch)return NULL;
  size_t rgbaSlice=rgbaPitch*height;
  if(depth>limit/rgbaSlice)return NULL;
  size_t destinationPitch=(size_t)width*2,destinationSlice=destinationPitch*height,bytes=destinationSlice*depth;
  uint32_t blocksX=width/4+(width%4!=0),blocksY=height/4+(height%4!=0);
  if(!rowPitch)rowPitch=blocksX*8;
  if(rowPitch<blocksX*8)return NULL;
  size_t rowEnd=(size_t)(blocksY-1)*rowPitch+blocksX*8;
  if(rowEnd>sourceSize)return NULL;
  size_t slicePitch=(size_t)rowPitch*(rowsPerImage?rowsPerImage:blocksY);
  if(depth>1&&slicePitch>(sourceSize-rowEnd)/(depth-1))slicePitch=sourceSize/depth;
  if(depth>1&&slicePitch>(sourceSize-rowEnd)/(depth-1))return NULL;
  uint8_t *decoded=malloc(bytes);if(!decoded)return NULL;
  for(uint32_t z=0;z<depth;z++)for(uint32_t by=0;by<blocksY;by++)for(uint32_t bx=0;bx<blocksX;bx++){
    const uint8_t *compressed=(const uint8_t *)source+z*slicePitch+by*(size_t)rowPitch+bx*8;
    uint16_t colors[4];packedBC1Palette(compressed,colors);
    uint32_t indices=compressed[4]|((uint32_t)compressed[5]<<8)|((uint32_t)compressed[6]<<16)|((uint32_t)compressed[7]<<24);
    uint32_t rows=height-by*4;if(rows>4)rows=4;
    uint32_t columns=width-bx*4;if(columns>4)columns=4;
    for(uint32_t y=0;y<rows;y++){
      uint16_t *destination=(uint16_t *)(decoded+z*destinationSlice+((size_t)by*4+y)*destinationPitch)+(size_t)bx*4;
      uint32_t row=indices>>(y*8);
      for(uint32_t x=0;x<columns;x++,row>>=2)destination[x]=colors[row&3];
    }
  }
  *decodedSize=bytes;return decoded;
}
