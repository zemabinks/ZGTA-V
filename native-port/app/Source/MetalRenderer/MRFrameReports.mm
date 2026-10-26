// Optional frame reports (launch argument --frame-reports): bounded performance aggregates every 15 seconds of world
// rendering, sent as a GET to your own game-file server (its access log then holds them). Off by default. No asset
// contents, input, position or persistent device IDs.
#include "MRFrameReports.h"
#include "NativeFrameMetrics.h"
#include "NativeAssetServer.h"
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <UIKit/UIKit.h>
#include <TargetConditionals.h>
#include <atomic>
#include <mach/mach.h>
#include <os/proc.h>

extern "C" void pg_log(const char *);

namespace mr {
static bool enabled;
static PGFrameMetricsWindow window;
static double windowStart;
static uint64_t sequence;
static std::atomic<bool> inFlight{false}, resetPending{false}, applicationActive{true};
static NSURLSession *session;
static NSString *runId, *build;
static id<MTLDevice> device;

static NSString *number(double value) { return [NSString stringWithFormat:@"%.3f", value]; }

static void enqueue(PGFrameMetricsSnapshot stats) {
	bool expected = false;
	if (!inFlight.compare_exchange_strong(expected, true)) return;
	uint64_t seq = ++sequence;
	dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{ @autoreleasepool {
		NSURLComponents *url = [NSURLComponents componentsWithString:[PGAssetServer() stringByAppendingString:@"/install/native-performance.json"]];
		double frames = (double)stats.frames;
		task_vm_info_data_t memory = {};
		mach_msg_type_number_t count = TASK_VM_INFO_COUNT;
		bool memoryKnown = task_info(mach_task_self(), TASK_VM_INFO, (task_info_t)&memory, &count) == KERN_SUCCESS;
		NSDictionary<NSString *, NSString *> *values = @{
			@"schema": @"1", @"renderer": @"metal", @"qos": @"0", @"build": build, @"run": runId, @"seq": [NSString stringWithFormat:@"%llu", seq],
			@"frames": [NSString stringWithFormat:@"%llu", stats.frames], @"fps": number(stats.fps()), @"p95": number(stats.p95Ms), @"p99": number(stats.p99Ms), @"max": number(stats.maxMs),
			@"over33": [NSString stringWithFormat:@"%llu", stats.over33], @"over50": [NSString stringWithFormat:@"%llu", stats.over50],
			@"over100": [NSString stringWithFormat:@"%llu", stats.over100], @"over250": [NSString stringWithFormat:@"%llu", stats.over250],
			@"draws": number(stats.draws / frames), @"idle": number(stats.work.idle / frames), @"pipe": number(stats.work.pipeline / frames),
			@"modules": number(0), @"upload": number(stats.work.uploads / frames), @"uploadMB": number(stats.work.uploadBytes / 1048576.0),
			@"wait": number(stats.work.gpuWait / frames), @"submit": number(stats.work.submit / frames),
			@"worstIdle": number(stats.worstWork.idle), @"worstPipe": number(stats.worstWork.pipeline), @"worstModules": number(0),
			@"worstUpload": number(stats.worstWork.uploads), @"worstWait": number(stats.worstWork.gpuWait), @"worstSubmit": number(stats.worstWork.submit),
			@"memoryClamps": number(0), @"metalMB": number(device ? device.currentAllocatedSize / 1048576.0 : 0),
			@"footprintMB": number(memoryKnown ? memory.phys_footprint / 1048576.0 : 0),
#if TARGET_OS_SIMULATOR
			@"headroomMB": number(0),
#else
			@"headroomMB": number(os_proc_available_memory() / 1048576.0),
#endif
			@"thermal": [NSString stringWithFormat:@"%ld", (long)NSProcessInfo.processInfo.thermalState],
		};
		NSMutableArray<NSURLQueryItem *> *items = [NSMutableArray arrayWithCapacity:values.count];
		for (NSString *key in [[values allKeys] sortedArrayUsingSelector:@selector(compare:)]) [items addObject:[NSURLQueryItem queryItemWithName:key value:values[key]]];
		url.queryItems = items;
		NSMutableURLRequest *request = [NSMutableURLRequest requestWithURL:url.URL cachePolicy:NSURLRequestReloadIgnoringLocalCacheData timeoutInterval:3];
		NSURLSessionDataTask *task = [session dataTaskWithRequest:request completionHandler:^(NSData *, NSURLResponse *, NSError *) { inFlight.store(false); }];
		task.priority = NSURLSessionTaskPriorityLow;
		[task resume];
	}});
}

void frameReportsInstall(id<MTLDevice> metalDevice) {
	device = metalDevice;
	enabled = [NSProcessInfo.processInfo.arguments containsObject:@"--frame-reports"];
	if (!enabled) { pg_log("Frame reports disabled."); return; }
	build = [NSBundle.mainBundle objectForInfoDictionaryKey:@"CFBundleVersion"] ?: @"probe";
	runId = NSUUID.UUID.UUIDString;
	NSURLSessionConfiguration *configuration = [NSURLSessionConfiguration ephemeralSessionConfiguration];
	configuration.URLCache = nil; configuration.HTTPCookieStorage = nil; configuration.HTTPMaximumConnectionsPerHost = 1;
	configuration.timeoutIntervalForRequest = 3; configuration.timeoutIntervalForResource = 5;
	session = [NSURLSession sessionWithConfiguration:configuration];
	dispatch_async(dispatch_get_main_queue(), ^{
		[NSNotificationCenter.defaultCenter addObserverForName:UIApplicationWillResignActiveNotification object:nil queue:nil usingBlock:^(NSNotification *) { applicationActive.store(false); resetPending.store(true); }];
		[NSNotificationCenter.defaultCenter addObserverForName:UIApplicationDidBecomeActiveNotification object:nil queue:nil usingBlock:^(NSNotification *) { resetPending.store(true); applicationActive.store(true); }];
	});
	pg_log("Frame reports enabled: bounded aggregates every 15 seconds of active world rendering.");
}

void frameReportsRecord(double timeMs, double frameMs, uint64_t draws, bool world, const FrameWork &w) {
	if (!enabled) return;
	if (resetPending.exchange(false)) { window.reset(); windowStart = 0; return; }
	if (!applicationActive.load() || !world || draws < 100) return;
	PGFrameWork work{w.idle, w.pipeline, 0, w.uploads, w.uploadBytes, w.gpuWait, w.submit};
	if (!window.record(frameMs, draws, work)) return;
	if (!windowStart) windowStart = timeMs;
	if (timeMs - windowStart >= 15000) { enqueue(window.snapshot()); window.reset(); windowStart = timeMs; }
}
}  // namespace mr
