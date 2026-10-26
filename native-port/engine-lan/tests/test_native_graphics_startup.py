"""Execute the actual zero-buffer setup block and failed-start drain contract."""
from pathlib import Path
import subprocess
import tempfile
import unittest

APP = Path(__file__).resolve().parents[2] / 'app'


class NativeGraphicsStartup(unittest.TestCase):
    def test_nil_zero_buffer_uses_existing_failure_drain_without_null_write(self):
        source = (APP / 'Source/MetalRenderer/MRRenderer.mm').read_text()
        begin = source.index('\tR->zeroBuffer = [R->device newBufferWithLength:65536')
        end = source.index('\tR->visibility = ', begin)
        actual_allocation = source[begin:end]
        begin = source.index('static void *threadMain(void *) {')
        end = source.index('\n}  // namespace mr', begin)
        actual_thread = source[begin:end]
        fixture = r'''
#import <Foundation/Foundation.h>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <pthread.h>
#include <stdexcept>
static const unsigned MTLResourceStorageModeShared = 0;
@interface TestBuffer : NSObject {
    void *_bytes;
}
@property(readonly) void *contents;
- (instancetype)initWithLength:(NSUInteger)length;
@end
@implementation TestBuffer
- (instancetype)initWithLength:(NSUInteger)length {
    self = [super init];
    if (self) { _bytes = malloc(length); assert(_bytes); memset(_bytes, 0xab, length); }
    return self;
}
- (void *)contents { return _bytes; }
- (void)dealloc { free(_bytes); [super dealloc]; }
@end
@interface TestDevice : NSObject
@property BOOL failAllocation;
- (TestBuffer *)newBufferWithLength:(NSUInteger)length options:(unsigned)options;
@end
@implementation TestDevice
- (TestBuffer *)newBufferWithLength:(NSUInteger)length options:(unsigned)options {
    assert(length == 65536 && options == MTLResourceStorageModeShared);
    return self.failAllocation ? nil : [[TestBuffer alloc] initWithLength:length];
}
@end
struct Renderer { TestDevice *device; TestBuffer *zeroBuffer; uint8_t *mem; uint64_t ring; };
static Renderer *R;
static unsigned allocationErrors = 0, startErrors = 0, notifications = 0, loops = 0;
struct PGGraphicsProgress {
    enum Phase { Setup, SetupFailed };
    Phase current = Setup;
    void phase(Phase phase) { current = phase; }
} graphicsProgress;
static void logf(const char *message) {
    assert(!strcmp(message, "Metal renderer: zero buffer allocation failed.")); allocationErrors++;
}
static void pg_log(const char *message) {
    assert(!strcmp(message, "Metal renderer could not start.")); startErrors++;
}
static void PGGraphicsNotify(uint64_t address) { assert(address == 4); notifications++; }
static void fixtureSleep(unsigned duration) {
    assert(duration == 5000);
    throw std::runtime_error("observed original failed-start drain");
}
#define usleep fixtureSleep
static bool setup() {
''' + actual_allocation + r'''
    return true;
}
static void loop() { loops++; }
''' + actual_thread + r'''
int main() { @autoreleasepool {
    alignas(8) std::atomic<uint32_t> header[16]{};
    TestDevice *device = [TestDevice new];
    device.failAllocation = YES;
    Renderer renderer{device, nil, (uint8_t *)header, 0}; R = &renderer;
    header[0].store(96); header[1].store(64);
    try { threadMain(nullptr); assert(false); } catch (const std::runtime_error &) {}
    assert(allocationErrors == 1 && startErrors == 1 && notifications == 1 && loops == 0);
    assert(graphicsProgress.current == PGGraphicsProgress::SetupFailed);
    assert(header[2].load() == 2 && header[1].load() == 96 && header[0].load() == 96);
    assert(header[3].load() == 0 && !renderer.zeroBuffer);
    // Healthy setup still initializes the complete shared zero buffer and
    // enters the original renderer loop, without touching the ring header.
    device.failAllocation = NO;
    for (auto &word : header) word.store(0);
    threadMain(nullptr);
    assert(renderer.zeroBuffer && loops == 1 && allocationErrors == 1 && startErrors == 1);
    assert(header[2].load() == 0 && notifications == 1);
    auto *bytes = (unsigned char *)renderer.zeroBuffer.contents;
    for (unsigned i = 0; i < 65536; i++) assert(bytes[i] == 0);
    [renderer.zeroBuffer release]; [device release];
    puts("NATIVE_GRAPHICS_STARTUP_PASS");
} }
'''
        with tempfile.TemporaryDirectory(prefix='zgta-native-graphics-startup-') as folder:
            directory = Path(folder)
            path = directory / 'fixture.mm'
            path.write_text(fixture)
            binary = directory / 'fixture'
            compiled = subprocess.run([
                '/usr/bin/clang++', '-std=c++17', '-fno-objc-arc',
                '-Wall', '-Wextra', '-Werror', '-framework', 'Foundation',
                str(path), '-o', str(binary),
            ], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('NATIVE_GRAPHICS_STARTUP_PASS', result.stdout)


if __name__ == '__main__':
    unittest.main()
