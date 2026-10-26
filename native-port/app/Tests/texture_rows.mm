#import <Foundation/Foundation.h>
#import <JavaScriptCore/JavaScriptCore.h>
#include "../Source/NativeTextureRows.h"
#include <assert.h>
#include <stdio.h>
#include <vector>
static std::vector<uint8_t> engine;
static size_t calls;
static JSValueRef store(JSContextRef c,JSObjectRef,JSObjectRef,size_t n,const JSValueRef v[],JSValueRef *error){
 calls++;if(!PGStoreTextureRows(c,n,v,engine.data(),engine.size(),error)){
  JSStringRef message=JSStringCreateWithUTF8CString("Invalid compressed texture upload range");JSValueRef text=JSValueMakeString(c,message);JSStringRelease(message);*error=JSObjectMakeError(c,1,&text,nullptr);
 }return JSValueMakeUndefined(c);
}
static void evaluate(JSContext *context,NSString *script){[context evaluateScript:script];if(context.exception){fprintf(stderr,"%s\n",context.exception.toString.UTF8String);abort();}}
int main(){@autoreleasepool {
 uint8_t src[256],dst[256],expected[256];for(size_t i=0;i<256;i++)src[i]=i;
 for(size_t rows=1;rows<=9;rows++)for(size_t pitch=7;pitch<18;pitch++){
  memset(dst,0xaa,sizeof dst);memcpy(expected,dst,sizeof dst);
  for(size_t row=0;row<rows;row++)memcpy(expected+5+row*pitch,src+3+row*(pitch+1),7);
  assert(PGCopyTextureRows(dst,sizeof dst,5,pitch,src,sizeof src,3,pitch+1,7,rows)&&!memcmp(dst,expected,sizeof dst));
 }
 memset(dst,0xab,sizeof dst);memcpy(expected,dst,sizeof dst);
 assert(!PGCopyTextureRows(dst,256,250,9,src,256,0,9,8,2)&&!memcmp(dst,expected,256));
 assert(!PGCopyTextureRows(dst,256,0,8,src,256,SIZE_MAX,8,8,1));
 assert(!PGCopyTextureRows(dst,256,0,SIZE_MAX,src,256,0,8,8,SIZE_MAX));
 assert(PGCopyTextureRows(NULL,0,0,0,NULL,0,0,0,0,0));
 // TypedArray.set's row-by-row alias behavior is retained.
 memcpy(dst,src,256);memcpy(expected,src,256);for(size_t i=0;i<4;i++)memmove(expected+8+i*8,expected+i*8,8);
 assert(PGCopyTextureRows(dst,256,8,8,dst,256,0,8,8,4)&&!memcmp(dst,expected,256));
 engine.resize(4*1024*1024);for(size_t i=0;i<engine.size();i++)engine[i]=(uint8_t)(i*37+11);
 JSContext *context=[[JSContext alloc] init];JSContextRef c=context.JSGlobalContextRef;
 JSObjectRef buffer=JSObjectMakeArrayBufferWithBytesNoCopy(c,engine.data(),engine.size(),[](void *,void *){},nullptr,nullptr);
 context[@"memBuffer"]=[JSValue valueWithJSValueRef:buffer inContext:context];
 JSStringRef key=JSStringCreateWithUTF8CString("nativeStoreTextureRows");JSObjectSetProperty(c,JSContextGetGlobalObject(c),key,JSObjectMakeFunctionWithCallback(c,key,store),kJSPropertyAttributeNone,nullptr);JSStringRelease(key);
 NSString *source=[NSString stringWithContentsOfFile:@"Resources/wgpu_worker.js" encoding:NSUTF8StringEncoding error:nil];
 NSRange begin=[source rangeOfString:@"function storeCompressedUpload("],end=[source rangeOfString:@"\nfunction createShader(" options:0 range:NSMakeRange(begin.location,source.length-begin.location)];
 NSString *function=[source substringWithRange:NSMakeRange(begin.location,end.location-begin.location)];
 evaluate(context,@"function mipSize(o,m){return {w:Math.max(1,o.desc.size.width>>m),h:Math.max(1,o.desc.size.height>>m)}};function blockInfo(f){var k=+f[2];return {bytes:k===1||k===4?8:16}};function assert(v){if(!v)throw Error('check failed')};var nativeTextureShadowRows=false;");
 evaluate(context,function);
 evaluate(context,@"for(var f=1;f<=7;f++)for(var mip=0;mip<3;mip++)for(var depth=1;depth<=3;depth++){var format='bc'+f+'-unorm',block=blockInfo(format).bytes;var a={nativeBC:format,desc:{dimension:depth===3?'3d':'2d',size:{width:64,height:64}}},b={nativeBC:format,desc:a.desc};var data=new Uint8Array(memBuffer,13,8192),pitch=8*block+16,rows=5;nativeTextureShadowRows=false;storeCompressedUpload(a,mip,2,4,4,1,7,9,depth,pitch,rows,data);nativeTextureShadowRows=true;storeCompressedUpload(b,mip,2,4,4,1,7,9,depth,pitch,rows,data);assert(a.compressedShadow.size===b.compressedShadow.size);for(var entry of a.compressedShadow){var old=entry[1],fresh=b.compressedShadow.get(entry[0]);assert(old.length===fresh.length);for(var i=0;i<old.length;i++)assert(old[i]===fresh[i]);}}");
 evaluate(context,@"var threw=false;try{nativeStoreTextureRows(new Uint8Array(16),0,64,60,16,0,16,16,2)}catch(e){threw=true}assert(threw);threw=false;try{nativeStoreTextureRows(new Uint8Array(16),0,64,0,16,15,16,2,1)}catch(e){threw=true}assert(threw);");
 assert(calls>=126);
 puts("PASS: native texture rows match the production JavaScript shadows for BC1–BC7, partial boxes, padded rows, mips, array slices and 3D layers; complete bounds, sparse writes and per-row overlap behavior checked.");
 if(getenv("PG_TEXTURE_ROWS_MICROBENCH")){
  evaluate(context,@"var object={nativeBC:'bc1-rgba-unorm',desc:{dimension:'2d',size:{width:1024,height:1024}}},data=new Uint8Array(memBuffer,0,524288);function benchRows(native){nativeTextureShadowRows=native;var start=Date.now();for(var i=0;i<200;i++)storeCompressedUpload(object,0,0,0,0,0,1024,1024,1,2048,256,data);return (Date.now()-start)/200}");
  double reference=[context evaluateScript:@"benchRows(false)"].toDouble,native=[context evaluateScript:@"benchRows(true)"].toDouble;
  printf("JIT disabled 1024x1024 shadow copy: JavaScript %.3f ms, native %.3f ms, %.2fx speedup\n",reference,native,reference/native);
 }
 }return 0;
}
