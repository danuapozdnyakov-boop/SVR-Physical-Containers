#pragma once
// Only used by a listener attached to this plugin's generated moving leaves.
constexpr bool ContainerIgnoresPartnerLayer(unsigned layer){
 switch(layer){
  case 1:case 2:case 9:case 13:case 17:case 27:case 31:case 35: // buildings, frames, terrain
   return true;
  default:return false; // keep HIGGS hands/held items (56), weapons, actor bodies, clutter, projectiles and picking
 }
}
