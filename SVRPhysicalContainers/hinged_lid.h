#pragma once
#include <algorithm>
#include <cmath>
struct LidResult {float angle,speed;bool closed;};
struct HingedLid {
 bool upper=false,closing=false;
 LidResult Step(float angle,float speed,float limit,bool held,bool contact,float dt){
  if(held){upper=false;closing=false;return {angle,speed,false};}
  if(upper && contact && speed<-.05f)upper=false;
  if(upper)return {limit,0,false};
  if(angle>=limit-.008f && speed>=0){upper=true;closing=false;return {limit,0,false};}
  if(speed<-.03f)closing=true;
  // Capture the closing trajectory even if Havok already reversed its velocity at the bottom.
  if(angle<=.05235988f && closing){closing=false;return {0,0,true};}
  if(!contact && angle>.05235988f && angle<limit-.008f){
   speed=std::clamp(speed-8.f*(std::max)(0.f,std::cos(angle))*dt,-3.5f,3.5f);
   if(speed<-.03f)closing=true;
  }
  if(angle>.15f && speed>.1f)closing=false;
  return {angle,speed,false};
 }
};

