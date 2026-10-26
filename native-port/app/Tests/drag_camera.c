#include "NativeDragCamera.h"
#include <assert.h>
int main(void){
 float a=pg_drag_camera_axis(120.0/30,1.0/30);
 float b=pg_drag_camera_axis(120.0/60,1.0/60);
 float c=pg_drag_camera_axis(120.0/120,1.0/120);
 assert(fabs(a-b)<0.00001&&fabs(b-c)<0.00001);
 assert(pg_drag_camera_axis(0,1.0/60)==0);
 assert(pg_drag_camera_axis(100,0.5)==0);
 assert(pg_drag_camera_axis(NAN,0.01)==0);
 assert(pg_drag_camera_axis(1,NAN)==0);
 assert(pg_drag_camera_axis(-2,0.02)<0);
 assert(pg_drag_camera_axis(200,0.02)==1);
 return 0;
}
