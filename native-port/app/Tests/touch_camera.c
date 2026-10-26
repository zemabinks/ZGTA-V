#include "NativeTouchCamera.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

static int drag(int hz, double sign) {
    PGTouchCameraRemainder state = {0};
    int total = 0;
    for (int i = 0; i < hz; i++) {
        int32_t x, y;
        pg_touch_camera_motion(&state, sign * 120 / hz, sign * 120 / hz, 1.0 / hz, true, &x, &y);
        assert(x == y);
        total += x;
    }
    return total;
}
int main(void) {
    for (int sign = -1; sign <= 1; sign += 2) {
        assert(abs(drag(30, sign) - sign * 192) <= 1);
        assert(abs(drag(60, sign) - sign * 192) <= 1);
        assert(abs(drag(120, sign) - sign * 192) <= 1);
    }
    PGTouchCameraRemainder state = {0};
    int32_t x, y;
    pg_touch_camera_motion(&state, .2, -.2, 1.0/60, true, &x, &y);
    assert(x == 0 && y == 0 && state.x > 0 && state.y < 0);
    for (int i = 0; i < 4; i++) pg_touch_camera_motion(&state, .2, -.2, 1.0/60, true, &x, &y);
    assert(state.x > .5 && state.y < -.5); // Small drags retain their fractional motion.
    pg_touch_camera_motion(&state, 0, 0, 1.0/60, true, &x, &y);
    assert(x == 0 && y == 0); // A resting finger never keeps rotating.
    pg_touch_camera_motion(&state, 100, -100, .5, true, &x, &y);
    assert(x == 0 && y == 0 && state.x == 0 && state.y == 0);
    pg_touch_camera_motion(&state, 1, -1, 1.0/60, true, &x, &y);
    assert(x == 1 && y == -1); // Resume has no stale jump.
    pg_touch_camera_motion(&state, 100, 100, 1.0/60, false, &x, &y);
    assert(x == 0 && y == 0 && state.x == 0 && state.y == 0);
    pg_touch_camera_motion(&state, NAN, 1, 1.0/60, true, &x, &y);
    assert(x == 0 && y == 0);
    pg_touch_camera_motion(&state, 1, 1, NAN, true, &x, &y);
    assert(x == 0 && y == 0);
    puts("Touch camera: directions, sub-pixel motion, 30/60/120 Hz, idle, stall and reset passed");
    return 0;
}
