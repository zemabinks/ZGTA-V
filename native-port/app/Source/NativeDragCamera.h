#pragma once
#include <math.h>

// Same pad dead-zone mapping as Port's lookAxis, fed by relative motion
// consumed on the engine's pad update, rather than the UI's display rate.
static inline float pg_drag_camera_axis(double points, double seconds) {
 if(!isfinite(points)||!isfinite(seconds)||seconds<=0||seconds>0.05)return 0;
 double speed=fabs(points)/fmax(seconds,1.0/240.0);
 if(speed<=3)return 0;
 double amount=fmin(1,speed/180.0);
 return (float)copysign(0.35+0.65*pow(amount,0.70),points);
}
