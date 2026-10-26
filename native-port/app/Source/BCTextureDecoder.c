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
