#pragma once
#include <math.h>
#include <stdint.h>
#include <stdbool.h>
#include <limits.h>

typedef struct { double x, y; } PGTouchCameraRemainder;

// Convert one engine poll's queued drag to mouse pixels. Preserve sub-pixel
// motion, but discard stale input after a stall or when touch look is disabled.
static inline void pg_touch_camera_motion(PGTouchCameraRemainder *state,
    double x, double y, double seconds, bool enabled, int32_t *dx, int32_t *dy) {
    *dx = *dy = 0;
    if (!enabled || !isfinite(x) || !isfinite(y) || !isfinite(seconds) || seconds <= 0 || seconds > 0.05) {
        state->x = state->y = 0;
        return;
    }
    double nextX = fmax(INT32_MIN, fmin(INT32_MAX, state->x + x * 1.6));
    double nextY = fmax(INT32_MIN, fmin(INT32_MAX, state->y + y * 1.6));
    *dx = (int32_t)trunc(nextX);
    *dy = (int32_t)trunc(nextY);
    state->x = nextX - *dx;
    state->y = nextY - *dy;
}
