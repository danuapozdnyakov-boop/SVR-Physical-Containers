#include "latch.h"
#include <cassert>
#include <cstdio>
#include <initializer_list>
int main(){
 for(bool sliding:{false,true}){
  ContainerLatch l;float near=sliding?.004f:.04f;
  assert(l.Update(0,0,false,false,sliding));
  assert(!l.Update(0,0,true,false,sliding)); // fresh grab releases latch
  assert(!l.Update(near,.2f,true,false,sliding));
  assert(!l.Update(.5f,.2f,true,false,sliding));
  assert(l.Update(near,-.2f,true,false,sliding)); // closing while still held
  assert(l.Update(.1f,2.f,true,false,sliding)); // remains locked despite impulse
  assert(l.Update(0,0,false,false,sliding));
  assert(!l.Update(0,0,true,false,sliding)); // only next grab releases
  assert(l.Update(near,.005f,false,false,sliding)); // small rebound captured
  ContainerLatch open;open.latched=false;
  assert(!open.Update(.5f,0,false,false,sliding)); // no attraction from wide open
  assert(!open.Update(near,.2f,false,false,sliding)); // opening motion is free
 }
 puts("PASS: near-close latch, rebound immunity and release only on next grab; hinges and drawers");
}
