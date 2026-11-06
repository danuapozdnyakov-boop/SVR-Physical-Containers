#include "hinged_lid.h"
#include <cassert>
int main(){
 HingedLid l;auto r=l.Step(.7f,0,1.5f,false,false,.02f);assert(r.speed<0 && !r.closed);
 r=l.Step(.3f,-2,1.5f,false,false,.02f);assert(r.speed<0);
 r=l.Step(.02f,1.5f,1.5f,false,false,.02f);assert(r.closed && r.speed==0);
 HingedLid up;r=up.Step(1.5f,2,1.5f,false,false,.02f);assert(r.angle==1.5f && r.speed==0);
 r=up.Step(1.5f,-.01f,1.5f,false,false,.02f);assert(r.speed==0);
 r=up.Step(1.49f,-.4f,1.5f,false,true,.02f);assert(r.speed<0);
 HingedLid held;r=held.Step(.7f,1,1.5f,true,false,.02f);assert(r.speed==1);
 HingedLid opening;r=opening.Step(.02f,1,1.5f,false,true,.02f);assert(!r.closed);
}
