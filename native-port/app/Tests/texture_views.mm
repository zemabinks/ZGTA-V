#import <JavaScriptCore/JavaScriptCore.h>
#include "../Source/NativeTextureView.h"
#include <assert.h>
#include <stdio.h>
static void check(JSContext *context,NSString *expression,size_t offset,size_t length){
 JSValue *value=[context evaluateScript:expression];PGTextureView view;
 assert(PGGetTextureView(context.JSGlobalContextRef,value.JSValueRef,&view));assert(view.length==length);
 for(size_t i=0;i<length;i++)assert(view.bytes[i]==(uint8_t)(offset+i));
}
int main(){@autoreleasepool {
 JSContext *context=[[JSContext alloc] init];[context evaluateScript:@"var backing=new ArrayBuffer(64),all=new Uint8Array(backing);for(var i=0;i<64;i++)all[i]=i;"];
 check(context,@"backing",0,64);check(context,@"new Uint8Array(backing,3,19)",3,19);
 check(context,@"new Uint16Array(backing,4,8)",4,16);check(context,@"new Uint32Array(backing,12,3)",12,12);
 check(context,@"new DataView(backing,9,27)",9,27);check(context,@"new Uint8Array(backing,64,0)",64,0);
 for(NSString *expression in @[@"null",@"undefined",@"42",@"{}",@"[]",@"({buffer:backing,byteOffset:-1,byteLength:4})",@"({buffer:backing,byteOffset:63,byteLength:2})",@"({buffer:backing,byteOffset:0.5,byteLength:4})",@"({buffer:backing,byteOffset:0,byteLength:NaN})",@"({get buffer(){throw Error('bad view')}})"]){
  JSValue *value=[context evaluateScript:expression];PGTextureView view;assert(!PGGetTextureView(context.JSGlobalContextRef,value.JSValueRef,&view));
 }
 puts("PASS: synchronous texture views preserve byte offsets/lengths for ArrayBuffer, typed arrays and DataView; malformed views rejected.");
 }return 0;
}
