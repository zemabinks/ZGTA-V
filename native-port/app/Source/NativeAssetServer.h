#pragma once
// The server that holds your own copy of the game files (set in the app).
#ifdef __OBJC__
#import <Foundation/Foundation.h>
#ifdef __cplusplus
extern "C" {
#endif
NSString *PGAssetServer(void);
#ifdef __cplusplus
}
#endif
#endif
