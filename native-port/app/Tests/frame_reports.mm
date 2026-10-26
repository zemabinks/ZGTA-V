#import <Foundation/Foundation.h>
#import <JavaScriptCore/JavaScriptCore.h>
#include <TargetConditionals.h>
#include <atomic>
#include <cassert>
#include <cstdio>
static void pg_log(const char *text){puts(text);}
#include "../Source/NativeFrameReports.inc"
static void frame(JSContext *context,double time,double interval,uint32_t draws,bool world=true){
 JSContextRef c=context.JSGlobalContextRef;JSValueRef values[]={JSValueMakeNumber(c,time),JSValueMakeNumber(c,interval),JSValueMakeNumber(c,draws),JSValueMakeBoolean(c,world),JSValueMakeNumber(c,20),JSValueMakeNumber(c,1),JSValueMakeNumber(c,.5),JSValueMakeNumber(c,2),JSValueMakeNumber(c,65536),JSValueMakeNumber(c,0),JSValueMakeNumber(c,1)};
 NativeFrameReports::record(c,11,values);
}
int main(){@autoreleasepool {
 NativeFrameReports::gpuMemorySample=[]()->uint64_t{return 128ull*1048576;};NativeFrameReports::memoryClampSample=[]()->uint64_t{return 42;};
 JSContext *context=[[JSContext alloc] init];NativeFrameReports::install(context);assert(NativeFrameReports::enabled);
 frame(context,100,33.333,500);assert(NativeFrameReports::window.snapshot().frames==1);
 frame(context,200,33.333,500,false);frame(context,300,33.333,99);assert(NativeFrameReports::window.snapshot().frames==1);
 NativeFrameReports::applicationActive.store(false);frame(context,400,100,500);assert(NativeFrameReports::window.snapshot().frames==1);
 NativeFrameReports::applicationActive.store(true);NativeFrameReports::resetPending.store(true);frame(context,1000,5000,500);assert(NativeFrameReports::window.snapshot().frames==0);
 // A slow world frame while active is retained, not mistaken for background.
 frame(context,1100,100,500);assert(NativeFrameReports::window.snapshot().frames==1&&NativeFrameReports::window.snapshot().maxMs==100);
 NativeFrameReports::window.reset();NativeFrameReports::windowStart=0;NativeFrameReports::inFlight.store(true);
 frame(context,2000,33.333,500);frame(context,18000,33.333,500);assert(NativeFrameReports::sequence==0&&NativeFrameReports::window.snapshot().frames==0);NativeFrameReports::inFlight.store(false);
 NativeFrameReports::windowStart=0;NativeFrameReports::window.reset();frame(context,20000,33.333,500);frame(context,36000,50,500);assert(NativeFrameReports::sequence==1);
 NSDate *deadline=[NSDate dateWithTimeIntervalSinceNow:8];while(NativeFrameReports::inFlight.load()&&deadline.timeIntervalSinceNow>0)[NSThread sleepForTimeInterval:.02];
 assert(!NativeFrameReports::inFlight.load()&&NativeFrameReports::completedRequests.load()==1&&NativeFrameReports::failedRequests.load()==0);
 puts("PASS: active-world filter, background exclusion, resume interval reset, long active frames, one request in flight, rate window, async private HTTPS report received with HTTP 200.");
 [NativeFrameReports::session invalidateAndCancel];
 }return 0;
}
