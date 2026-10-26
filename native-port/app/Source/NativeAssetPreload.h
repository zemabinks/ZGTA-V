#pragma once
#include <stdint.h>
#include <stdbool.h>

// "Download all game files": fills the same packed 4 KB block cache that
// streaming reads (Documents/AssetCache-<version>/Packed-v1), through the
// engine's own locked fill path. Once every block is present, reads never
// touch the network. Progress lives in the cache's presence maps, so a run
// stopped by pause, relaunch or a crash resumes where it left off.

// Opens the asset cache exactly as the engine will (idempotent; safe before
// or after PGStartEngine with the same arguments).
void PGAssetCachePrepare(const char *manifestPath, const char *filesRoot);
// False on the simulator unless --stream-assets is set: there the game reads
// the Mac's mirror directly and never looks at the cache.
bool PGAssetPreloadSupported(void);
// filter: NULL for every file, otherwise comma-separated path prefixes
// (debug subsets). Reads only the small presence maps.
void PGAssetPreloadMeasure(const char *filter, uint64_t *totalBytes, uint64_t *cachedBytes, uint32_t *fileCount);

typedef enum {
  PGAssetPreloadErrorNone = 0,
  PGAssetPreloadErrorNetwork = 1,  // repeated failed range requests
  PGAssetPreloadErrorStorage = 2,  // a cache write did not persist (disk full)
} PGAssetPreloadError;

typedef struct {
  bool running;
  uint64_t totalBytes;     // planned bytes (filtered manifest)
  uint64_t cachedBytes;    // on device: measured at start plus bytes stored since
  uint64_t downloadedBytes;// network bytes this run
  int32_t error;           // PGAssetPreloadError of the last run
} PGAssetPreloadStatus;

// Starts background workers (no-op if already running). lanes: 1...6.
bool PGAssetPreloadStart(const char *filter, unsigned lanes);
// Lanes finish their current 1 MB span and exit; returns immediately.
void PGAssetPreloadStop(void);
// Fewer lanes while the game runs so demand reads keep the bandwidth.
void PGAssetPreloadSetLanes(unsigned lanes);
PGAssetPreloadStatus PGAssetPreloadGetStatus(void);
// Deletes this version's cache directory and recreates it empty. Only when
// no preload is running and the engine has not started.
bool PGAssetCacheRemoveAll(uint64_t *freedBytes);
