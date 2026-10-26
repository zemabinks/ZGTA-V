#pragma once
#include <errno.h>
#include <stdint.h>
#include <unistd.h>

// Interrupted local/mod reads must resume at the last completed byte. A real
// I/O error remains an error, even after a successful partial read.
#ifndef PG_ASSET_PREAD
#define PG_ASSET_PREAD pread
#endif
static inline int64_t pg_asset_read_at(int descriptor, uint8_t *destination, uint32_t length, uint64_t offset) {
  if (!length) return 0;
  if (!destination || offset > INT64_MAX || length > (uint64_t)INT64_MAX - offset) { errno = EINVAL; return -1; }
  uint32_t done = 0;
  while (done < length) {
    ssize_t count = PG_ASSET_PREAD(descriptor, destination + done, length - done, (off_t)(offset + done));
    if (count < 0 && errno == EINTR) continue;
    if (count < 0) return -1;
    if (!count) break;
    if ((uint64_t)count > length - done) { errno = EIO; return -1; }
    done += (uint32_t)count;
  }
  return done;
}
