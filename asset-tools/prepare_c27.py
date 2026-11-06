from pathlib import Path
import sys,json,shutil,struct,math

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'standalone-doors'))
from nif_io import Nif,node_offsets
BASE=ROOT/'nexus-release/candidate/SVRPhysicalContainers'
OUT=ROOT/'physical-containers/c27'
OUT.mkdir(exist_ok=True)
shutil.copytree(BASE/'source',OUT/'source',dirs_exist_ok=True,
                ignore=shutil.ignore_patterns('*.obj','*.lib','*.exp'))
for name in ('removable_latch.h','removable_latch_test.cpp'):
    shutil.copy2(ROOT/'physical-containers'/name,OUT/'source'/name)
profiles=[r for r in json.loads((ROOT/'physical-containers/build-report.json').read_text()) if 'error' not in r]
audit=[]
for row in profiles:
    rel=Path('meshes')/row['physical_model'].replace('\\','/')
    data=(BASE/rel).read_bytes();n=Nif(data)
    names={n.strings[struct.unpack_from('<i',b)[0]]:i for i,(kind,b) in enumerate(n.blocks)
           if kind in ('NiNode','BSFadeNode') and struct.unpack_from('<i',b)[0]>=0}
    free=any(k in row['model'].replace('\\','/').rsplit('/',1)[-1].lower() for k in ('urn','barrel','canopicjar'))
    radii=[]; bodies=[]; shaders=[]
    for leaf in row['leaves']:
        node=n.blocks[names[leaf['leaf']]][1]
        co=struct.unpack_from('<i',node,node_offsets(node)['collision'])[0]
        bi=struct.unpack_from('<i',n.blocks[co][1],6)[0];body=n.blocks[bi][1]
        assert struct.unpack_from('<I',body,244)[0]==(0 if free else 1)
        if free:
            assert n.blocks[bi][0]=='bhkRigidBody'
            shape=n.blocks[struct.unpack_from('<i',body)[0]]
            assert shape[0]=='bhkConvexVerticesShape'
            vertices=[struct.unpack_from('<3f',shape[1],36+i*16) for i in range(struct.unpack_from('<I',shape[1],32)[0])]
            widths=[max(v[j] for v in vertices)-min(v[j] for v in vertices) for j in range(3)]
            radii.append(min(.70,max(.08,max(widths[:2])*.5+.04)))
            struct.pack_into('<f',body,196,1.0) # bhkRigidBodyCInfo2010 Gravity Factor.
            struct.pack_into('<2f',body,212,6.0,10.0) # Normal free movement, not hinge speed limits.
            bodies.append(bi)
        else:radii.append(.2)
    # Preserve existing texture assignments, UVs and geometry; render reverse faces too.
    for i,(kind,b) in enumerate(n.blocks):
        if kind=='BSLightingShaderProperty':offset=20+4*struct.unpack_from('<I',b,8)[0]
        elif kind=='BSEffectShaderProperty':offset=16+4*struct.unpack_from('<I',b,4)[0]
        else:continue
        flags=struct.unpack_from('<I',b,offset)[0]
        if not flags&16:
            struct.pack_into('<I',b,offset,flags|16);shaders.append(i)
    encoded=n.encode();assert Nif(encoded).encode()==encoded
    old=Nif(data);allowed=set(bodies+shaders)
    assert len(old.blocks)==len(n.blocks) and old.strings==n.strings
    for i in range(len(n.blocks)):
        if i not in allowed:assert n.blocks[i]==old.blocks[i]
    dest=OUT/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(encoded)
    audit.append({'model':row['model'],'free':free,'bodies':bodies,'two_sided_materials':shaders,'radii':radii})

q=lambda s:json.dumps(s,ensure_ascii=False)
header='''#pragma once
struct LeafProfile {const char* leaf;const char* shadow;float axis[3];float perpendicular[3];bool sliding;float limit;bool removable=false;float snapRadius=.2f;};
struct ModelProfile {const char* original;const char* physical;std::initializer_list<LeafProfile> leaves;};
static const ModelProfile MODELS[]={
'''
for row,entry in zip(profiles,audit):
    leaves=[]
    for p,radius in zip(row['leaves'],entry['radii']):
        leaves.append('{'+q(p['leaf'])+','+q(p['animated_node'])+',{'+','.join(str(v)+'.f' for v in p['axis'])+'},{'+','.join(str(v)+'.f' for v in p['perpendicular'])+'},'+('true' if p['mechanism']=='slide' else 'false')+','+str(p['limit'])+'f,'+('true' if entry['free'] else 'false')+','+str(round(radius,6))+'f}')
    header+='{'+q(row['model'])+','+q(row['physical_model'])+',{'+','.join(leaves)+'}},\n'
header+='};\n';(OUT/'source/models.generated.h').write_text(header,encoding='utf-8')
cpp=(OUT/'source/physical_containers.cpp').read_text(encoding='utf-8')
cpp=cpp.replace('#include "latch.h"','#include "latch.h"\n#include "removable_latch.h"')
start=cpp.index('    auto delta=',cpp.index('if(l.profile->removable){'))
end=cpp.index('    if(l.latch.latched){',start)
cpp=cpp[:start]+'''    // Compare centres, not hinge origins: a rotated lid must not need an exact pivot match.
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
'''+cpp[end:]
cpp=cpp.replace('C2.6 removable lids','C2.7 gravity/rim-snap lids').replace('REL::Version{0,2,6,0}','REL::Version{0,2,7,0}')
cpp=cpp.replace('!d.locked && partHeld && distance>.12f', '!d.locked && !l.latch.latched && partHeld && distance>.12f')
(OUT/'source/physical_containers.cpp').write_text(cpp,encoding='utf-8')
texture=Path('textures/svrphysicalcontainersc23/barrel_inside.dds');(OUT/texture).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BASE/texture,OUT/texture)
(OUT/'SKSE/Plugins').mkdir(parents=True,exist_ok=True)
(OUT/'asset-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print(json.dumps({'models':len(audit),'free_models':sum(a['free'] for a in audit),'new_two_sided_materials':sum(len(a['two_sided_materials']) for a in audit)},indent=2))
