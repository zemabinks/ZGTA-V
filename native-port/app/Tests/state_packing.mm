#import <Foundation/Foundation.h>
#import <JavaScriptCore/JavaScriptCore.h>
#include <cassert>
#include <cstdio>
static NSString *exercise(BOOL optimized,NSString *source){
 JSContext *context=[[JSContext alloc] init];context[@"nativeFixedStatePacking"]=@(optimized);
 [context evaluateScript:@"var batches=[];var self=globalThis;var nativeGPUCall=function(){};var nativeGPUBatch=function(a,o){batches.push([Array.from(a),o.map(x=>x.label)]);};var NativeGPU=function(){};var normalizeGPUVector=function(v){return v;};"];
 [context evaluateScript:source];assert(!context.exception);
 [context evaluateScript:[NSString stringWithUTF8String:R"JS(
 const fixturePass={label:'pass0'},fixtureOtherPass={label:'pass1'},fixturePlan={label:'plan'};
 for(let i=0;i<10000;i++){
  nativeDrawState(25);
  nativeDrawState(19,i+1,57,i*4);
  nativeDrawState(20,1,0.25,i%13,960,540,0,1);
  nativeDrawState(21,1,i%7,0,960,540);
  nativeDrawState(22,0.1,0.2,0.3,0.4);
  nativeDrawState(23,i%256);
  nativeDrawState(24,i%2);
  nativeDrawVertices(0,2,[{buf:7,stride:16,offset:i*16},{buf:8,stride:4,offset:0}]);
  reservePreparedDraw();nativeDrawTransaction(i%7?fixturePass:fixtureOtherPass,i%65536);
  if(i%17===0){reservePreparedDraw();nativeWarmTransaction(fixturePass,i%65536);}
  if(i%31===0)nativeDrawPacket(fixturePass,fixturePlan,1,36,1,0,-4,0,i,960,540);
 }
 flushDrawBatch();var packedState=JSON.stringify(batches);
 )JS"]];
 assert(!context.exception);return context[@"packedState"].toString;
}
int main(){@autoreleasepool {
 NSString *source=[NSString stringWithContentsOfFile:@"Resources/gpu-batch.js" encoding:NSUTF8StringEncoding error:nil];assert(source);
 NSString *reference=exercise(NO,source),*optimized=exercise(YES,source);assert([reference isEqualToString:optimized]);
 puts("PASS: production state packing matches reference for 70,000 state packets, vertex state, prepared draws, object indices, and batch rollover.");
}return 0;}
