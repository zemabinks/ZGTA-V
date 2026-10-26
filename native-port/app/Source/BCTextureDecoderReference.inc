// Original block-copy decoder retained for controlled comparisons.
void *PGDecodeBCReference(int format,uint32_t width,uint32_t height,uint32_t depth,uint32_t rowPitch,uint32_t rowsPerImage,const void *source,size_t sourceSize,size_t *decodedSize){
  if(format<1||format>7||!width||!height||!depth)return NULL;
  size_t pixelBytes=format==4?1:format==5?2:format==6?8:4;
  uint64_t bytes=(uint64_t)width*height*depth*pixelBytes;if(bytes>256*1024*1024)return NULL;
  uint8_t *decoded=malloc(bytes);if(!decoded)return NULL;
  uint32_t blocksX=(width+3)/4,blocksY=(height+3)/4;size_t blockBytes=format==1||format==4?8:16;
  if(!rowPitch)rowPitch=blocksX*blockBytes;if(rowPitch<blocksX*blockBytes){free(decoded);return NULL;}
  size_t slicePitch=(size_t)rowPitch*(rowsPerImage?rowsPerImage:blocksY);
  if(depth>1&&slicePitch*(depth-1)+(size_t)(blocksY-1)*rowPitch+blocksX*blockBytes>sourceSize)slicePitch=sourceSize/depth;
  for(uint32_t z=0;z<depth;z++)for(uint32_t by=0;by<blocksY;by++)for(uint32_t bx=0;bx<blocksX;bx++){
    size_t offset=z*slicePitch+by*(size_t)rowPitch+bx*blockBytes;
    if(offset>sourceSize||blockBytes>sourceSize-offset){free(decoded);return NULL;}
    const uint8_t *compressed=(const uint8_t *)source+offset;
    _Alignas(16) uint8_t block[128];
    switch(format){case 1:bcdec_bc1(compressed,block,16);break;case 2:bcdec_bc2(compressed,block,16);break;case 3:bcdec_bc3(compressed,block,16);break;case 4:bcdec_bc4(compressed,block,4);break;case 5:bcdec_bc5(compressed,block,8);break;case 6:{uint16_t rgb[48];bcdec_bc6h_half(compressed,rgb,12,0);uint16_t *rgba=(uint16_t *)block;for(int p=0;p<16;p++){memcpy(rgba+p*4,rgb+p*3,6);rgba[p*4+3]=0x3c00;}break;}case 7:bcdec_bc7(compressed,block,16);break;}
    for(uint32_t y=0;y<4&&by*4+y<height;y++){size_t n=width-bx*4;if(n>4)n=4;memcpy(decoded+(((size_t)z*height+by*4+y)*width+bx*4)*pixelBytes,block+y*4*pixelBytes,n*pixelBytes);}
  }
  *decodedSize=bytes;return decoded;
}
