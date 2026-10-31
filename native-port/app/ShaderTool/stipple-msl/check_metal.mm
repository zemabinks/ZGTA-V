// Runtime compiler check on the current Mac. This is not an iPhone check.
// Usage: check-metal <sources.jsonl> [maximum]
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <fstream>
#include <iostream>

int main(int argc, char **argv) {
    @autoreleasepool {
        if (argc < 2 || argc > 3) return 2;
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) { std::cerr << "No Metal device available\n"; return 3; }
        std::cout << "Mac Metal device: " << device.name.UTF8String << "\n";
        std::ifstream input(argv[1]);
        std::string line; size_t count = 0, failed = 0;
        size_t maximum = argc == 3 ? strtoull(argv[2], nullptr, 10) : SIZE_MAX;
        while (count < maximum && std::getline(input, line)) {
            @autoreleasepool {
                NSData *data = [NSData dataWithBytes:line.data() length:line.size()];
                NSDictionary *record = [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
                if (!record) return 4;
                NSError *error = nil;
                MTLCompileOptions *options = [MTLCompileOptions new];
                options.languageVersion = MTLLanguageVersion2_4;
                options.fastMathEnabled = YES;
                id<MTLLibrary> library = [device newLibraryWithSource:record[@"source"] options:options error:&error];
                if (!library) {
                    failed++;
                    std::cerr << [record[@"h"] UTF8String] << ": " << error.localizedDescription.UTF8String << "\n";
                } else {
                    for (uint32_t level : {1u, 7u, 15u, 16u, 17u, 20u, 22u, 25u, 27u, 30u, 31u}) {
                        MTLFunctionConstantValues *values = [MTLFunctionConstantValues new];
                        [values setConstantValue:&level type:MTLDataTypeUInt atIndex:0];
                        id<MTLFunction> function = [library newFunctionWithName:[NSString stringWithFormat:@"s_%@_stipple", record[@"h"]] constantValues:values error:&error];
                        if (!function) {failed++; std::cerr << [record[@"h"] UTF8String] << " specialization: " << error.localizedDescription.UTF8String << "\n";}
                    }
                }
                count++;
                if (count % 100 == 0) std::cout << "checked " << count << ", failed " << failed << "\n";
            }
        }
        std::cout << "Mac MSL compile/specialization: " << count << " programs, " << failed << " failures\n";
        return failed ? 1 : 0;
    }
}
