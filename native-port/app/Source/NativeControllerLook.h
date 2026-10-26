#pragma once
#include <math.h>
#include <stdint.h>

// Mouse deltas are accumulated by the game between input polls. Integrate stick
// velocity in seconds so 30, 60 and 120 Hz displays have the same camera speed.
typedef struct { double x, y; } PGLookRemainder;

static inline double pg_look_axis(float input) {
  if (!isfinite(input)) return 0;
  double magnitude = fmin(fabs((double)input), 1.0);
  if (magnitude <= 0.10) return 0;
  double amount = (magnitude - 0.10) / 0.90;
  // Preserve fine adjustment near the centre, with full speed at the edge.
  return copysign(amount * (0.70 + 0.30 * amount), input);
}

static inline int32_t pg_look_delta(double axis, double seconds, double speed, double *remainder) {
  if (!axis) { *remainder = 0; return 0; }
  double total = *remainder + axis * speed * seconds;
  int32_t whole = (int32_t)trunc(total);
  *remainder = total - whole;
  return whole;
}

static inline void pg_controller_look(PGLookRemainder *remainder, float x, float y,
                                      double seconds, int32_t *dx, int32_t *dy) {
  *dx = *dy = 0;
  if (!isfinite(seconds) || seconds <= 0) { remainder->x = remainder->y = 0; return; }
  // Avoid a large camera jump after a suspended or stalled UI callback.
  seconds = fmin(seconds, 0.05);
  *dx = pg_look_delta(pg_look_axis(x), seconds, 2880.0, &remainder->x);
  *dy = pg_look_delta(-pg_look_axis(y), seconds, 2160.0, &remainder->y);
}
