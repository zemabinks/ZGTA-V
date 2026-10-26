#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <string.h>
#include <sys/types.h>
static unsigned calls, mode;
static ssize_t injected_read(int fd, void *output, size_t length, off_t offset) {
  assert(fd == 42); calls++;
  if (calls == 1) { errno = EINTR; return -1; }
  if (mode == 1 && calls == 3) { errno = EIO; return -1; }
  if (offset >= 10) return 0;
  size_t n = length > 2 ? 2 : length;
  if (n > (size_t)(10 - offset)) n = (size_t)(10 - offset);
  const char *digits = "0123456789";
  memcpy(output, &digits[offset], n); return (ssize_t)n;
}
#define PG_ASSET_PREAD injected_read
#include "NativeAssetRead.h"
int main(void) {
  uint8_t data[12]; memset(data, 0xaa, sizeof data);
  assert(pg_asset_read_at(42,data,6,3)==6);
  assert(!memcmp(data,"345678",6));assert(data[6]==0xaa);
  calls=0;assert(pg_asset_read_at(42,data,6,8)==2);assert(!memcmp(data,"89",2));
  calls=0;mode=1;assert(pg_asset_read_at(42,data,6,0)==-1);assert(errno==EIO);
  calls=0;assert(pg_asset_read_at(42,data,6,INT64_MAX)==-1);assert(errno==EINVAL);assert(calls==0);
  assert(pg_asset_read_at(42,0,6,0)==-1);assert(calls==0);
  assert(pg_asset_read_at(42,0,0,0)==0);assert(calls==0);
  return 0;
}
