#pragma once
constexpr float HingedInventoryThreshold = .13962634f; // 8 degrees
constexpr float DrawerInventoryThreshold(float limit){
 const float earlyTravel=limit*.20f;
 return earlyTravel<.02f?earlyTravel:.02f;
}
constexpr bool OpeningTriggersInventory(float previous,float current,float speed,float threshold){
 return current>threshold && (current>previous+.00001f || speed>.01f);
}
constexpr bool ClosedEnoughToRearm(float position,bool sliding){return position<=(sliding?.003f:.035f);}
