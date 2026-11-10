#include "close_assist.h"
#include "interaction_policy.h"
#include <cassert>
#include <cstdio>
int main(){
 assert(CloseAssistSpeed(.04f,0,false,false,false)<0); // released lid two degrees from shut
 assert(CloseAssistSpeed(.05235988f,0,false,false,false)<0);
 assert(CloseAssistSpeed(.06f,0,false,false,false)==0); // outside latch zone
 assert(CloseAssistSpeed(1.f,0,false,false,false)==0); // stays open
 assert(CloseAssistSpeed(.04f,.01f,false,false,false)==.01f); // deliberate opening
 assert(CloseAssistSpeed(.04f,0,true,false,false)==0); // grab owns the part
 assert(CloseAssistSpeed(.04f,0,false,true,false)==0); // lock owns the part
 assert(CloseAssistSpeed(.006f,0,false,false,true)<0); // drawer six mm from shut
 assert(CloseAssistSpeed(.007f,0,false,false,true)==0);
 assert(CloseAssistSpeed(0,0,false,false,true)==0);
 assert(OpeningTriggersInventory(.12f,.15f,.3f,HingedInventoryThreshold));
 assert(!OpeningTriggersInventory(.0f,.02f,.3f,HingedInventoryThreshold));
 assert(OpeningTriggersInventory(.01f,.021f,.2f,DrawerInventoryThreshold(.1f)));
 assert(!OpeningTriggersInventory(.025f,.021f,-.2f,DrawerInventoryThreshold(.1f)));
 assert(!OpeningTriggersInventory(.8f,.7f,-.2f,.5235988f)); // closing an open chest
 assert(!OpeningTriggersInventory(.7f,.7f,0,.5235988f)); // touching an already open lid
 assert(!ClosedEnoughToRearm(.7f,false));
 assert(ClosedEnoughToRearm(.02f,false));
 assert(!ClosedEnoughToRearm(.1f,true));
 puts("PASS: three-degree/six-mm latch zone; no attraction when open, grabbed, locked or opening");
}
