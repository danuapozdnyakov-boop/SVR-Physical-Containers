#pragma once
struct ContainerLatch {
 bool latched=true,wasHeld=false,canLatch=false;
 bool Update(float distance,float speed,bool held,bool locked,bool sliding){
  const float zone=sliding?.006f:.05235988f;
  if(held && !wasHeld){latched=false;canLatch=false;}
  if(!held || distance>zone*1.5f)canLatch=true;
  // Small positive rebound is captured too. An intentional opening is not.
  if(!latched && canLatch && !locked && distance<=zone && speed<=.01f)latched=true;
  wasHeld=held;
  return latched;
 }
};
