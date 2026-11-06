#pragma once
#include <algorithm>
// Only the last three degrees / six millimetres. Never fight an active grab,
// an opening motion, a locked mechanism, or a deliberately half-open container.
constexpr bool CloseAssistEligible(float distance,float velocity,bool held,bool locked,bool sliding){
 return !held && !locked && distance>0 && distance<=(sliding?.006f:.05235988f) && velocity<=0.f;
}
inline float CloseAssistSpeed(float distance,float velocity,bool held,bool locked,bool sliding){
 if(!CloseAssistEligible(distance,velocity,held,locked,sliding))return velocity;
 return -(std::min)(sliding?.06f:.35f,distance*(sliding?8.f:6.f));
}
