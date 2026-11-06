from pathlib import Path
s=Path('physical-containers/physical_containers.cpp').read_text(encoding='utf-8');doors=Path('standalone-doors/physical_doors.cpp').read_text(encoding='utf-8')
a=doors.index('static std::atomic_uint64_t disabledDoorContacts');b=doors.index('struct Leaf {',a);contact=doors[a:b].replace('DoorContactListener','ContainerContactListener').replace('doorContacts','containerContacts').replace('disabledDoorContacts','disabledContainerContacts').replace('DoorIgnoresPartnerLayer','ContainerIgnoresPartnerLayer')
s=s.replace('#include "models.generated.h"','#include "models.generated.h"\n#include "contact_policy.h"')
pos=s.index('struct Leaf {');s=s[:pos]+contact+s[pos:]
s=s.replace('const LeafProfile* profile=nullptr;float angle=0;', 'const LeafProfile* profile=nullptr;RE::hkpRigidBody* contactBody=nullptr;std::uint32_t contactUid=0;float angle=0;')
s=s.replace('   auto& a=l.profile->axis;', '''   if(l.contactBody!=leaf || l.contactUid!=leaf->uid){leaf->contactPointCallbackDelay=0;leaf->AddContactListener(&containerContacts);l.contactBody=leaf;l.contactUid=leaf->uid;}
   auto& a=l.profile->axis;''')
needle='   auto current=rotate(leaf,{p[0],p[1],p[2]});'
s=s.replace(needle,'''   if(l.profile->sliding){
    auto origin=read(anchor->motion.motionState.transform.translation),position=read(leaf->motion.motionState.transform.translation);
    float distance=dot(add(position,scale(origin,-1)),axis);float limited=d.locked?0.f:std::clamp(distance,0.f,l.profile->limit);
    auto target=add(origin,scale(axis,limited));auto error=add(position,scale(target,-1));
    auto x=rotate(anchor,{1,0,0}),y=rotate(anchor,{0,1,0}),z=rotate(anchor,{0,0,1});
    if(dot(error,error)>.000025f || dot(rotate(leaf,{1,0,0}),x)<.99999f || dot(rotate(leaf,{0,1,0}),y)<.99999f){auto pos=packed(target);auto q=quaternion(x,y,z);l.body->SetPositionAndRotation(pos,q);}
    float speed=d.locked?0.f:std::clamp(dot(read(leaf->motion.linearVelocity),axis),-.20f,.20f);
    if((limited<=0 && speed<0)||(limited>=l.profile->limit && speed>0))speed=0;
    leaf->SetLinearVelocity(packed(scale(axis,speed)));leaf->SetAngularVelocity(packed({0,0,0}));
    bool touched=held || handNear(l.body);touchedAny|=touched;l.angle=limited;
    if((d.locked && touched)||(!d.locked && touched && limited>std::min(.10f,.35f*l.profile->limit)))queue(d);
    continue;
   }
'''+needle)
s=s.replace('std::clamp(angle,0.f,1.8f)','std::clamp(angle,0.f,l.profile->limit)').replace('angle>=1.8f','angle>=l.profile->limit')
a=s.index('   // Stay open after looting.');b=s.index('   auto angular=',a);s=s[:a]+'''   // No return spring: released parts stay where the player left them.
   omega=std::clamp(omega,-.65f,.65f);
'''+s[b:]
s=s.replace('dot(error,error)>1e-6f','dot(error,error)>.000025f')
s=s.replace('leaf.angle=previous.angle;break;', 'leaf.angle=previous.angle;leaf.contactBody=previous.contactBody;leaf.contactUid=previous.contactUid;break;')
s=s.replace('C1 registered','C2 registered').replace('REL::Version{0,1,0,0}','REL::Version{0,2,0,0}')
Path('physical-containers/physical_containers.cpp').write_text(s,encoding='utf-8')
policy=Path('standalone-doors/contact_policy.h').read_text().replace('DoorIgnoresPartnerLayer','ContainerIgnoresPartnerLayer')
Path('physical-containers/contact_policy.h').write_text(policy,encoding='utf-8')
