#include "NativeControllerLook.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

static int32_t integrate(float stick, unsigned hz) {
  PGLookRemainder remainder = {0};
  int32_t result = 0;
  for (unsigned i = 0; i < hz * 10; ++i) {
    int32_t dx, dy;
    pg_controller_look(&remainder, stick, stick, 1.0 / hz, &dx, &dy);
    result += dx;
    assert(dx * dy <= 0);
  }
  return result;
}

int main(void) {
  for (unsigned hz = 30; hz <= 120; hz *= 2) {
    assert(abs(integrate(1, hz) - 28800) <= 1);
    assert(abs(integrate(-1, hz) + 28800) <= 1);
    assert(abs(integrate(0.2f, hz) - integrate(0.2f, 60)) <= 1);
    assert(integrate(0.09f, hz) == 0);
    assert(integrate(NAN, hz) == 0);
    assert(integrate(INFINITY, hz) == 0);
  }
  PGLookRemainder remainder = {0};
  int32_t dx, dy;
  pg_controller_look(&remainder, 0.101f, 0.101f, 1.0/120, &dx, &dy);
  assert(remainder.x != 0);
  pg_controller_look(&remainder, 0, 0, 1.0/120, &dx, &dy);
  assert(dx == 0 && dy == 0 && remainder.x == 0 && remainder.y == 0);
  pg_controller_look(&remainder, 1, 1, 100, &dx, &dy);
  assert(dx == 144 && dy == -108);
  pg_controller_look(&remainder, 1, 1, NAN, &dx, &dy);
  assert(dx == 0 && dy == 0);
  pg_controller_look(&remainder, 1, 1, -1, &dx, &dy);
  assert(dx == 0 && dy == 0);
  assert(pg_look_axis(2) == 1);
  puts("Controller look: consistent speed at 30/60/120 Hz, fine input, dead zone, signs and resume bounds passed.");
}
