#pragma once
constexpr bool OpeningTriggersInventory(float previous,float current,float speed,float threshold){
 return current>threshold && (current>previous+.00001f || speed>.01f);
}
constexpr bool ClosedEnoughToRearm(float position,bool sliding){return position<=(sliding?.003f:.035f);}
