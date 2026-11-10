#include "RE/Skyrim.h"
#include "SKSE/SKSE.h"
#include "HiggsInterface.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <mutex>
#include <unordered_map>
#include <unordered_set>
#include <atomic>
#include "models.generated.h"
#include "close_assist.h"
#include "latch.h"
#include "hinged_lid.h"
#include "removable_latch.h"
#include "interaction_policy.h"
#include <memory>
#include "contact_policy.h"
using namespace std::literals;
static std::ofstream logFile;
static std::atomic_bool gameReady=false;
static std::atomic<const char*> phase{"plugin loading"};
static HANDLE crashFile=INVALID_HANDLE_VALUE;
static LONG WINAPI recordFault(EXCEPTION_POINTERS* e){
 if(!e || crashFile==INVALID_HANDLE_VALUE)return EXCEPTION_CONTINUE_SEARCH;
 DWORD code=e->ExceptionRecord->ExceptionCode;
 if(code!=EXCEPTION_ACCESS_VIOLATION && code!=EXCEPTION_ILLEGAL_INSTRUCTION)return EXCEPTION_CONTINUE_SEARCH;
 static thread_local bool writing=false;if(writing)return EXCEPTION_CONTINUE_SEARCH;writing=true;
 char line[1024];DWORD written;MEMORY_BASIC_INFORMATION info{};char module[MAX_PATH]{};
 VirtualQuery(e->ExceptionRecord->ExceptionAddress,&info,sizeof(info));
 if(info.Type==MEM_IMAGE)GetModuleFileNameA(static_cast<HMODULE>(info.AllocationBase),module,MAX_PATH);
 int count=snprintf(line,sizeof(line),"exception=%08lX phase=%s module=%s offset=%llX rip=%llX rsp=%llX\r\n",code,phase.load(),module,
  (unsigned long long)((uintptr_t)e->ExceptionRecord->ExceptionAddress-(uintptr_t)info.AllocationBase),
  (unsigned long long)e->ContextRecord->Rip,(unsigned long long)e->ContextRecord->Rsp);
 if(count>0)WriteFile(crashFile,line,(DWORD)(std::min)(count,(int)sizeof(line)-1),&written,nullptr);
 uintptr_t stack[64]{};SIZE_T size=0;
 if(ReadProcessMemory(GetCurrentProcess(),(void*)e->ContextRecord->Rsp,stack,sizeof(stack),&size)){
  for(unsigned i=0;i<size/sizeof(uintptr_t);++i){
   MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery((void*)stack[i],&m,sizeof(m)) || m.Type!=MEM_IMAGE)continue;
   if(!(m.Protect&(PAGE_EXECUTE|PAGE_EXECUTE_READ|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY)))continue;
   module[0]=0;GetModuleFileNameA(static_cast<HMODULE>(m.AllocationBase),module,MAX_PATH);
   count=snprintf(line,sizeof(line),"stack_candidate[%u]=%s+%llX\r\n",i,module,(unsigned long long)(stack[i]-(uintptr_t)m.AllocationBase));
   if(count>0)WriteFile(crashFile,line,(DWORD)(std::min)(count,(int)sizeof(line)-1),&written,nullptr);
  }
 }
 FlushFileBuffers(crashFile);writing=false;
 return EXCEPTION_CONTINUE_SEARCH;  // Diagnostic only: never suppress or resume a game fault.
}
struct V {float x,y,z;};
static V read(const RE::hkVector4& v){return {v.quad.m128_f32[0],v.quad.m128_f32[1],v.quad.m128_f32[2]};}
static float dot(V a,V b){return a.x*b.x+a.y*b.y+a.z*b.z;}
static V cross(V a,V b){return {a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};}
static V scale(V a,float s){return {a.x*s,a.y*s,a.z*s};}
static V add(V a,V b){return {a.x+b.x,a.y+b.y,a.z+b.z};}
static V unit(V a){return scale(a,1/std::sqrt((std::max)(dot(a,a),1e-12f)));}
static RE::hkVector4 packed(V a){RE::hkVector4 v;v.quad=_mm_set_ps(0,a.z,a.y,a.x);return v;}
static RE::hkQuaternion quaternion(V x,V y,V z){
 float qx,qy,qz,qw;float trace=x.x+y.y+z.z;
 if(trace>0){float s=std::sqrt(trace+1)*2;qw=s/4;qx=(y.z-z.y)/s;qy=(z.x-x.z)/s;qz=(x.y-y.x)/s;}
 else if(x.x>y.y && x.x>z.z){float s=std::sqrt(1+x.x-y.y-z.z)*2;qw=(y.z-z.y)/s;qx=s/4;qy=(y.x+x.y)/s;qz=(z.x+x.z)/s;}
 else if(y.y>z.z){float s=std::sqrt(1+y.y-x.x-z.z)*2;qw=(z.x-x.z)/s;qx=(y.x+x.y)/s;qy=s/4;qz=(z.y+y.z)/s;}
 else{float s=std::sqrt(1+z.z-x.x-y.y)*2;qw=(x.y-y.x)/s;qx=(z.x+x.z)/s;qy=(z.y+y.z)/s;qz=s/4;}
 RE::hkQuaternion q;q.vec.quad=_mm_set_ps(qw,qz,qy,qx);return q;
}
static V rotate(RE::hkpRigidBody* b,V v){
 auto& m=b->motion.motionState.transform.rotation;
 auto x=read(m.col0),y=read(m.col1),z=read(m.col2);
 return add(add(scale(x,v.x),scale(y,v.y)),scale(z,v.z));
}
static std::atomic_uint64_t disabledContainerContacts=0;
struct BodyOwner {std::uint32_t uid;RE::NiAVObject* root;bool removable=false;};
using BodyOwners=std::unordered_map<RE::hkpRigidBody*,BodyOwner>;
static std::atomic<std::shared_ptr<const BodyOwners>> containerOwners{std::make_shared<const BodyOwners>()};
struct ContainerContactListener final:RE::hkpContactListener{
 void ContactPointCallback(const RE::hkpContactPointEvent& e) override{
  const unsigned source=unsigned(e.source);if(source>1 || !e.contactPointProperties)return;
  auto partner=e.bodies[1-source];if(!partner)return;
  const unsigned layer=partner->collidable.broadPhaseHandle.collisionFilterInfo.filter&0x7f;
  auto own=e.bodies[source];auto owners=containerOwners.load(std::memory_order_acquire);
  auto a=owners->find(own),b=owners->find(partner);
  bool sameContainer=own && a!=owners->end() && b!=owners->end() && a->second.uid==own->uid && b->second.uid==partner->uid && a->second.root==b->second.root;
  // Free lids must collide with floors/walls; only their own container is suppressed.
  if(!sameContainer && a!=owners->end() && a->second.removable)return;
  if(!sameContainer && !ContainerIgnoresPartnerLayer(layer))return;
  // HIGGS uses this same solver flag. No global collision table or other objects are modified.
  e.contactPointProperties->flags.set(RE::hkContactPointMaterial::Flag::kIsDisabled);
  if(e.contactMgr)e.contactMgr->contactPointCallbackDelay=0;
  disabledContainerContacts.fetch_add(1,std::memory_order_relaxed);
 }
};
static ContainerContactListener containerContacts;
static std::unordered_map<RE::hkpRigidBody*,std::uint32_t> registeredContacts;
struct Leaf {HingedLid lid;ContainerLatch latch;RE::NiAVObject* node=nullptr;RE::NiAVObject* anchorNode=nullptr;RE::bhkRigidBody* body=nullptr; RE::bhkRigidBody* anchor=nullptr; RE::NiAVObject* shadow=nullptr;const LeafProfile* profile=nullptr;RE::hkpRigidBody* contactBody=nullptr;std::uint32_t contactUid=0;std::uint32_t poseUid=0;bool poseInitialized=false;float angle=0;bool detached=false;};
struct Door {
 RE::ObjectRefHandle handle;RE::NiAVObject* root=nullptr;std::vector<Leaf> leaves;
 bool locked=false,activated=false;float cooldown=0;
};
static std::vector<Door> doors;
static std::unordered_set<RE::FormID> supported;
static std::mutex stateMutex;
struct ActivationRequest { RE::ObjectRefHandle handle; bool lockpick; };
static std::vector<ActivationRequest> queuedActivation;
static std::atomic_uint menuSuspended=0;
static void menuState(unsigned bit,bool opening){if(opening)menuSuspended.fetch_or(bit);else menuSuspended.fetch_and(~bit);}
static RE::ObjectRefHandle lastInteraction;
struct MenuGrip {RE::ObjectRefHandle handle;unsigned retry=0;};
static MenuGrip menuGrip[2];
struct HiddenDoor {RE::ObjectRefHandle handle;RE::NiAVObject* root;bool culled;};
static std::vector<HiddenDoor> hiddenDoors;
static void restoreHidden(){
 for(auto& d:hiddenDoors)if(auto ref=d.handle.get())if(ref->Get3D()==d.root)d.root->SetAppCulled(d.culled);
 hiddenDoors.clear();
}
struct MenuEvents final:RE::BSTEventSink<RE::MenuOpenCloseEvent>{
 RE::BSEventNotifyControl ProcessEvent(const RE::MenuOpenCloseEvent* e,RE::BSTEventSource<RE::MenuOpenCloseEvent>*) override{
  if(!e)return RE::BSEventNotifyControl::kContinue;
  if(e->menuName==RE::ContainerMenu::MENU_NAME){
   if(e->opening){
    auto api=HiggsAPI::g_higgs;
    if(api)for(int h=0;h<2;++h){
     menuGrip[h]={};auto ref=api->GetGrabbedObject(h==0);if(!ref)continue;
     std::lock_guard guard(stateMutex);
     for(auto& d:doors)if(d.handle==ref->GetHandle())for(auto& l:d.leaves)
      if(l.profile && l.profile->removable && api->GetGrabbedRigidBody(h==0)==l.body)menuGrip[h]={ref->GetHandle(),60};
    }
   }
   menuState(1,e->opening);
  }else if(e->menuName==RE::LoadingMenu::MENU_NAME){
   std::lock_guard guard(stateMutex);
   if(e->opening){menuState(4,true);restoreHidden();doors.clear();queuedActivation.clear();}
   else menuState(4,false);
   logFile<<"loading menu="<<e->opening<<"; container tracking reset\n";logFile.flush();
  }else if(e->menuName==RE::LockpickingMenu::MENU_NAME){
   std::lock_guard guard(stateMutex);restoreHidden();menuState(2,e->opening);
   if(e->opening){
    // Use the engine's exact lockpick target; never guess by proximity to a chest or door.
    auto targetOwner=RE::LockpickingMenu::GetTargetReference();auto target=targetOwner.get();
    if(target && (!target->GetBaseObject() || !supported.contains(target->GetBaseObject()->GetFormID())))target=nullptr;
    if(target && target->Get3D()){
     auto root=target->Get3D();hiddenDoors.push_back({target->GetHandle(),root,root->GetAppCulled()});root->SetAppCulled(true);
     logFile<<"lockpick: hidden door="<<std::hex<<target->GetFormID()<<std::dec<<'\n';logFile.flush();
    }
   }
  }
  return RE::BSEventNotifyControl::kContinue;
 }
};
static MenuEvents menuEvents;
static RE::bhkRigidBody* bodyOf(RE::NiAVObject* n){
 if(!n || !n->collisionObject)return nullptr;
 auto c=n->collisionObject->AsBhkNiCollisionObject();
 return c && c->body ? c->body->AsBhkRigidBody():nullptr;
}
static void collectOwners(RE::NiAVObject* root,RE::NiAVObject* node,BodyOwners& owners,unsigned depth=0){
 if(!node || depth>64)return;
 if(auto wrapper=bodyOf(node))if(auto body=wrapper->GetRigidBody())owners[body]={body->uid,root};
 if(auto group=node->AsNode())for(auto& child:group->GetChildren())collectOwners(root,child.get(),owners,depth+1);
}
static RE::NiAVObject* find(RE::NiAVObject* root,const std::string& name){return root->GetObjectByName(RE::BSFixedString(name.c_str()));}
static void collect(RE::NiAVObject* root,RE::NiAVObject* n,std::vector<Leaf>& leaves,const ModelProfile& model,unsigned depth=0){
 if(!n || depth>64)return;
 std::string name=n->name.c_str()?n->name.c_str():"";
 if(name.starts_with("SVC_Physical_")){
  auto anchor=find(root,"SVC_Anchor_"+name.substr(13));
  auto body=bodyOf(n),fixed=bodyOf(anchor);
  if(body && fixed){
   Leaf l;l.body=body;l.anchor=fixed;l.node=n;l.anchorNode=anchor;
   // The original target name is retained in an empty animated node.
   for(const auto& p:model.leaves)if(name==p.leaf){
    l.profile=&p;if(auto s=find(root,p.shadow))l.shadow=s;break;
   }
   leaves.push_back(std::move(l));
  }
 }
 if(auto node=n->AsNode())for(auto& child:node->GetChildren())collect(root,child.get(),leaves,model,depth+1);
}
static void queue(Door& d,bool lockpick=false){
 if(d.activated || d.cooldown>0)return;
 queuedActivation.push_back({d.handle,lockpick});d.activated=true;d.cooldown=3.f;
}
static bool handNear(RE::bhkRigidBody* wrapper){
 auto api=HiggsAPI::g_higgs;if(!api)return false;
 RE::hkAabb aabb;wrapper->GetAabbWorldspace(aabb);
 auto lo=read(aabb.min),hi=read(aabb.max);
 for(bool left:{false,true})if(auto object=api->GetHandRigidBody(left))if(auto hand=object->AsBhkRigidBody())if(auto b=hand->GetRigidBody()){
  auto p=read(b->motion.motionState.transform.translation);
  if(p.x>=lo.x-.18f && p.x<=hi.x+.18f && p.y>=lo.y-.18f && p.y<=hi.y+.18f && p.z>=lo.z-.18f && p.z<=hi.z+.18f)return true;
 }
 return false;
}
static void physics(void* w){
 auto api=HiggsAPI::g_higgs;if(!api || !w || !gameReady.load() || menuSuspended.load())return;
 auto world=static_cast<RE::bhkWorld*>(w);
 static auto previous=std::chrono::steady_clock::now();auto now=std::chrono::steady_clock::now();
 float dt=std::clamp(std::chrono::duration<float>(now-previous).count(),.001f,.03f);previous=now;
 std::lock_guard guard(stateMutex);if(doors.empty())return;
 phase.store("physics: world lock");RE::BSWriteLockGuard worldGuard(world->worldLock);
 for(auto& d:doors){
  auto ref=d.handle.get();if(!ref || !ref->loadedData || ref->loadedData->data3D.get()!=d.root)continue;
  bool held=api->GetGrabbedObject(true)==ref.get() || api->GetGrabbedObject(false)==ref.get();
  d.cooldown=(std::max)(0.f,d.cooldown-dt);bool allClosed=true;
  for(auto& l:d.leaves){
   auto leaf=l.body->GetRigidBody(),anchor=l.anchor->GetRigidBody();
   if(!l.profile || !leaf || !anchor || leaf->world!=world->GetWorld1() || anchor->world!=leaf->world)continue;
   if(!registeredContacts.contains(leaf) || registeredContacts[leaf]!=leaf->uid){
    auto owners=std::make_shared<BodyOwners>(*containerOwners.load());collectOwners(d.root,d.root,*owners);
    for(auto& owned:d.leaves)if(owned.profile && owned.profile->removable)if(auto rb=owned.body->GetRigidBody())if(owners->contains(rb))(*owners)[rb].removable=true;
    containerOwners.store(owners,std::memory_order_release);
    leaf->contactPointCallbackDelay=0;leaf->AddContactListener(&containerContacts);registeredContacts[leaf]=leaf->uid;l.contactBody=leaf;l.contactUid=leaf->uid;
   }
   bool initialize=!l.poseInitialized || l.poseUid!=leaf->uid;
   if(initialize){
    auto pos=anchor->motion.motionState.transform.translation;
    auto q=quaternion(rotate(anchor,{1,0,0}),rotate(anchor,{0,1,0}),rotate(anchor,{0,0,1}));
    l.body->SetPositionAndRotation(pos,q);leaf->SetLinearVelocity(packed({0,0,0}));leaf->SetAngularVelocity(packed({0,0,0}));l.poseInitialized=true;l.poseUid=leaf->uid;l.latch=ContainerLatch{};
   }
   bool partHeld=held && (api->GetGrabbedRigidBody(true)==l.body || api->GetGrabbedRigidBody(false)==l.body);
   if(l.profile->removable){
    auto pos=anchor->motion.motionState.transform.translation;
    // Compare centres, not hinge origins: a rotated lid must not need an exact pivot match.
    auto com=read(leaf->motion.motionState.sweptTransform.centerOfMassLocal);
    auto currentCenter=add(read(leaf->motion.motionState.transform.translation),rotate(leaf,com));
    auto seatedCenter=add(read(pos),rotate(anchor,com));
    auto delta=add(currentCenter,scale(seatedCenter,-1));
    float distance=std::sqrt(dot(delta,delta));
    auto up=unit(rotate(anchor,{0,0,1}));
    float height=dot(delta,up);
    float radial=std::sqrt((std::max)(0.f,dot(delta,delta)-height*height));
    UpdateRemovableLatch(l.latch,l.detached,radial,height,l.profile->snapRadius,partHeld,d.locked);
    // HIGGS owns a held body's motion; restore real gravity only after release.
    if(!partHeld && !l.latch.latched)leaf->motion.gravityFactor=1.f;
    if(l.latch.latched){
     auto q=quaternion(rotate(anchor,{1,0,0}),rotate(anchor,{0,1,0}),rotate(anchor,{0,0,1}));
     l.body->SetPositionAndRotation(pos,q);leaf->SetLinearVelocity(packed({0,0,0}));leaf->SetAngularVelocity(packed({0,0,0}));
    }
    allClosed&=l.latch.latched;
    if(!d.locked && !l.latch.latched && partHeld && distance>.12f && l.angle<=.12f)queue(d);
    l.angle=distance;
    continue;
   }
   auto& a=l.profile->axis;auto& p=l.profile->perpendicular;
   auto axis=unit(rotate(anchor,{a[0],a[1],a[2]}));auto closed=unit(rotate(anchor,{p[0],p[1],p[2]}));
   if(l.profile->sliding){
    auto origin=read(anchor->motion.motionState.transform.translation),position=read(leaf->motion.motionState.transform.translation);
    float distance=dot(add(position,scale(origin,-1)),axis);float limited=d.locked?0.f:std::clamp(distance,0.f,l.profile->limit);
    float speed=d.locked?0.f:std::clamp(dot(read(leaf->motion.linearVelocity),axis),-.8f,.8f);
    bool closeSnap=l.latch.Update(limited,speed,partHeld,d.locked,true);
    if(closeSnap)limited=0;
    auto target=add(origin,scale(axis,limited));auto error=add(position,scale(target,-1));
    auto x=rotate(anchor,{1,0,0}),y=rotate(anchor,{0,1,0}),z=rotate(anchor,{0,0,1});
    if((closeSnap && std::abs(distance)>.00001f) || dot(error,error)>.000025f || dot(rotate(leaf,{1,0,0}),x)<.99999f || dot(rotate(leaf,{0,1,0}),y)<.99999f){auto pos=packed(target);auto q=quaternion(x,y,z);l.body->SetPositionAndRotation(pos,q);}
    speed=closeSnap?0.f:CloseAssistSpeed(limited,speed,partHeld,d.locked,true);
    if((limited<=0 && speed<0)||(limited>=l.profile->limit && speed>0))speed=0;
    leaf->SetLinearVelocity(packed(scale(axis,speed)));leaf->SetAngularVelocity(packed({0,0,0}));
    bool touched=partHeld || handNear(l.body);allClosed&=ClosedEnoughToRearm(limited,true);
    bool opening=OpeningTriggersInventory(l.angle,limited,speed,DrawerInventoryThreshold(l.profile->limit));l.angle=limited;
    if(!d.locked && touched && opening)queue(d);
    continue;
   }
   auto current=rotate(leaf,{p[0],p[1],p[2]});current=unit(add(current,scale(axis,-dot(axis,current))));
   float angle=std::atan2(dot(axis,cross(closed,current)),dot(closed,current));
   float omega=dot(read(leaf->motion.angularVelocity),axis);
   float limited=d.locked?0.f:std::clamp(angle,0.f,l.profile->limit);
   if(std::abs(axis.z)<.3f && !d.locked){auto result=l.lid.Step(limited,omega,l.profile->limit,partHeld,handNear(l.body),dt);limited=result.angle;omega=result.speed;if(result.closed)l.latch.latched=true;}
   bool closeSnap=l.latch.Update(limited,omega,partHeld,d.locked,false);
   if(closeSnap)limited=0;
   auto turn=[&](V v){return add(add(scale(v,std::cos(limited)),scale(cross(axis,v),std::sin(limited))),scale(axis,dot(axis,v)*(1-std::cos(limited))));};
   auto x=turn(rotate(anchor,{1,0,0})),y=turn(rotate(anchor,{0,1,0})),z=turn(rotate(anchor,{0,0,1}));
   auto position=read(anchor->motion.motionState.transform.translation);
   auto error=add(position,scale(read(leaf->motion.motionState.transform.translation),-1));
   auto movingAxis=unit(rotate(leaf,{a[0],a[1],a[2]}));
   if((closeSnap && (std::abs(angle)>.00001f || dot(error,error)>1e-10f || dot(rotate(leaf,{1,0,0}),x)<.999999f || dot(rotate(leaf,{0,1,0}),y)<.999999f)) || std::abs(limited-angle)>.00001f || dot(error,error)>.00000025f || dot(movingAxis,axis)<.999998f || (d.locked && std::abs(angle)>.0002f)){
    auto pos=packed(position);auto q=quaternion(x,y,z);l.body->SetPositionAndRotation(pos,q);
   }
   angle=limited;if(d.locked || (angle<=0 && omega<0) || (angle>=l.profile->limit && omega>0))omega=0;
   // Small latch attraction only near fully closed; no return from open positions.
   omega=closeSnap?0.f:CloseAssistSpeed(angle,omega,partHeld,d.locked,false);
   omega=std::clamp(omega,-3.5f,3.5f);
   auto angular=scale(axis,omega);auto com=read(leaf->motion.motionState.sweptTransform.centerOfMassLocal);
   auto radius=add(add(scale(x,com.x),scale(y,com.y)),scale(z,com.z));auto linear=cross(angular,radius);
   auto angularError=add(angular,scale(read(leaf->motion.angularVelocity),-1));auto linearError=add(linear,scale(read(leaf->motion.linearVelocity),-1));
   if(dot(angularError,angularError)>1e-8f)leaf->SetAngularVelocity(packed(angular));
   if(dot(linearError,linearError)>1e-8f)leaf->SetLinearVelocity(packed(linear));
   bool opening=OpeningTriggersInventory(l.angle,angle,omega,HingedInventoryThreshold);l.angle=angle;bool touched=partHeld || handNear(l.body);allClosed&=ClosedEnoughToRearm(angle,false);
   if(!d.locked && touched && opening)queue(d);
  }
  // An open container remains consumed even if the hand leaves. Rearm after closing;
  // Rearm lockpicking after release so only a new grab can try again.
  if(d.cooldown<=0 && (d.locked?!held:allClosed))d.activated=false;
 }
 phase.store("idle after physics");
}
static void grabbed(bool,RE::TESObjectREFR* ref){
 if(!ref)return;std::lock_guard guard(stateMutex);
 for(auto& d:doors)if(d.handle==ref->GetHandle() && d.locked){queue(d,true);break;}
}
// HIGGS can move a held part after the pre-physics callback. A closed latch
// must remain shut until a NEW grab; keep bodies dynamic so HIGGS can select them.
static void holdLatches(){
 if(!gameReady.load() || menuSuspended.load())return;
 auto player=RE::PlayerCharacter::GetSingleton();auto cell=player?player->GetParentCell():nullptr;
 auto world=cell?cell->GetbhkWorld():nullptr;if(!world)return;
 std::lock_guard guard(stateMutex);if(doors.empty())return;
 RE::BSWriteLockGuard worldGuard(world->worldLock);
 for(auto& d:doors){
  auto ref=d.handle.get();if(!ref || !ref->loadedData || ref->loadedData->data3D.get()!=d.root)continue;
  for(auto& l:d.leaves){
   auto leaf=l.body->GetRigidBody(),anchor=l.anchor->GetRigidBody();
   if(!l.poseInitialized || !leaf || !anchor || leaf->uid!=l.poseUid || leaf->world!=world->GetWorld1() || anchor->world!=leaf->world)continue;
   if(!l.latch.latched){
    if(l.profile->removable)continue;
    auto& a=l.profile->axis;auto& p=l.profile->perpendicular;
    auto axis=unit(rotate(anchor,{a[0],a[1],a[2]}));
    auto origin=read(anchor->motion.motionState.transform.translation);
    auto x=rotate(anchor,{1,0,0}),y=rotate(anchor,{0,1,0}),z=rotate(anchor,{0,0,1});
    auto position=origin;float value=0;
    if(l.profile->sliding){
     value=std::clamp(dot(add(read(leaf->motion.motionState.transform.translation),scale(origin,-1)),axis),0.f,l.profile->limit);
     position=add(origin,scale(axis,value));
     auto speed=dot(read(leaf->motion.linearVelocity),axis);if((value<=0 && speed<0)||(value>=l.profile->limit && speed>0))speed=0;
     leaf->SetLinearVelocity(packed(scale(axis,speed)));leaf->SetAngularVelocity(packed({0,0,0}));
    }else{
     auto closed=rotate(anchor,{p[0],p[1],p[2]}),current=rotate(leaf,{p[0],p[1],p[2]});
     value=std::clamp(std::atan2(dot(axis,cross(closed,current)),dot(closed,current)),0.f,l.profile->limit);
     auto turn=[&](V v){return add(add(scale(v,std::cos(value)),scale(cross(axis,v),std::sin(value))),scale(axis,dot(axis,v)*(1-std::cos(value))));};
     x=turn(x);y=turn(y);z=turn(z);
     auto speed=dot(read(leaf->motion.angularVelocity),axis);if((value<=0 && speed<0)||(value>=l.profile->limit && speed>0))speed=0;
     auto angular=scale(axis,speed),com=read(leaf->motion.motionState.sweptTransform.centerOfMassLocal);
     leaf->SetAngularVelocity(packed(angular));leaf->SetLinearVelocity(packed(cross(angular,add(add(scale(x,com.x),scale(y,com.y)),scale(z,com.z)))));
    }
    auto error=add(position,scale(read(leaf->motion.motionState.transform.translation),-1));
    if(dot(error,error)>.00000025f || dot(rotate(leaf,{1,0,0}),x)<.999998f || dot(rotate(leaf,{0,1,0}),y)<.999998f){
     auto pos=packed(position);auto q=quaternion(x,y,z);l.body->SetPositionAndRotation(pos,q);
     if(l.node && l.anchorNode){auto visual=l.anchorNode->world;
      visual.rotate.entry[0][0]=x.x;visual.rotate.entry[1][0]=x.y;visual.rotate.entry[2][0]=x.z;
      visual.rotate.entry[0][1]=y.x;visual.rotate.entry[1][1]=y.y;visual.rotate.entry[2][1]=y.z;
      visual.rotate.entry[0][2]=z.x;visual.rotate.entry[1][2]=z.y;visual.rotate.entry[2][2]=z.z;
      visual.translate={position.x*69.99125f,position.y*69.99125f,position.z*69.99125f};
      l.node->local=l.node->parent?l.node->parent->world.Invert()*visual:visual;RE::NiUpdateData u{};u.flags.set(RE::NiUpdateData::Flag::kDisableCollision);l.node->UpdateDownwardPass(u,0);
     }
    }
    continue;
   }
   auto pos=anchor->motion.motionState.transform.translation;
   auto q=quaternion(rotate(anchor,{1,0,0}),rotate(anchor,{0,1,0}),rotate(anchor,{0,0,1}));
   auto error=add(read(pos),scale(read(leaf->motion.motionState.transform.translation),-1));
   bool moved=dot(error,error)>1e-10f || dot(rotate(leaf,{1,0,0}),rotate(anchor,{1,0,0}))<.999999f || dot(rotate(leaf,{0,1,0}),rotate(anchor,{0,1,0}))<.999999f;
   if(moved)l.body->SetPositionAndRotation(pos,q);
   auto linear=read(leaf->motion.linearVelocity),angular=read(leaf->motion.angularVelocity);
   if(dot(linear,linear)>1e-10f)leaf->SetLinearVelocity(packed({0,0,0}));
   if(dot(angular,angular)>1e-10f)leaf->SetAngularVelocity(packed({0,0,0}));l.angle=0;
   if(moved && l.node && l.anchorNode){
    auto visual=l.anchorNode->world;l.node->local=l.node->parent?l.node->parent->world.Invert()*visual:visual;
    RE::NiUpdateData data{};data.flags.set(RE::NiUpdateData::Flag::kDisableCollision);l.node->UpdateDownwardPass(data,0);
   }
  }
 }
}
static void update(){
 if(!gameReady.load())return;
 phase.store("update: player");
 auto player=RE::PlayerCharacter::GetSingleton();auto tes=RE::TES::GetSingleton();
 if(!player || !tes || !player->GetParentCell() || !player->Get3D())return;
 if(auto ui=RE::UI::GetSingleton();ui && ui->GameIsPaused())return;
 // Re-establish only the same removable lid if a menu released its HIGGS hold.
 // Bounded retries, no self-queued tasks, and never replace an object already in that hand.
 if(!menuSuspended.load())if(auto api=HiggsAPI::g_higgs)for(int h=0;h<2;++h){
  auto& saved=menuGrip[h];if(!saved.retry)continue;--saved.retry;
  auto ref=saved.handle.get();auto held=api->GetGrabbedObject(h==0);
  if(!ref || !ref->Get3D() || ref->IsLocked() || ref->IsActivationBlocked() || held){saved.retry=0;continue;}
  if(api->CanGrabObject(h==0))api->GrabObject(ref.get(),h==0);
 }
 std::vector<ActivationRequest> activate;
 {
  std::lock_guard guard(stateMutex);activate.swap(queuedActivation);
  for(auto& d:doors)if(auto ref=d.handle.get();ref && ref->Get3D()==d.root){
   d.locked=ref->IsLocked() || ref->IsActivationBlocked();
  }
 }
 // Engine activation and lockpick/teleport actions run outside the physics world lock.
 for(const auto& request:activate)if(auto ref=request.handle.get()){
  if(menuSuspended.load())break;
  if(!ref->Get3D() || ref->IsLocked()!=request.lockpick)continue;
  if(request.lockpick){
   auto api=HiggsAPI::g_higgs;
   if(!api || (api->GetGrabbedObject(true)!=ref.get() && api->GetGrabbedObject(false)!=ref.get()))continue;
  }
  const auto& h=request.handle;
  lastInteraction=h;
  phase.store("native container activation");
  bool success=ref->ActivateRef(player,0,nullptr,1,false);
  phase.store("after native container activation");
  logFile<<"activate ref="<<std::hex<<ref->GetFormID()<<std::dec<<" reason="<<(request.lockpick?"grab-lockpick":"opening-motion")<<" locked="<<ref->IsLocked()<<" accepted="<<success<<'\n';logFile.flush();
 }
 static unsigned frame=0;if(++frame%6)return;
 std::vector<Door> discovered;
 phase.store("update: discovering doors");
 tes->ForEachReference([&](RE::TESObjectREFR* ref){
  auto base=ref?ref->GetBaseObject():nullptr;
  if(!base || !supported.contains(base->GetFormID()) || !ref->loadedData || !ref->loadedData->data3D)return RE::BSContainer::ForEachResult::kContinue;
  Door d;d.handle=ref->GetHandle();d.root=ref->loadedData->data3D.get();d.locked=ref->IsLocked() || ref->IsActivationBlocked();
  auto modelBase=base->As<RE::TESObjectCONT>();
  if(modelBase)for(const auto& model:MODELS)if(std::string_view(modelBase->GetModel())==model.physical){
   collect(d.root,d.root,d.leaves,model);break;
  }
  if(!d.leaves.empty())discovered.push_back(std::move(d));
  return RE::BSContainer::ForEachResult::kContinue;
 });
 std::lock_guard guard(stateMutex);
 for(auto& d:discovered)for(auto& old:doors)if(old.handle==d.handle && old.root==d.root){
  d.cooldown=old.cooldown;d.activated=old.activated;
  for(auto& leaf:d.leaves)for(auto& previous:old.leaves)if(leaf.body==previous.body){leaf.lid=previous.lid;leaf.latch=previous.latch;leaf.poseUid=previous.poseUid;leaf.poseInitialized=previous.poseInitialized;leaf.angle=previous.angle;leaf.contactBody=previous.contactBody;leaf.contactUid=previous.contactUid;leaf.detached=previous.detached;break;}
  break;
 }
 if(discovered.size()!=doors.size()){logFile<<"loaded physical containers="<<discovered.size()<<'\n';logFile.flush();}
 doors=std::move(discovered);
 phase.store("idle after update");
}
static void install(){
 auto api=HiggsAPI::GetHiggsInterface();auto data=RE::TESDataHandler::GetSingleton(false);
 if(!api || !data){logFile<<"HIGGS or data handler unavailable; no models changed\n";logFile.flush();return;}
 for(auto door:data->GetFormArray<RE::TESObjectCONT>()){
  if(!door)continue;std::string name=door->GetModel()?door->GetModel():"";
  std::transform(name.begin(),name.end(),name.begin(),[](unsigned char c){return c=='/'?'\\':char(std::tolower(c));});
  for(const auto& model:MODELS)if(name==model.original){
   auto path=std::filesystem::path("Data/meshes")/model.physical;
   if(!std::filesystem::exists(path)){logFile<<"missing mesh "<<model.physical<<'\n';break;}
   door->SetModel(model.physical);supported.insert(door->GetFormID());break;
  }
 }
 if(auto ui=RE::UI::GetSingleton())ui->AddEventSink<RE::MenuOpenCloseEvent>(&menuEvents);
 api->AddPrePhysicsStepCallback(physics);api->AddPostVrikPostHiggsCallback(update);api->AddPostVrikPostHiggsCallback(holdLatches);api->AddGrabbedCallback(grabbed);
 logFile<<"C2.11 early inventory and grab-only lockpicking; gravity/rim-snap lids registered; patched base containers="<<supported.size()<<" models="<<std::size(MODELS)<<"; ordered anchors and shapes; CLUTTER leaves; scoped lockpick visibility; cell tracking reset\n";logFile.flush();
 phase.store("waiting for save load / native model loading");
}
SKSE_EXPORT constinit SKSE::PluginDeclaration SKSEPlugin_Version({
 .Version=REL::Version{0,2,11,0},.Name="SVRPhysicalContainers"sv,.Author="Local physical containers"sv,
 .StructCompatibility=SKSE::StructCompatibility::Dependent,
 .RuntimeCompatibility={REL::Version{1,4,15,0},REL::Version{1,4,15,1}},.MinimumSKSEVersion=REL::Version{0,0,0,0}
});
SKSE_PLUGIN_QUERY(const SKSE::QueryInterface* skse,SKSE::PluginInfo* info){
 info->infoVersion=SKSE::PluginInfo::kVersion;info->name="SVRPhysicalContainers";info->version=1;
 return !skse->IsEditor()&&(skse->RuntimeVersion()==REL::Version{1,4,15,0}||skse->RuntimeVersion()==REL::Version{1,4,15,1});
}
SKSE_PLUGIN_LOAD(const SKSE::LoadInterface* skse){
 SKSE::Init(skse);if(auto p=SKSE::log::log_directory()){
  logFile.open(*p/"SVRPhysicalContainers.log");
  crashFile=CreateFileW((*p/"SVRPhysicalContainers-crash.txt").c_str(),GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_WRITE_THROUGH,nullptr);
  AddVectoredExceptionHandler(0,recordFault);
 }
 SKSE::GetMessagingInterface()->RegisterListener([](SKSE::MessagingInterface::Message* m){
  if(m->type==SKSE::MessagingInterface::kDataLoaded)install();
  else if(m->type==SKSE::MessagingInterface::kPreLoadGame || m->type==SKSE::MessagingInterface::kNewGame){
   gameReady.store(false);
   std::lock_guard lock(stateMutex);restoreHidden();doors.clear();queuedActivation.clear();menuSuspended.store(false);
   if(m->type==SKSE::MessagingInterface::kNewGame)gameReady.store(true);
  }else if(m->type==SKSE::MessagingInterface::kPostLoadGame){
   // SKSE dispatches the boolean as (void*)0 or (void*)1, not a pointer to a bool.
   bool success=m->data!=nullptr;
   gameReady.store(success);logFile<<"post load success="<<success<<'\n';logFile.flush();
  }
 });return true;
}

