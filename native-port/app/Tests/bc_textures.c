#include "../Source/BCTextureDecoder.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <math.h>
static uint32_t state=0x61735acb;
static uint32_t random32(void){state^=state<<13;state^=state>>17;state^=state<<5;return state;}
static size_t countCases;
static void check(int format,uint32_t width,uint32_t height,uint32_t depth,int padded,int fallback){
 size_t blockBytes=format==1||format==4?8:16,bx=(width+3)/4,by=(height+3)/4;
 uint32_t pitch=(uint32_t)(bx*blockBytes+(padded?32:0)),rows=(uint32_t)(by+(padded?2:0));
 size_t slice=(size_t)pitch*(fallback?by:rows),size=slice*depth;
 uint8_t *allocation=malloc(size+5),*source=allocation+3;
 for(size_t i=0;i<size;i++)source[i]=(uint8_t)random32();
 size_t oldSize=0,newSize=0;
 void *old=PGDecodeBCReference(format,width,height,depth,pitch,rows,source,size,&oldSize);
 void *fresh=PGDecodeBC(format,width,height,depth,pitch,rows,source,size,&newSize);
 assert(old&&fresh&&oldSize==newSize&&!memcmp(old,fresh,newSize));free(old);free(fresh);
 size_t last=(size_t)(depth-1)*slice+(by-1)*pitch+bx*blockBytes;
 // The exact final block is accepted; removing its final byte is rejected.
 old=PGDecodeBCReference(format,width,height,depth,pitch,0,source,last-1,&oldSize);
 fresh=PGDecodeBC(format,width,height,depth,pitch,0,source,last-1,&newSize);
 assert((old==NULL)==(fresh==NULL));if(old){assert(oldSize==newSize&&!memcmp(old,fresh,newSize));}
 free(old);free(fresh);free(allocation);countCases++;
}
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static double measure(int format,uint32_t dim,int reference,const void *source,size_t size){
 double results[7];volatile uint8_t checkSum=0;
 for(int trial=0;trial<7;trial++){
  double start=now();for(int i=0;i<12;i++){size_t outSize=0;uint8_t *out=(reference?PGDecodeBCReference:PGDecodeBC)(format,dim,dim,1,0,0,source,size,&outSize);assert(out);checkSum^=out[outSize/2];free(out);}
  results[trial]=(now()-start)*1000/12;
 }
 for(int i=0;i<7;i++)for(int j=i+1;j<7;j++)if(results[j]<results[i]){double v=results[i];results[i]=results[j];results[j]=v;}
 return results[3]+checkSum*0.0;
}
int main(void){
 uint32_t dims[]={1,2,3,4,5,7,8,15,16,17,31,32,33,63,64,65};
 for(int format=1;format<=7;format++)for(size_t i=0;i<sizeof(dims)/sizeof(dims[0]);i++)for(int padded=0;padded<2;padded++)for(uint32_t depth=1;depth<=3;depth++)check(format,dims[i],dims[(i*7+3)%16],depth,padded,0);
 for(int format=1;format<=7;format++)for(int i=0;i<100;i++)check(format,1+random32()%80,1+random32()%80,1+random32()%3,i%2,i%3==0);
 uint8_t block[16]={0};size_t size=123;
 assert(!PGDecodeBC(0,4,4,1,0,0,block,16,&size)&&size==0);
 assert(!PGDecodeBC(1,0,4,1,0,0,block,16,&size));
 assert(!PGDecodeBC(1,4,4,1,1,0,block,16,&size));
 assert(!PGDecodeBC(1,UINT32_MAX,UINT32_MAX,UINT32_MAX,0,0,block,16,&size));
 assert(!PGDecodeBC(1,4,4,1,0,0,NULL,16,&size));
 assert(!PGDecodeBC(1,4,4,1,0,0,block,16,NULL));
 printf("PASS: %zu BC1–BC7 equivalence cases, clipped edges, depth, row padding, tight-depth fallback, truncated data and invalid bounds.\n",countCases);
 if(getenv("PG_BC_MICROBENCH")){
  for(int f=1;f<=7;f++)for(uint32_t dim=256;dim<=1024;dim*=2){
   size_t sourceSize=(size_t)dim*dim*(f==1||f==4?8:16)/16;uint8_t *source=malloc(sourceSize);
   for(size_t i=0;i<sourceSize;i++)source[i]=random32();
   double old=measure(f,dim,1,source,sourceSize),fresh=measure(f,dim,0,source,sourceSize);
   printf("BC%d %ux%u: original %.3f ms, direct %.3f ms, speedup %.3fx\n",f,dim,dim,old,fresh,old/fresh);free(source);
  }
 }
 return 0;
}
